import streamlit as st
import pandas as pd

# ==========================================
# 0. CONFIGURATION & STYLE
# ==========================================
st.set_page_config(
    page_title="Architecte Diabète ADA/EASD 2025",
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

DISCLAIMER = "⚠️ **AIDE À LA DÉCISION CLINIQUE**: Algorithme basé sur les **Standards of Care ADA 2025**. Ne remplace pas le jugement clinique."

# ==========================================
# 1. CLASSES DE DÉFINITION (BASE DE CONNAISSANCES 2025)
# ==========================================
DRUG_CLASSES = {
    "Metformin": {"type": "Oral", "contra_egfr": 30, "warning_egfr": 45},
    "SGLT2i": {"type": "Oral", "contra_egfr": 20, "benefit": ["HF", "CKD", "ASCVD"]},  # Init >=20, continue until dialysis
    "GLP1_RA": {"type": "Injectable", "contra_egfr": 15, "benefit": ["ASCVD", "Weight", "CKD_FLOW", "MASLD"]}, # Updated 2025: CKD & Liver
    "GIP_GLP1": {"type": "Injectable", "contra_egfr": 15, "benefit": ["Weight+++", "Glycemia+++"]},  # Tirzepatide
    "DPP4i": {"type": "Oral", "contra_egfr": 0, "conflict": ["GLP1_RA", "GIP_GLP1"]},
    "SU": {"type": "Oral", "contra_egfr": 60, "risk": "Hypo"},
    "TZD": {"type": "Oral", "contra": "HF", "benefit": ["MASLD"]}, # Updated 2025: Benefit in MASLD
    "Insulin_Basal": {"type": "Injectable", "risk": "Hypo"},
    "Insulin_Prandial": {"type": "Injectable", "risk": "Hypo"}
}

# ==========================================
# 2. UI - ENTRÉE DES DONNÉES (SIDEBAR)
# ==========================================
st.sidebar.title("🧬 Données Cliniques")
st.sidebar.caption("Conforme aux Standards ADA/EASD 2025")

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

st.sidebar.subheader("Comorbidités (Cardio-rénal-Métabolique)")
ascvd = st.sidebar.checkbox("ASCVD (IDM, AVC, AOMI)")
hf = st.sidebar.checkbox("Insuffisance Cardiaque (IC)")
ckd_dx = st.sidebar.checkbox("Diagnostic MRC (Maladie Rénale)")
if acr != "A1 Normal (<30 mg/g)":
    ckd_dx = True
# 2025 UPDATE: LIVER SCREENING
masld = st.sidebar.checkbox("MASLD/MASH (Steatose/Fibrose hépatique)")

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
# 3. MOTEUR DE DÉCISION (LOGIQUE 2025)
# ==========================================
def generate_plan(meds, hba1c, target, egfr, bmi, ascvd, hf, ckd, masld, age, newly_dx, catabolic, ketosis, acute_illness, suspected_t1d):
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
                "reason": "Redondance thérapeutique : Ne combinez pas DPP-4i avec GLP-1 RA ou GIP/GLP-1 RA.",
                "ref": "ADA Standards 2025: Pharmacologic Therapy"
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
                "reason": "Contre-indication absolue : eGFR < 30 ml/min.",
                "ref": "ADA Standards: CKD"
            })
            simulated_meds.remove("Metformin")
        elif egfr < 45:
            plan.append({
                "type": "ALERT",
                "text": "Réduisez la dose de Metformine (Max 1g/j)",
                "reason": "Prudence si eGFR < 45.",
                "ref": "ADA Standards: CKD"
            })

    # SGLT2i Safety
    if "SGLT2i" in simulated_meds and egfr < 20:
        plan.append({
            "type": "ALERT",
            "text": "SGLT2i : Ne pas initier si < 20, mais poursuivre si déjà toléré jusqu'à la dialyse",
            "reason": "Pour la protection rénale/cardiaque, le traitement peut être continué malgré un eGFR bas (sauf intolérance).",
            "ref": "ADA/KDIGO 2024-2025"
        })

    if "TZD" in simulated_meds and hf:
        plan.append({
            "type": "STOP",
            "text": "ARRÊTEZ TZD (Pioglitazone)",
            "reason": "Contre-indication : Risque d'aggravation de l'Insuffisance Cardiaque.",
            "ref": "ADA Standards: HF"
        })
        simulated_meds.remove("TZD")

    stop_dpp4_if_incretin_present()

    # Règles "Sick Day"
    if "SGLT2i" in simulated_meds and (ketosis or acute_illness):
        plan.append({
            "type": "ALERT",
            "text": "PAUSE temporaire du SGLT2i (Risque Acidocétose)",
            "reason": "Arrêt immédiat en cas de maladie aiguë, jeûne prolongé ou cétose. Reprendre quand stabilisé.",
            "ref": "ADA Standards: Safety"
        })

    # -----------------------------------------------------
    # ÉTAPE 2: DRAPEAUX ROUGES -> INSULINE
    # -----------------------------------------------------
    red_flags = suspected_t1d or ketosis or catabolic or acute_illness
    if red_flags:
        if "Insulin_Basal" not in simulated_meds:
            plan.append({
                "type": "START",
                "text": "INITIEZ l'Insuline Basale (URGENT)",
                "reason": "Drapeaux rouges (catabolisme/cétose/suspi DT1) nécessitent l'insuline immédiate.",
                "ref": "ADA Standards: Injectables"
            })
            simulated_meds.append("Insulin_Basal")

        stop_su_if_present(
            reason="Risque majeur d'hypoglycémie à l'initiation de l'insuline.",
            ref="ADA Standards: Hypoglycemia"
        )
        # On arrête ici l'algo pour les cas aigus graves
    
    # -----------------------------------------------------
    # ÉTAPE 3: PROTECTION D'ORGANE (PRIORITÉ 2025)
    # -----------------------------------------------------
    if not red_flags:
        # A. INSUFFISANCE CARDIAQUE (HF) -> SGLT2i Roi
        if hf and "SGLT2i" not in simulated_meds and egfr >= 20:
            plan.append({
                "type": "START",
                "text": "INITIEZ SGLT2i (Dapa/Empa/Sota)",
                "reason": "Pilier du traitement de l'IC (FE réduite ou préservée).",
                "ref": "ADA Standards 2025: HF"
            })
            simulated_meds.append("SGLT2i")

        # B. MALADIE RÉNALE (CKD) -> 2025 UPDATE: SGLT2i AND/OR GLP-1 (FLOW Trial)
        if ckd:
            # 1. SGLT2i First
            if "SGLT2i" not in simulated_meds and egfr >= 20:
                plan.append({
                    "type": "START",
                    "text": "INITIEZ SGLT2i (Protection Rénale)",
                    "reason": "Ralentit la progression de la MRC et réduit le risque CV.",
                    "ref": "ADA Standards 2025: CKD"
                })
                simulated_meds.append("SGLT2i")
            
            # 2. GLP-1 RA (Semaglutide) Second or Combined - NOUVEAU 2025
            if ("GLP1_RA" not in simulated_meds and "GIP_GLP1" not in simulated_meds):
                reason_ckd = "Alternative au SGLT2i si intolérance OU thérapie combinée pour protection rénale additionnelle (Étude FLOW)."
                if "SGLT2i" in simulated_meds:
                    reason_ckd = "Envisagez l'ajout de GLP-1 RA (Semaglutide) pour renforcer la protection rénale (Étude FLOW)."
                
                plan.append({
                    "type": "START",
                    "text": "Envisagez GLP-1 RA (Semaglutide)",
                    "reason": reason_ckd,
                    "ref": "ADA Standards 2025 / FLOW Trial"
                })
                # On l'ajoute virtuellement pour la suite
                # simulated_meds.append("GLP1_RA") 

        # C. ASCVD (Cardio)
        if ascvd:
            has_protection = ("SGLT2i" in simulated_meds) or ("GLP1_RA" in simulated_meds)
            if not has_protection:
                plan.append({
                    "type": "START",
                    "text": "INITIEZ GLP-1 RA ou SGLT2i",
                    "reason": "Bénéfice MACE prouvé (IDM/AVC/Décès CV) indépendant de l'HbA1c.",
                    "ref": "ADA Standards 2025: ASCVD"
                })
                if bmi > 27:
                    simulated_meds.append("GLP1_RA")
                    stop_dpp4_if_incretin_present()
                else:
                    simulated_meds.append("SGLT2i")

        # D. MASLD / FOIE (NOUVEAU 2025)
        if masld and not hf:
             has_liver_drug = ("GLP1_RA" in simulated_meds) or ("GIP_GLP1" in simulated_meds) or ("TZD" in simulated_meds)
             if not has_liver_drug:
                 plan.append({
                    "type": "START",
                    "text": "Envisagez GLP-1 RA ou Pioglitazone",
                    "reason": "MASLD : Les agonistes GLP-1 ou la Pioglitazone ont un bénéfice histologique prouvé sur la stéatohépatite.",
                    "ref": "ADA Standards 2025: MASLD"
                 })

    # -----------------------------------------------------
    # ÉTAPE 4: GESTION DU POIDS & GLYCÉMIE (HIERARCHIE 2025)
    # -----------------------------------------------------
    gap = hba1c - target
    
    # Gestion du POIDS comme cible primaire (2025)
    has_weight_drug = ("GLP1_RA" in simulated_meds) or ("GIP_GLP1" in simulated_meds)
    if bmi >= 30 and not has_weight_drug and not red_flags:
        drug_choice = "GIP/GLP-1 RA (Tirzépatide)"
        reason_weight = "Efficacité pondérale très élevée (supérieure au GLP-1 seul)."
        
        plan.append({
            "type": "START",
            "text": f"INITIEZ {drug_choice}",
            "reason": f"Obésité : La gestion du poids est un objectif co-primaire. {reason_weight}",
            "ref": "ADA Standards 2025: Obesity"
        })
        simulated_meds.append("GIP_GLP1")
        stop_dpp4_if_incretin_present()

    # Gestion de la GLYCÉMIE (si écart persistant)
    if gap > 0 and not red_flags:
        # 1. Metformine Base
        if "Metformin" not in simulated_meds and egfr >= 30:
             plan.append({
                "type": "START",
                "text": "AJOUTEZ la Metformine",
                "reason": "Traitement de fond efficace et sûr.",
                "ref": "ADA Standards 2025"
            })
             simulated_meds.append("Metformin")

        # 2. Switch DPP-4 -> Incretin plus puissant
        if "DPP4i" in simulated_meds and gap > 0.5:
             plan.append({
                "type": "SWITCH",
                "text": "REMPLACEZ DPP-4i par GIP/GLP-1 ou GLP-1 RA",
                "reason": "Le DPP-4i est peu puissant. Passage à un injectable pour efficacité glycémique majeure.",
                "ref": "ADA Standards 2025"
             })
             simulated_meds.remove("DPP4i")
             simulated_meds.append("GIP_GLP1")

        # 3. Positionnement Insuline
        has_potent_injectable = ("GLP1_RA" in simulated_meds) or ("GIP_GLP1" in simulated_meds)
        if "Insulin_Basal" not in simulated_meds:
            if not has_potent_injectable:
                plan.append({
                    "type": "START",
                    "text": "INITIEZ GLP-1 RA / GIP-GLP1 (avant Insuline)",
                    "reason": "L'insuline ne doit être considérée qu'après échec des incrétino-mimétiques (sauf signes cataboliques).",
                    "ref": "ADA Standards 2025: Injectables"
                })
                simulated_meds.append("GLP1_RA")
            else:
                # Echec sous GLP-1/GIP-GLP1 -> Insuline
                plan.append({
                    "type": "START",
                    "text": "INITIEZ l'Insuline Basale",
                    "reason": "Échec thérapeutique sous traitement non-insulinique optimisé.",
                    "ref": "ADA Standards 2025"
                })
                simulated_meds.append("Insulin_Basal")
                stop_su_if_present("Risque Hypo", "ADA 2025")

        # 4. Intensification Insuline
        if "Insulin_Basal" in simulated_meds and "Insulin_Prandial" not in simulated_meds:
             plan.append({
                "type": "START",
                "text": "AJOUTEZ Insuline Prandiale ou iGLP-1",
                "reason": "Intensification nécessaire.",
                "ref": "ADA Standards 2025"
             })

    return plan

