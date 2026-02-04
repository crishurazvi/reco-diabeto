import streamlit as st
import pandas as pd

# ==========================================
# 0. CONFIGURATION & STYLE
# ==========================================
st.set_page_config(
    page_title="Architecte Diabète ADA/EASD 2022",
    page_icon="🧬",
    layout="wide"
)

# CSS Avancé pour différencier les actions
st.markdown("""
    <style>
    .action-stop { border-left: 6px solid #d9534f; background-color: #fff5f5; padding: 15px; margin-bottom: 10px; border-radius: 4px; }
    .action-start { border-left: 6px solid #28a745; background-color: #f0fff4; padding: 15px; margin-bottom: 10px; border-radius: 4px; }
    .action-switch { border-left: 6px solid #007bff; background-color: #eef7ff; padding: 15px; margin-bottom: 10px; border-radius: 4px; }
    .action-alert { border-left: 6px solid #ffc107; background-color: #fffbf0; padding: 15px; margin-bottom: 10px; border-radius: 4px; }
    .citation { font-size: 0.85em; color: #666; font-style: italic; margin-top: 5px; }
    .metric-box { text-align: center; padding: 10px; background: #f8f9fa; border-radius: 5px; }
    </style>
""", unsafe_allow_html=True)

DISCLAIMER = "⚠️ **AIDE À LA DÉCISION CLINIQUE**: Algorithme basé sur le Rapport de Consensus ADA/EASD 2022. Ne remplace pas le jugement clinique."

# ==========================================
# 1. CLASSES DE DÉFINITION (BASE DE CONNAISSANCES)
# ==========================================
# Définitions basées sur le texte fourni (Table 1 & Texte)
DRUG_CLASSES = {
    "Metformin": {"type": "Oral", "contra_egfr": 30, "warning_egfr": 45},
    "SGLT2i": {"type": "Oral", "contra_egfr": 20, "benefit": ["HF", "CKD", "ASCVD"]},  # init >=20
    "GLP1_RA": {"type": "Injectable", "contra_egfr": 15, "benefit": ["ASCVD", "Weight", "CKD_Secondary"]},
    "GIP_GLP1": {"type": "Injectable", "contra_egfr": 15, "benefit": ["Weight++", "Glycemia++"]},  # Tirzepatide
    "DPP4i": {"type": "Oral", "contra_egfr": 0, "conflict": ["GLP1_RA", "GIP_GLP1"]},
    "SU": {"type": "Oral", "contra_egfr": 60, "risk": "Hypo"},
    "TZD": {"type": "Oral", "contra": "HF"},
    "Insulin_Basal": {"type": "Injectable", "risk": "Hypo"},
    "Insulin_Prandial": {"type": "Injectable", "risk": "Hypo"}
}

# ==========================================
# 2. UI - ENTRÉE DES DONNÉES (SIDEBAR)
# ==========================================
st.sidebar.title("🧬 Données Cliniques")
st.sidebar.caption("Conforme au Consensus ADA/EASD 2022")

st.sidebar.subheader("Profil Patient")
c1, c2 = st.sidebar.columns(2)
age = c1.number_input("Âge (ans)", 18, 100, 55)
weight = c2.number_input("Poids (kg)", 40, 250, 95)
height = st.sidebar.number_input("Taille (cm)", 100, 240, 175)
bmi = weight / ((height / 100) ** 2)
st.sidebar.markdown(f"**IMC:** {bmi:.1f} kg/m²")

st.sidebar.subheader("Laboratoire")
hba1c = st.sidebar.number_input("HbA1c (%)", 4.0, 18.0, 8.2, step=0.1)
target_a1c = st.sidebar.selectbox("Cible HbA1c", [6.5, 7.0, 7.5, 8.0], index=1)
egfr = st.sidebar.number_input("eGFR (mL/min)", 5, 140, 45)
acr = st.sidebar.selectbox("Albuminurie (uACR)", ["A1 Normal (<30 mg/g)", "A2 Micro (30-300 mg/g)", "A3 Macro (>300 mg/g)"])

st.sidebar.subheader("Comorbidités (Cardio-rénal)")
ascvd = st.sidebar.checkbox("ASCVD (IDM, AVC, AOMI)")
hf = st.sidebar.checkbox("Insuffisance Cardiaque (IC)")
ckd_dx = st.sidebar.checkbox("Diagnostic MRC (Maladie Rénale)")
if acr != "A1 Normal (<30 mg/g)":
    ckd_dx = True

