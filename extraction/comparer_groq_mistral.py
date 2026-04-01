import json
import os
import time
import csv
from difflib import SequenceMatcher

# ============================================================
# CHEMINS
# ============================================================
GROQ_JSON    = r"C:\Users\user\pfe_mails\resultats\groq\_tous_les_resultats_groq.json"
MISTRAL_JSON = r"C:\Users\user\pfe_mails\resultats\mistral\_tous_les_resultats_mistral.json"
SORTIE_CSV   = r"C:\Users\user\pfe_mails\resultats\comparaison_groq_mistral.csv"
SORTIE_JSON  = r"C:\Users\user\pfe_mails\resultats\comparaison_groq_mistral.json"

# ============================================================
# UTILITAIRES
# ============================================================

def similarite(a, b):
    """Similarité textuelle entre deux chaînes (0.0 à 1.0)"""
    if not a and not b:
        return 1.0
    if not a or not b:
        return 0.0
    return SequenceMatcher(None, str(a).lower().strip(), str(b).lower().strip()).ratio()

def champ_rempli(valeur):
    """Vérifie si un champ est non vide"""
    if isinstance(valeur, list):
        return len(valeur) > 0
    if isinstance(valeur, dict):
        return any(v for v in valeur.values())
    return bool(str(valeur).strip())

def compter_elements(valeur):
    """Compte le nombre d'éléments extraits"""
    if isinstance(valeur, list):
        return len(valeur)
    if isinstance(valeur, str) and valeur.strip():
        return 1
    return 0

# ============================================================
# COMPARAISON PAR CV
# ============================================================

def comparer_cv(groq_cv, mistral_cv):
    resultats = {
        "cv": groq_cv.get("cv_filename", ""),
        "champs": {}
    }

    # --- Informations personnelles ---
    for champ in ["nom", "email", "telephone", "ville"]:
        g = groq_cv.get("informations_personnelles", {}).get(champ, "")
        m = mistral_cv.get("informations_personnelles", {}).get(champ, "")
        resultats["champs"][champ] = {
            "groq": g,
            "mistral": m,
            "groq_rempli": champ_rempli(g),
            "mistral_rempli": champ_rempli(m),
            "similarite": round(similarite(g, m), 2)
        }

    # --- Champs listes (nb éléments extraits) ---
    for champ in ["formation", "experiences", "competences_techniques", "projets", "langues"]:
        g = groq_cv.get(champ, [])
        m = mistral_cv.get(champ, [])
        resultats["champs"][champ] = {
            "groq_nb": compter_elements(g),
            "mistral_nb": compter_elements(m),
            "groq_rempli": champ_rempli(g),
            "mistral_rempli": champ_rempli(m),
        }

    # --- Champs bonus (présents dans Mistral mais pas Groq) ---
    certificats_m = mistral_cv.get("certificats", [])
    exp_asso_m    = mistral_cv.get("experiences_associatives", [])
    resultats["champs"]["certificats"] = {
        "groq_nb": 0,
        "mistral_nb": compter_elements(certificats_m),
        "note": "Mistral extrait ce champ, Groq non"
    }
    resultats["champs"]["experiences_associatives"] = {
        "groq_nb": 0,
        "mistral_nb": compter_elements(exp_asso_m),
        "note": "Mistral extrait ce champ, Groq non"
    }

    return resultats

# ============================================================
# SCORE GLOBAL PAR METHODE
# ============================================================

def calculer_scores(comparaisons):
    scores = {"groq": 0, "mistral": 0, "total": 0}
    champs_simples = ["nom", "email", "telephone", "ville"]
    champs_listes  = ["formation", "experiences", "competences_techniques", "projets", "langues"]

    for comp in comparaisons:
        for champ in champs_simples:
            if comp["champs"][champ]["groq_rempli"]:
                scores["groq"] += 1
            if comp["champs"][champ]["mistral_rempli"]:
                scores["mistral"] += 1
            scores["total"] += 1

        for champ in champs_listes:
            if comp["champs"][champ]["groq_rempli"]:
                scores["groq"] += 1
            if comp["champs"][champ]["mistral_rempli"]:
                scores["mistral"] += 1
            scores["total"] += 1

    return scores

# ============================================================
# EXPORT CSV
# ============================================================