# ==========================================
# 4. AFFICHAGE DES RÉSULTATS
# ==========================================
plan_actions = generate_plan(
    current_meds, hba1c, target_a1c, egfr, bmi, ascvd, hf, ckd_dx, masld, age,
    newly_dx, catabolic, ketosis, acute_illness, suspected_t1d
)

st.divider()

col_main, col_detail = st.columns([1.5, 1])

with col_main:
    st.header("📋 Plan d'Action (ADA 2025)")
    st.markdown(DISCLAIMER)

    if not plan_actions and hba1c <= target_a1c:
        st.success("✅ Patient à la cible et sous traitement cardio-rénal optimisé.")
    elif not plan_actions and hba1c > target_a1c:
        st.warning("⚠️ Cas complexe/réfractaire. Avis spécialisé requis (Pompes, Greffe, etc.).")

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
    st.subheader("Phénotype Clinique")
    st.metric("Glycémie (HbA1c)", f"{hba1c}%", delta=f"{hba1c-target_a1c:.1f}% vs Cible", delta_color="inverse")

    st.markdown("**Priorités Organiques :**")
    if hf:
        st.error("Insuffisance Cardiaque (Priorité Absolue SGLT2i)")
    elif ckd_dx:
        st.error("Maladie Rénale (Priorité SGLT2i + GLP-1/FLOW)")
    elif ascvd:
        st.warning("ASCVD (Priorité GLP-1/SGLT2i)")
    elif masld:
        st.info("Foie/MASLD (Priorité GLP-1/Pioglitazone)")
    else:
        st.success("Pas de comorbidité majeure déclarée")

    if bmi > 30:
        st.info("ℹ️ Obésité : Gestion du poids prioritaire (Tirzépatide).")