st.sidebar.subheader("Sévérité / Drapeaux rouges")
newly_dx = st.sidebar.checkbox("Diagnostic récent (<1 an)")
catabolic = st.sidebar.checkbox("Symptômes cataboliques (perte poids, polyurie...)")
ketosis = st.sidebar.checkbox("Cétonurie / Cétose (ou suspicion)")
acute_illness = st.sidebar.checkbox("Maladie aiguë / Hospitalisation")
suspected_t1d = st.sidebar.checkbox("Suspicion DT1/LADA (début rapide, IMC faible...)")

st.sidebar.subheader("Traitement Actuel")
current_meds = []
if st.sidebar.checkbox("Metformine"):
    current_meds.append("Metformin")
if st.sidebar.checkbox("SGLT2i (Dapa/Empa/Cana)"):
    current_meds.append("SGLT2i")
if st.sidebar.checkbox("GLP-1 RA (Sema/Dula/Lira)"):
    current_meds.append("GLP1_RA")
if st.sidebar.checkbox("GIP/GLP-1 RA (Tirzépatide)"):
    current_meds.append("GIP_GLP1")
if st.sidebar.checkbox("DPP-4i (Sita/Lina/Vilda)"):
    current_meds.append("DPP4i")
if st.sidebar.checkbox("Sulfonylurée (SU)"):
    current_meds.append("SU")
if st.sidebar.checkbox("TZD (Pioglitazone)"):
    current_meds.append("TZD")
if st.sidebar.checkbox("Insuline Basale"):
    current_meds.append("Insulin_Basal")
if st.sidebar.checkbox("Insuline Prandiale"):
    current_meds.append("Insulin_Prandial")