def exporter_csv(comparaisons, chemin):
    champs_simples = ["nom", "email", "telephone", "ville"]
    champs_listes  = ["formation", "experiences", "competences_techniques", "projets", "langues"]

    with open(chemin, "w", newline="", encoding="utf-8-sig") as f:
        writer = csv.writer(f, delimiter=";")

        # En-tête
        writer.writerow([
            "CV", "Champ",
            "Groq (valeur/nb)", "Mistral (valeur/nb)",
            "Groq rempli", "Mistral rempli",
            "Similarité", "Note"
        ])

        for comp in comparaisons:
            cv = comp["cv"]

            for champ in champs_simples:
                c = comp["champs"][champ]
                writer.writerow([
                    cv, champ,
                    c["groq"], c["mistral"],
                    "✅" if c["groq_rempli"] else "❌",
                    "✅" if c["mistral_rempli"] else "❌",
                    c["similarite"], ""
                ])

            for champ in champs_listes:
                c = comp["champs"][champ]
                writer.writerow([
                    cv, champ,
                    c["groq_nb"], c["mistral_nb"],
                    "✅" if c["groq_rempli"] else "❌",
                    "✅" if c["mistral_rempli"] else "❌",
                    "-", ""
                ])

            for champ in ["certificats", "experiences_associatives"]:
                c = comp["champs"][champ]
                writer.writerow([
                    cv, champ,
                    c["groq_nb"], c["mistral_nb"],
                    "❌", "✅" if c["mistral_nb"] > 0 else "❌",
                    "-", c.get("note", "")
                ])

            writer.writerow([])  # ligne vide entre CVs

# ============================================================
# MAIN
# ============================================================

if __name__ == "__main__":

    # Chargement
    with open(GROQ_JSON, "r", encoding="utf-8") as f:
        groq_data = json.load(f)
    with open(MISTRAL_JSON, "r", encoding="utf-8") as f:
        mistral_data = json.load(f)

    # Indexer par nom de fichier
    groq_index    = {cv["cv_filename"]: cv for cv in groq_data}
    mistral_index = {cv["cv_filename"]: cv for cv in mistral_data}

    # CVs communs
    cvs_communs = set(groq_index.keys()) & set(mistral_index.keys())
    print(f"\n📄 CVs comparés : {len(cvs_communs)}")

    # Comparaison
    comparaisons = []
    for cv_nom in sorted(cvs_communs):
        comp = comparer_cv(groq_index[cv_nom], mistral_index[cv_nom])
        comparaisons.append(comp)

    # Scores globaux
    scores = calculer_scores(comparaisons)
    taux_groq    = round(scores["groq"]    / scores["total"] * 100, 1)
    taux_mistral = round(scores["mistral"] / scores["total"] * 100, 1)

    # Affichage résumé
    print("\n" + "="*55)
    print("       COMPARAISON GROQ vs MISTRAL")
    print("="*55)
    print(f"  Groq    — champs remplis : {scores['groq']}/{scores['total']} ({taux_groq}%)")
    print(f"  Mistral — champs remplis : {scores['mistral']}/{scores['total']} ({taux_mistral}%)")
    print(f"\n  ✨ Mistral extrait en plus : certificats + expériences associatives")
    print("="*55)

    # Détail par CV
    for comp in comparaisons:
        print(f"\n📄 {comp['cv']}")
        print(f"  {'Champ':<30} {'Groq':>10} {'Mistral':>10} {'Similarité':>12}")
        print(f"  {'-'*62}")
        for champ, vals in comp["champs"].items():
            if "similarite" in vals:
                g = "✅" if vals["groq_rempli"] else "❌"
                m = "✅" if vals["mistral_rempli"] else "❌"
                print(f"  {champ:<30} {g:>10} {m:>10} {vals['similarite']:>12}")
            elif "groq_nb" in vals:
                g = str(vals["groq_nb"])
                m = str(vals["mistral_nb"])
                print(f"  {champ:<30} {g:>10} {m:>10} {'(nb items)':>12}")

    # Export
    os.makedirs(os.path.dirname(SORTIE_CSV), exist_ok=True)
    exporter_csv(comparaisons, SORTIE_CSV)

    with open(SORTIE_JSON, "w", encoding="utf-8") as f:
        json.dump({
            "scores": {
                "groq": {"remplis": scores["groq"], "total": scores["total"], "taux": taux_groq},
                "mistral": {"remplis": scores["mistral"], "total": scores["total"], "taux": taux_mistral}
            },
            "comparaisons": comparaisons
        }, f, ensure_ascii=False, indent=2)

    print(f"\n✅ CSV exporté  : {SORTIE_CSV}")
    print(f"✅ JSON exporté : {SORTIE_JSON}")