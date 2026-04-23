"""
pipeline_auto.py
----------------
Lance le pipeline complet automatiquement :
1. Récupère les nouveaux emails (PDFs)
2. Extrait les données des CVs
3. Injecte dans Elasticsearch (index: cvs)

Usage:
    python pipeline_auto.py          # traite les nouveaux CVs
    python pipeline_auto.py --all    # retraite tous les CVs
"""

import os
import sys
import time

# ── Chemins ────────────────────────────────────────────────────────────────
BASE_DIR        = r"C:\Users\user\pfe_mails"
ATTACHMENTS_DIR = os.path.join(BASE_DIR, "cv_attachments", "attachments")
RESULTATS_DIR   = os.path.join(BASE_DIR, "resultats", "pipeline_hybride")
TRAITES_FILE    = os.path.join(BASE_DIR, "cvs_traites.txt")

sys.path.insert(0, BASE_DIR)
sys.path.insert(0, os.path.join(BASE_DIR, "extraction"))
sys.path.insert(0, os.path.join(BASE_DIR, "cv_attachments"))

# ══════════════════════════════════════════════════════════════════════════════
# ÉTAPE 1 — Récupérer les nouveaux emails
# ══════════════════════════════════════════════════════════════════════════════
def step1_fetch_emails():
    print("\n[ÉTAPE 1] Récupération des nouveaux emails...")
    try:
        from mail.connector import connect_imap, disconnect_imap, ensure_connected
        from mail.fetcher import fetch_emails
        from mail.parser import parse_email

        mail = connect_imap()
        mail = ensure_connected(mail)
        email_ids = fetch_emails(mail, folder="INBOX", filter="UNSEEN")

        if not email_ids:
            print("  Aucun nouvel email.")
        else:
            print(f"  {len(email_ids)} email(s) trouvé(s)")
            for eid in email_ids:
                parse_email(mail, eid)

        disconnect_imap(mail)
        print("  ✅ Emails récupérés")
    except Exception as e:
        print(f"  ⚠️ Erreur emails : {e}")

# ══════════════════════════════════════════════════════════════════════════════
# ÉTAPE 2 — Extraire les CVs non encore traités
# ══════════════════════════════════════════════════════════════════════════════
def step2_extraire_cvs(force_all=False):
    print("\n[ÉTAPE 2] Extraction des CVs...")
    import glob

    os.makedirs(RESULTATS_DIR, exist_ok=True)

    # Charger la liste des CVs déjà traités
    traites = set()
    if os.path.exists(TRAITES_FILE) and not force_all:
        with open(TRAITES_FILE, "r") as f:
            traites = set(f.read().splitlines())

    # Trouver les nouveaux CVs
    tous = glob.glob(os.path.join(ATTACHMENTS_DIR, "*.pdf"))
    nouveaux = [c for c in tous if os.path.basename(c) not in traites]

    if not nouveaux:
        print("  Aucun nouveau CV à extraire.")
        return False

    print(f"  {len(nouveaux)} nouveau(x) CV(s) à traiter")

    try:
        from extraction.Pipeline_hybride import extraire_cv_pipeline, verifier_services
        import json

        mistral_ok, groq_ok = verifier_services()

        for chemin in nouveaux:
            nom = os.path.basename(chemin)
            print(f"\n  [CV] {nom}")
            resultat = extraire_cv_pipeline(chemin, mistral_ok=mistral_ok, groq_ok=groq_ok)

            nom_json = os.path.splitext(nom)[0] + ".json"
            with open(os.path.join(RESULTATS_DIR, nom_json), "w", encoding="utf-8") as f:
                json.dump(resultat, f, ensure_ascii=False, indent=2)

            # Marquer comme traité
            with open(TRAITES_FILE, "a") as f:
                f.write(nom + "\n")

        print("  ✅ Extraction terminée")
        return True
    except Exception as e:
        print(f"  ⚠️ Erreur extraction : {e}")
        return False

# ══════════════════════════════════════════════════════════════════════════════
# ÉTAPE 3 — Injecter dans Elasticsearch
# ══════════════════════════════════════════════════════════════════════════════
def step3_injecter():
    print("\n[ÉTAPE 3] Injection dans Elasticsearch...")
    try:
        sys.path.insert(0, os.path.join(BASE_DIR, "extraction"))
        from injecter_elasticsearch import pipeline_complet
        pipeline_complet(reset=False)
        print("  ✅ Injection terminée")
    except Exception as e:
        print(f"  ⚠️ Erreur injection : {e}")

# ══════════════════════════════════════════════════════════════════════════════
# PIPELINE COMPLET
# ══════════════════════════════════════════════════════════════════════════════
def run_pipeline(force_all=False):
    print("\n" + "=" * 55)
    print("   PIPELINE AUTO — DÉMARRAGE")
    print("=" * 55)
    debut = time.time()

    step1_fetch_emails()
    new_cvs = step2_extraire_cvs(force_all=force_all)
    if new_cvs or force_all:
        step3_injecter()
    else:
        print("\n[INFO] Aucun nouveau CV — injection ignorée")

    duree = round(time.time() - debut, 1)
    print(f"\n{'=' * 55}")
    print(f"   ✅ PIPELINE TERMINÉ en {duree}s")
    print(f"{'=' * 55}\n")

if __name__ == "__main__":
    force_all = "--all" in sys.argv
    run_pipeline(force_all=force_all)