# ==========================================
# 3. MOTEUR DE DÉCISION
# ==========================================
def generate_plan(meds, hba1c, target, egfr, bmi, ascvd, hf, ckd, age, newly_dx, catabolic, ketosis, acute_illness, suspected_t1d):
    plan = []
    simulated_meds = meds.copy()

    def stop_su_if_present(reason, ref):
        if "SU" in simulated_meds:
            plan.append({
                "type": "STOP",
                "text": "ARRÊTEZ la Sulfonylurée (SU)",
                "reason": reason,
                "ref": ref
            })
            simulated_meds.remove("SU")

    def stop_dpp4_if_incretin_present():
        has_incretin = ("GLP1_RA" in simulated_meds) or ("GIP_GLP1" in simulated_meds)
        if "DPP4i" in simulated_meds and has_incretin:
            plan.append({
                "type": "STOP",
                "text": "ARRÊTEZ le DPP-4i",
                "reason": "Ne combinez pas DPP-4i avec GLP-1 RA ou GIP/GLP-1 RA (mécanismes similaires, bénéfice faible).",
                "ref": "Consensus Report: Principles of Care"
            })
            simulated_meds.remove("DPP4i")

    # -----------------------------------------------------
    # ÉTAPE 1: SÉCURITÉ & SANITISATION
    # -----------------------------------------------------
    if "Metformin" in simulated_meds:
        if egfr < 30:
            plan.append({
                "type": "STOP",
                "text": "ARRÊTEZ la Metformine",
                "reason": "Contre-indication : eGFR < 30 ml/min.",
                "ref": "Consensus Report: Table 1"
            })
            simulated_meds.remove("Metformin")
        elif egfr < 45:
            plan.append({
                "type": "ALERT",
                "text": "Réduisez la dose de Metformine",
                "reason": "Envisagez une réduction de dose si eGFR < 45.",
                "ref": "Consensus Report: Other glucose-lowering medications"
            })

    # SGLT2i: NE PAS initier sous 20, mais NE PAS arrêter automatiquement si déjà initié et toléré
    if "SGLT2i" in simulated_meds and egfr < 20:
        plan.append({
            "type": "ALERT",
            "text": "NE PAS initier SGLT2i si eGFR < 20 ; si déjà en cours, poursuivre si toléré",
            "reason": "L'initiation n'est pas recommandée si eGFR < 20. Si déjà initié, peut être continué pour le bénéfice cardio-rénal, si toléré.",
            "ref": "ADA-KDIGO 2022 / Consensus"
        })
        # on ne le retire pas de la liste

    if "TZD" in simulated_meds and hf:
        plan.append({
            "type": "STOP",
            "text": "ARRÊTEZ TZD (Pioglitazone)",
            "reason": "Risque de rétention hydrique et aggravation de l'IC.",
            "ref": "Consensus Report: Thiazolidinediones"
        })
        simulated_meds.remove("TZD")

    # Redondance incrétinique
    stop_dpp4_if_incretin_present()

    # Situations de sécurité où SGLT2i est temporairement évité (cétose/maladie aiguë)
    if "SGLT2i" in simulated_meds and (ketosis or acute_illness):
        plan.append({
            "type": "ALERT",
            "text": "Envisagez une PAUSE temporaire du SGLT2i",
            "reason": "En cas de maladie aiguë ou suspicion de cétose, risque accru d'acidocétose (DKA) ; réévaluer après stabilisation.",
            "ref": "Consensus Report: Safety considerations"
        })

    # -----------------------------------------------------
    # ÉTAPE 2: DRAPEAUX ROUGES -> INSULINE (pas seulement HbA1c)
    # -----------------------------------------------------
    red_flags = suspected_t1d or ketosis or catabolic or acute_illness
    if red_flags:
        if "Insulin_Basal" not in simulated_meds:
            plan.append({
                "type": "START",
                "text": "INITIEZ l'Insuline Basale (prioritaire)",
                "reason": "Drapeaux rouges (catabolisme/cétose/maladie aiguë/suspicion DT1) -> contrôle rapide et sûr ; ne pas attendre l'escalade thérapeutique.",
                "ref": "Consensus Report: Place of Insulin"
            })
            simulated_meds.append("Insulin_Basal")

        stop_su_if_present(
            reason="À l'initiation de l'insuline, les SU augmentent considérablement le risque d'hypoglycémie.",
            ref="Consensus Report: Hypoglycemia risk / Place of Insulin"
        )

        if hba1c >= 10 and "Insulin_Prandial" not in simulated_meds:
            plan.append({
                "type": "START",
                "text": "Envisagez une intensification rapide (± insuline prandiale)",
                "reason": "Hyperglycémie sévère + drapeaux rouges : peut nécessiter un régime plus intensif initialement.",
                "ref": "Consensus Report: Severe hyperglycemia"
            })

    # -----------------------------------------------------
    # ÉTAPE 3: PROTECTION D'ORGANE (indépendant de A1c/metformine)
    # -----------------------------------------------------
    if hf and "SGLT2i" not in simulated_meds and egfr >= 20 and (not ketosis) and (not acute_illness):
        plan.append({
            "type": "START",
            "text": "INITIEZ SGLT2i (Dapa/Empa)",
            "reason": "Bénéfice prouvé pour réduire les hospitalisations IC et la mortalité CV dans l'IC.",
            "ref": "Consensus Rec: People with HF"
        })
        simulated_meds.append("SGLT2i")

    if ckd and "SGLT2i" not in simulated_meds and egfr >= 20 and (not ketosis) and (not acute_illness):
        plan.append({
            "type": "START",
            "text": "INITIEZ SGLT2i",
            "reason": "Préféré pour ralentir la progression de la MRC et réduire les hospitalisations IC.",
            "ref": "Consensus Rec: People with CKD"
        })
        simulated_meds.append("SGLT2i")

    if ckd and "SGLT2i" not in simulated_meds and egfr < 20:
        if "GLP1_RA" not in simulated_meds and "GIP_GLP1" not in simulated_meds:
            plan.append({
                "type": "START",
                "text": "INITIEZ GLP-1 RA",
                "reason": "Alternative lorsque le SGLT2i ne peut pas être initié (eGFR < 20).",
                "ref": "Consensus Rec: CKD alternative"
            })
            simulated_meds.append("GLP1_RA")
            stop_dpp4_if_incretin_present()

    # ASCVD: strict 2022 -> considère “proven CV benefit” uniquement SGLT2i ou GLP-1 RA (pas GIP/GLP1 automatiquement)
    if ascvd:
        has_protection_strict = ("SGLT2i" in simulated_meds) or ("GLP1_RA" in simulated_meds)

        # Si sous GIP/GLP1 mais sans SGLT2i ou GLP1_RA, préférer SGLT2i (si éligible) plutôt que d'ajouter GLP1 par dessus
        if (not has_protection_strict) and ("GIP_GLP1" in simulated_meds):
            if ("SGLT2i" not in simulated_meds) and egfr >= 20 and (not ketosis) and (not acute_illness):
                plan.append({
                    "type": "START",
                    "text": "INITIEZ SGLT2i (pour protection CV avec ASCVD)",
                    "reason": "Dans l'algorithme strict 2022, le bénéfice CV prouvé concerne SGLT2i/GLP-1 RA. Évitez le doublon incrétinique.",
                    "ref": "Consensus Rec: People with established CVD"
                })
                simulated_meds.append("SGLT2i")
            elif "GLP1_RA" not in simulated_meds:
                plan.append({
                    "type": "ALERT",
                    "text": "Envisagez le passage à un GLP-1 RA avec bénéfice CV prouvé",
                    "reason": "Si le SGLT2i ne peut pas être initié, pour l'ASCVD, l'algorithme 2022 favorise les GLP-1 RA avec bénéfices CV prouvés.",
                    "ref": "Consensus Rec: People with established CVD"
                })

        if not has_protection_strict and ("GIP_GLP1" not in simulated_meds):
            plan.append({
                "type": "START",
                "text": "INITIEZ GLP-1 RA ou SGLT2i",
                "reason": "ASCVD -> agent avec bénéfice CV prouvé, indépendant de l'HbA1c.",
                "ref": "Consensus Rec: People with established CVD"
            })
            if (egfr >= 20) and (bmi <= 27) and (not ketosis) and (not acute_illness):
                simulated_meds.append("SGLT2i")
            else:
                simulated_meds.append("GLP1_RA")
                stop_dpp4_if_incretin_present()

    # -----------------------------------------------------
    # ÉTAPE 4: INTENSIFICATION GLYCÉMIQUE & PONDÉRALE
    # -----------------------------------------------------
    gap = hba1c - target

    if gap > 0:
        # Combo précoce : lié à un écart important et un diagnostic récent
        if newly_dx and gap >= 1.5:
            plan.append({
                "type": "START",
                "text": "Envisagez une Thérapie Combinée Précoce",
                "reason": "Diagnostic récent et HbA1c très au-dessus de la cible (≥1.5%), la combinaison initiale peut être supérieure.",
                "ref": "Consensus Report: Early combination / VERIFY"
            })

        # Metformine comme base si éligible
        if "Metformin" not in simulated_meds and egfr >= 30:
            plan.append({
                "type": "START",
                "text": "AJOUTEZ la Metformine",
                "reason": "Bonne efficacité, coût réduit, vaste expérience.",
                "ref": "Consensus Report: Other medications"
            })
            simulated_meds.append("Metformin")

        # Poids comme cible primaire
        has_weight_drug = ("GLP1_RA" in simulated_meds) or ("GIP_GLP1" in simulated_meds) or ("SGLT2i" in simulated_meds)
        if bmi >= 30 and not has_weight_drug:
            plan.append({
                "type": "START",
                "text": "AJOUTEZ GLP-1 RA ou GIP/GLP-1 RA",
                "reason": "L'obésité est une cible primaire ; les agents incrétiniques ont une grande efficacité sur le poids et l'HbA1c.",
                "ref": "Consensus Report: Weight management"
            })
            simulated_meds.append("GIP_GLP1")
            stop_dpp4_if_incretin_present()

        # Switch DPP-4i -> GLP-1 si existe encore et besoin d'intensification
        if "DPP4i" in simulated_meds and gap > 0.5:
            plan.append({
                "type": "SWITCH",
                "text": "REMPLACEZ DPP-4i par GLP-1 RA",
                "reason": "Le DPP-4i a une efficacité modeste ; le GLP-1 RA a une efficacité supérieure et des bénéfices additionnels.",
                "ref": "Consensus Report: Comparative efficacy"
            })
            simulated_meds.remove("DPP4i")
            if "GLP1_RA" not in simulated_meds and "GIP_GLP1" not in simulated_meds:
                simulated_meds.append("GLP1_RA")

        # GLP-1 avant l'insuline (si pas de drapeaux rouges et HbA1c non extrême)
        has_incretin = ("GLP1_RA" in simulated_meds) or ("GIP_GLP1" in simulated_meds)
        if (not red_flags) and ("Insulin_Basal" not in simulated_meds) and (not has_incretin):
            if hba1c < 10:
                plan.append({
                    "type": "START",
                    "text": "INITIEZ GLP-1 RA (avant l'Insuline)",
                    "reason": "Avant l'insuline basale : bonne efficacité, pas d'hypoglycémie, perte de poids.",
                    "ref": "Consensus Report: Place of Insulin"
                })
                simulated_meds.append("GLP1_RA")
                stop_dpp4_if_incretin_present()
            else:
                plan.append({
                    "type": "START",
                    "text": "INITIEZ l'Insuline Basale (+ envisagez GLP-1 RA)",
                    "reason": "Une hyperglycémie sévère (HbA1c ≥10%) peut nécessiter de l'insuline.",
                    "ref": "Consensus Report: Severe hyperglycemia / Place of Insulin"
                })
                simulated_meds.append("Insulin_Basal")
                stop_su_if_present(
                    reason="À l'initiation de l'insuline, les SU augmentent considérablement le risque d'hypoglycémie.",
                    ref="Consensus Report: Hypoglycemia risk / Place of Insulin"
                )

        # Si a déjà un incrétin et est toujours au-dessus de la cible -> ajouter insuline basale
        if (("GLP1_RA" in simulated_meds) or ("GIP_GLP1" in simulated_meds)) and (gap > 0):
            if "Insulin_Basal" not in simulated_meds:
                plan.append({
                    "type": "START",
                    "text": "INITIEZ l'Insuline Basale",
                    "reason": "Persistance au-dessus de la cible sous thérapie non-insulinique optimisée.",
                    "ref": "Consensus Report: Fig 5"
                })
                simulated_meds.append("Insulin_Basal")
                stop_su_if_present(
                    reason="À l'initiation de l'insuline, les SU augmentent considérablement le risque d'hypoglycémie.",
                    ref="Consensus Report: Hypoglycemia risk / Place of Insulin"
                )

        # Si a déjà basale et est toujours au-dessus de la cible -> prandiale
        if ("Insulin_Basal" in simulated_meds) and (gap > 0) and ("Insulin_Prandial" not in simulated_meds):
            plan.append({
                "type": "START",
                "text": "AJOUTEZ de l'Insuline Prandiale",
                "reason": "Échec sous insuline basale (besoin d'intensification).",
                "ref": "Consensus Report: Insulin intensification"
            })
            simulated_meds.append("Insulin_Prandial")
            stop_su_if_present(
                reason="SU + insuline prandiale augmentent fortement le risque d'hypoglycémie.",
                ref="Consensus Report: Hypoglycemia risk"
            )

    return plan

