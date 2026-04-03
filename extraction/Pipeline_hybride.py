"""
pipeline_hybride.py
-------------------
Pipeline d'extraction CV avec rollback en cascade :
    1. Mistral       (online, priorité 1)
    2. Groq          (online, priorité 2)
    3. SpaCy + Regex (offline, priorité 3)

Usage :
    python pipeline_hybride.py                   # dossier par défaut
    python pipeline_hybride.py fichier.pdf       # un seul fichier
    python pipeline_hybride.py dossier/          # dossier custom
    python pipeline_hybride.py --offline         # force SpaCy (tests hors ligne)
"""

import os
import sys
import json
import glob
from pathlib import Path
from dotenv import load_dotenv

load_dotenv(r"C:\Users\user\pfe_mails\.env")

from Verifier_apis    import mistral_disponible, groq_disponible
from extraire_mistral import extraire_cv_mistral
from extraire    import extraire_cv
from extraire_spacy_r import extraire_cv_spacy

try:
    from lire_cv import lire_cv
except ImportError:
    import pdfplumber
    def lire_cv(chemin):
        chemin = Path(chemin)
        if chemin.suffix.lower() == ".pdf":
            texte = ""
            with pdfplumber.open(chemin) as pdf:
                for page in pdf.pages:
                    t = page.extract_text()
                    if t:
                        texte += t + "\n"
            return texte
        return chemin.read_text(encoding="utf-8", errors="ignore")


# =============================================================================
# VÉRIFICATION DES APIS — faite UNE SEULE FOIS au démarrage
# =============================================================================

def verifier_services():
    print("\n[INFO] Vérification des services disponibles...")
    mistral_ok = mistral_disponible()
    groq_ok    = groq_disponible()
    print(f"  Mistral : {'✓ disponible' if mistral_ok else '✗ indisponible'}")
    print(f"  Groq    : {'✓ disponible' if groq_ok    else '✗ indisponible'}")
    print(f"  SpaCy   : ✓ disponible (offline, toujours actif)\n")
    return mistral_ok, groq_ok


# =============================================================================
# PIPELINE HYBRIDE — rollback en cascade
# =============================================================================

def extraire_cv_pipeline(
    chemin_cv: str,
    mistral_ok: bool = True,
    groq_ok: bool = True,
    forcer_offline: bool = False,
) -> dict:
    """
    Cascade stricte : Mistral → Groq → SpaCy
    Les LLMs sont toujours tentés si disponibles,
    même si le texte est vide (PDF scanné).
    """
    nom_fichier = os.path.basename(chemin_cv)
    tentatives  = []

    # Lecture du texte — peut être vide si PDF scanné
    texte = ""
    try:
        texte = lire_cv(chemin_cv)
    except Exception as e:
        print(f"  [WARN] lire_cv échoué : {e}")

    if not texte.strip():
        print(f"  [WARN] Texte vide — PDF probablement scanné (image)")
        # Pour les PDFs scannés, on envoie un placeholder aux LLMs
        # afin qu'ils retournent un JSON vide structuré plutôt que de planter
        texte = "[PDF scanné — aucun texte extractible. Retourne le JSON avec des champs vides.]"

    # ── Étape 1 : Mistral ─────────────────────────────────────────────────────
    if not forcer_offline and mistral_ok:
        print(f"  [1/3] Tentative Mistral...")
        resultat = extraire_cv_mistral(texte, nom_fichier)
        tentatives.append({"methode": "mistral", "succes": resultat.get("succes", False)})
        if resultat.get("succes"):
            resultat["methode_utilisee"] = "mistral"
            resultat["tentatives"]       = tentatives
            print(f"  ✓ Mistral OK ({resultat.get('temps_reponse_sec', '?')}s)")
            return resultat
        print(f"  ✗ Mistral KO : {resultat.get('erreur')}")
    elif not forcer_offline and not mistral_ok:
        tentatives.append({"methode": "mistral", "succes": False, "raison": "indisponible"})
        print(f"  [1/3] Mistral ignoré (indisponible)")

    # ── Étape 2 : Groq ────────────────────────────────────────────────────────
    if not forcer_offline and groq_ok:
        print(f"  [2/3] Tentative Groq...")
        resultat = extraire_cv(texte, nom_fichier)
        tentatives.append({"methode": "groq", "succes": resultat.get("succes", False)})
        if resultat.get("succes"):
            resultat["methode_utilisee"] = "groq"
            resultat["tentatives"]       = tentatives
            print(f"  ✓ Groq OK ({resultat.get('temps_reponse_sec', '?')}s)")
            return resultat
        print(f"  ✗ Groq KO : {resultat.get('erreur')}")
    elif not forcer_offline and not groq_ok:
        tentatives.append({"methode": "groq", "succes": False, "raison": "indisponible"})
        print(f"  [2/3] Groq ignoré (indisponible)")

    # ── Étape 3 : SpaCy/Regex offline ─────────────────────────────────────────
    print(f"  [3/3] Fallback SpaCy/Regex offline...")
    resultat = extraire_cv_spacy(chemin_cv)
    tentatives.append({"methode": "spacy", "succes": resultat.get("succes", False)})
    resultat["methode_utilisee"] = "spacy_offline"
    resultat["tentatives"]       = tentatives
    statut = "✓" if resultat.get("succes") else "✗"
    print(f"  {statut} SpaCy ({resultat.get('temps_reponse_sec', '?')}s)")
    return resultat


# =============================================================================
# TRAITEMENT EN LOT + MÉTRIQUES
# =============================================================================