st.divider()
st.markdown("### 📚 Nouveautés ADA 2024-2025 intégrées")
with st.expander("Voir les détails des mises à jour"):
    st.markdown("""
    1.  **Rein (Étude FLOW) :** Le Sémaglutide a démontré une protection rénale majeure. Il est désormais recommandé en association avec les SGLT2i pour la MRC.
    2.  **Gestion du Poids :** Le poids est un objectif co-primaire. Le Tirzépatide (GIP/GLP-1) est mis en avant pour sa puissance supérieure.
    3.  **Foie (MASLD) :** Dépistage recommandé (FIB-4). Traitement par GLP-1 RA ou Pioglitazone si risque de fibrose.
    4.  **SGLT2i et eGFR :** Initiation possible jusqu'à eGFR 20, poursuite jusqu'à la dialyse.
    """)

# ==========================================
# 5. GÉNÉRATEUR DE PRÉSENTATION DE CAS (2025)
# ==========================================
st.divider()
st.subheader("🗣️ Demande d'avis spécialisé")

if st.button("Générer la lettre"):
    
    comorbs_pos = []
    if ascvd: comorbs_pos.append("ASCVD")
    if hf: comorbs_pos.append("Insuffisance Cardiaque")
    if ckd_dx: comorbs_pos.append(f"MRC (eGFR {egfr})")
    if masld: comorbs_pos.append("Risque hépatique (MASLD)")
    
    meds_str = f"sous {', '.join(current_meds)}" if current_meds else "naïf de traitement"
    recos = [item['text'] for item in plan_actions if item['type'] in ['START', 'STOP', 'SWITCH']]
    
    proposition = f"Je propose : {'; '.join(recos)}." if recos else "Je sollicite votre expertise."

    texte_presentation = f"""
"Cher Confrère, avis sur patient de {age} ans, IMC {bmi:.1f}.

Contexte Cardio-Rénal-Métabolique :
- {', '.join(comorbs_pos) if comorbs_pos else 'Pas de comorbidité majeure'}.
- HbA1c {hba1c}% (eGFR {egfr}).

Actuellement {meds_str}.

Conformément aux standards ADA 2025 (FLOW/Poids/MASLD), {proposition}
Merci."
    """
    st.info("💡 Copiez ce texte :")
    st.code(texte_presentation, language="text")