# ==========================================
# 4. AFFICHAGE DES RÉSULTATS
# ==========================================
plan_actions = generate_plan(
    current_meds, hba1c, target_a1c, egfr, bmi, ascvd, hf, ckd_dx, age,
    newly_dx, catabolic, ketosis, acute_illness, suspected_t1d
)

st.divider()

col_main, col_detail = st.columns([1.5, 1])

with col_main:
    st.header("📋 Plan d'Action Personnalisé")
    st.markdown(DISCLAIMER)

    if not plan_actions and hba1c <= target_a1c:
        st.success("✅ Le patient est à la cible et sous traitement optimisé pour la protection des organes.")
    elif not plan_actions and hba1c > target_a1c:
        st.warning("⚠️ Cas réfractaire. Options standard épuisées. Évaluation par spécialiste pour pompes/technologies avancées.")

    for item in plan_actions:
        icon = ""
        css_class = ""
        if item["type"] == "STOP":
            icon = "⛔"
            css_class = "action-stop"
        elif item["type"] == "START":
            icon = "✅"
            css_class = "action-start"
        elif item["type"] == "SWITCH":
            icon = "🔄"
            css_class = "action-switch"
        else:
            icon = "⚠️"
            css_class = "action-alert"

        st.markdown(f"""
        <div class="{css_class}">
            <strong>{icon} {item["type"]}: {item["text"]}</strong><br>
            <span style="font-size:0.95em">{item["reason"]}</span><br>
            <div class="citation">Source: {item["ref"]}</div>
        </div>
        """, unsafe_allow_html=True)