def traiter_dossier(
    dossier_cv: str,
    dossier_sortie: str,
    forcer_offline: bool = False,
) -> dict:
    os.makedirs(dossier_sortie, exist_ok=True)

    chemins = (
        glob.glob(os.path.join(dossier_cv, "*.pdf")) +
        glob.glob(os.path.join(dossier_cv, "*.txt"))
    )

    if not chemins:
        print(f"[ERREUR] Aucun CV trouvé dans : {dossier_cv}")
        return {}

    if forcer_offline:
        mistral_ok, groq_ok = False, False
        print("\n[INFO] Mode offline forcé — SpaCy uniquement\n")
    else:
        mistral_ok, groq_ok = verifier_services()

    print(f"[INFO] {len(chemins)} CV(s) trouvé(s)\n" + "=" * 55)

    tous_les_resultats = []
    compteurs          = {"mistral": 0, "groq": 0, "spacy_offline": 0, "echec": 0}
    temps_par_methode  = {"mistral": [], "groq": [], "spacy_offline": []}
    nb_succes          = 0
    nb_erreurs         = 0

    for chemin in chemins:
        nom = os.path.basename(chemin)
        print(f"\n[CV] {nom}")
        resultat = extraire_cv_pipeline(
            chemin,
            mistral_ok=mistral_ok,
            groq_ok=groq_ok,
            forcer_offline=forcer_offline,
        )

        methode = resultat.get("methode_utilisee", "echec")
        compteurs[methode] = compteurs.get(methode, 0) + 1

        if resultat.get("succes"):
            nb_succes += 1
            t = resultat.get("temps_reponse_sec", 0)
            if methode in temps_par_methode:
                temps_par_methode[methode].append(t)
        else:
            nb_erreurs += 1

        nom_json = os.path.splitext(nom)[0] + ".json"
        with open(os.path.join(dossier_sortie, nom_json), "w", encoding="utf-8") as f:
            json.dump(resultat, f, ensure_ascii=False, indent=2)

        tous_les_resultats.append(resultat)

    nb_total    = nb_succes + nb_erreurs
    taux_succes = round(nb_succes / nb_total * 100, 1) if nb_total > 0 else 0

    def stats(lst):
        if not lst:
            return {"moyen": 0, "min": 0, "max": 0}
        return {
            "moyen": round(sum(lst) / len(lst), 2),
            "min":   round(min(lst), 2),
            "max":   round(max(lst), 2),
        }

    metriques = {
        "methode":              "pipeline_hybride_cascade",
        "services_detectes":    {"mistral": mistral_ok, "groq": groq_ok, "spacy": True},
        "nb_cvs_traites":       nb_total,
        "nb_succes":            nb_succes,
        "nb_erreurs":           nb_erreurs,
        "taux_succes_pct":      taux_succes,
        "repartition_methodes": compteurs,
        "temps_par_methode":    {m: stats(t) for m, t in temps_par_methode.items()},
    }

    print("\n" + "=" * 55)
    print("        MÉTRIQUES PIPELINE HYBRIDE")
    print("=" * 55)
    print(f"  Services  : Mistral={'OK' if mistral_ok else 'KO'}  Groq={'OK' if groq_ok else 'KO'}  SpaCy=OK")
    print(f"  CVs traités : {nb_total}  |  Succès : {nb_succes} ({taux_succes}%)  |  Erreurs : {nb_erreurs}")
    print(f"\n  Répartition :")
    for m, c in compteurs.items():
        if c > 0:
            pct = round(c / nb_total * 100, 1)
            print(f"    {m:<20} : {c} CVs ({pct}%)")
    print("=" * 55)

    with open(os.path.join(dossier_sortie, "_tous_les_resultats_pipeline.json"), "w", encoding="utf-8") as f:
        json.dump({"metriques": metriques, "resultats": tous_les_resultats}, f, ensure_ascii=False, indent=2)
    with open(os.path.join(dossier_sortie, "_metriques_pipeline.json"), "w", encoding="utf-8") as f:
        json.dump(metriques, f, ensure_ascii=False, indent=2)

    print(f"\n✅ Résultats sauvegardés dans : {dossier_sortie}")
    return metriques


# =============================================================================
# POINT D'ENTRÉE
# =============================================================================

if __name__ == "__main__":
    DOSSIER_CV     = r"C:\Users\user\pfe_mails\cv_attachments\attachments"
    DOSSIER_SORTIE = r"C:\Users\user\pfe_mails\resultats\pipeline_hybride"
    FORCER_OFFLINE = "--offline" in sys.argv

    args_fichiers = [a for a in sys.argv[1:] if not a.startswith("--")]

    if args_fichiers:
        arg = args_fichiers[0]
        if os.path.isfile(arg):
            mistral_ok, groq_ok = (False, False) if FORCER_OFFLINE else verifier_services()
            print(f"\n[INFO] Fichier unique : {arg}")
            res = extraire_cv_pipeline(arg, mistral_ok=mistral_ok, groq_ok=groq_ok, forcer_offline=FORCER_OFFLINE)
            print(json.dumps(res, ensure_ascii=False, indent=2))
        elif os.path.isdir(arg):
            traiter_dossier(arg, DOSSIER_SORTIE, forcer_offline=FORCER_OFFLINE)
        else:
            print(f"[ERREUR] Introuvable : {arg}")
    else:
        traiter_dossier(DOSSIER_CV, DOSSIER_SORTIE, forcer_offline=FORCER_OFFLINE)