with col_detail:
    st.subheader("Résumé Clinique & Phénotype")
    st.metric("Glycémie (HbA1c)", f"{hba1c}%", delta=f"{hba1c-target_a1c:.1f}% vs Cible", delta_color="inverse")

    st.markdown("**Statut Organe :**")
    if hf:
        st.warning("Insuffisance Cardiaque (Priorité SGLT2i)")
    elif ckd_dx:
        st.warning("Maladie Rénale (Priorité SGLT2i)")
    elif ascvd:
        st.warning("ASCVD (Priorité GLP-1/SGLT2i)")
    else:
        st.success("Pas de maladie cardio-rénale établie")

    if age < 40:
        st.info("ℹ️ Patient Jeune (<40 ans) : Risque accru de complications à long terme. Agressivité thérapeutique nécessaire.")

    if bmi > 30:
        st.info("ℹ️ Obésité : La gestion du poids est une cible primaire (Tirzépatide/Sémaglutide).")

    if suspected_t1d or ketosis or catabolic or acute_illness:
        st.warning("⚠️ Drapeaux rouges présents : peut nécessiter de l'insuline précocement et une évaluation rapide.")

st.divider()
st.markdown("### 📚 Logique extraite du Consensus ADA/EASD 2022")
with st.expander("Voir les détails de l'algorithme"):
    st.markdown("""
    1.  **Sécurité d'abord (Safety First) :** Arrêt de la Metformine si eGFR < 30 ; réduire la dose si eGFR < 45. Pour les SGLT2i, ne pas initier sous eGFR 20, mais ne pas arrêter automatiquement si déjà initié et toléré.
    2.  **Protection d'Organe :** Ajout des agents prouvés (SGLT2i, GLP-1 RA) indépendant de l'HbA1c ou de l'utilisation de Metformine, en cas d'IC, MRC ou ASCVD.
    3.  **Tirzépatide (Nouveau) :** Le texte met en évidence le Tirzépatide (GIP/GLP-1) comme ayant une efficacité supérieure sur la glycémie et le poids par rapport au GLP-1 RA classique.
    4.  **Positionnement de l'Insuline :** L'algorithme force l'évaluation du GLP-1 RA avant de passer à l'insuline, sauf situations avec drapeaux rouges (cétose, catabolisme, maladie aiguë, suspicion DT1).
    5.  **Dé-prescription :** Identification des redondances (DPP-4i + GLP-1/GIP-GLP-1) et arrêt de ces molécules. Lors de l'initiation de l'insuline, l'arrêt des SU est recommandé pour réduire l'hypoglycémie.
    """)
# ==========================================
# 5. GÉNÉRATEUR DE PRÉSENTATION DE CAS (NOUVEAU)
# ==========================================
st.divider()
st.subheader("🗣️ Demande un avis")

if st.button("Générer la question pour le Diabétologue"):
    
    # 1. Construction des listes de comorbidités (Positifs et Négatifs pertinents)
    comorbs_pos = []
    comorbs_neg = []
    
    if ascvd: comorbs_pos.append("ASCVD établi")
    else: comorbs_neg.append("sans atcds ASCVD")
    
    if hf: comorbs_pos.append("Insuffisance Cardiaque")
    else: comorbs_neg.append("pas d'IC connue")
    
    if ckd_dx: comorbs_pos.append(f"MRC (eGFR {egfr})")
    else: comorbs_neg.append(f"fonction rénale conservée (eGFR {egfr})")

    # 2. Drapeaux rouges (Négatifs pertinents)
    red_flags_neg = []
    if not ketosis: red_flags_neg.append("pas de cétose")
    if not catabolic: red_flags_neg.append("pas de signes cataboliques")
    if not acute_illness: red_flags_neg.append("cliniquement stable")

    # 3. Traitement actuel formaté
    if not current_meds:
        meds_str = "naïf de traitement antidiabétique"
    else:
        meds_str = f"actuellement sous {', '.join(current_meds)}"

    # 4. Synthèse des recommandations de l'algorithme
    recos = [item['text'] for item in plan_actions if item['type'] in ['START', 'STOP', 'SWITCH']]
    if not recos:
        if hba1c <= target_a1c:
            proposition = "Le patient est à la cible, je propose de maintenir le traitement actuel."
        else:
            proposition = "Le patient n'est pas à la cible mais les options standard semblent épuisées. Quelle est votre conduite à tenir ?"
    else:
        proposition = f"Conformément aux recommandations, je pensais : {'; '.join(recos)}."

    # 5. Construction du texte final
    texte_presentation = f"""
"Bonjour Docteur, j'aimerais votre avis sur un patient de {age} ans, IMC {bmi:.1f} kg/m².

Concernant le terrain :
- Il présente  {', '.join(comorbs_pos) if comorbs_pos else 'Aucune comorbidité cardio-rénale majeure'}.
- À noter l'absence de  {', '.join(comorbs_neg)}.
- Sur le plan aigu  {', '.join(red_flags_neg)}.

Biologie actuelle : HbA1c à {hba1c}% (Cible {target_a1c}%) et eGFR à {egfr} ml/min.

Il est {meds_str}.

{proposition}
Êtes-vous d'accord avec cette modification thérapeutique ?"
    """

    st.info("💡 Copiez ce texte dans le dossier :")
    st.code(texte_presentation, language="text")
