"""
pipeline_auto.py
----------------
Pipeline automatique complet :
    1. Récupère les nouveaux emails Gmail (scheduler)
    2. Extrait les CVs en pièces jointes
    3. Lance le pipeline d'extraction (Mistral → Groq → SpaCy)
    4. Injecte les résultats dans Elasticsearch
    5. La notification est envoyée automatiquement par notifications.py (polling ES)

Usage :
    python pipeline_auto.py          # lance en continu
    python pipeline_auto.py --once   # un seul cycle (test)
"""

import os
import sys
import time
import json
import glob
import schedule
import threading
from pathlib import Path
from datetime import datetime
from dotenv import load_dotenv

load_dotenv(r"C:\Users\user\pfe_mails\.env")

# ── Imports pipeline existants ─────────────────────────────────────
from mail.connector       import connect_imap, disconnect_imap, ensure_connected
from mail.fetcher         import fetch_emails
from mail.parser          import parse_email
from pipeline_hybride     import extraire_cv_pipeline, verifier_services
from injecter_elasticsearch import connecter, creer_index, injecter
from nettoyer_json        import nettoyer_dossier
from config.logger        import logger

# ══════════════════════════════════════════════════════════════════
# CONFIGURATION
# ══════════════════════════════════════════════════════════════════
INTERVAL_MINUTES   = 1      # Fréquence vérification emails
DOSSIER_PIECES     = r"C:\Users\user\pfe_mails\cv_attachments\attachments"
DOSSIER_RESULTATS  = r"C:\Users\user\pfe_mails\resultats\pipeline_hybride"
DOSSIER_PROPRE     = r"C:\Users\user\pfe_mails\resultats\json_propres"
INDEX_CVS          = "cvs"
MAX_RETRIES        = 3
RETRY_DELAY        = 5

# Extensions CV acceptées
CV_EXTENSIONS = {".pdf", ".doc", ".docx", ".txt"}

# ── Verif APIs une seule fois au démarrage ─────────────────────────
_mistral_ok = False
_groq_ok    = False
_es_client  = None
_lock       = threading.Lock()


def init_services():
    """Initialise les services au démarrage."""
    global _mistral_ok, _groq_ok, _es_client

    logger.info("=" * 50)
    logger.info("   PIPELINE AUTO — DÉMARRAGE")
    logger.info("=" * 50)

    # Vérif APIs LLM
    _mistral_ok, _groq_ok = verifier_services()

    # Connexion ES
    try:
        _es_client = connecter()
        creer_index(_es_client)
        logger.info("✓ Elasticsearch connecté")
    except Exception as e:
        logger.error(f"✗ Elasticsearch non disponible : {e}")
        _es_client = None

    logger.info("=" * 50)


# ══════════════════════════════════════════════════════════════════
# ÉTAPE 1 : Récupération emails
# ══════════════════════════════════════════════════════════════════
def recuperer_emails() -> list:
    """Récupère les nouveaux CVs depuis Gmail. Retourne la liste des fichiers récupérés."""
    nouveaux_fichiers = []

    # Snapshot des fichiers existants avant
    existants = set(glob.glob(os.path.join(DOSSIER_PIECES, "*.*")))

    mail = None
    try:
        # Connexion avec retry
        for i in range(1, MAX_RETRIES + 1):
            try:
                mail = connect_imap()
                mail = ensure_connected(mail)
                break
            except Exception as e:
                logger.warning(f"Connexion IMAP tentative {i}/{MAX_RETRIES} : {e}")
                if i < MAX_RETRIES:
                    time.sleep(RETRY_DELAY)
                else:
                    logger.error("Connexion IMAP impossible")
                    return []

        email_ids = fetch_emails(mail, folder="INBOX", filter="UNSEEN")

        if not email_ids:
            logger.info("Aucun nouvel email")
            return []

        logger.info(f"{len(email_ids)} nouvel(s) email(s) trouvé(s)")

        for eid in email_ids:
            result = parse_email(mail, eid)
            if result:
                logger.info(f"  Email traité : {len(result['fichiers'])} pièce(s) jointe(s)")

    except Exception as e:
        logger.error(f"Erreur récupération emails : {e}")
    finally:
        if mail:
            disconnect_imap(mail)

    # Nouveaux fichiers = différence
    apres = set(glob.glob(os.path.join(DOSSIER_PIECES, "*.*")))
    nouveaux_fichiers = [
        f for f in (apres - existants)
        if Path(f).suffix.lower() in CV_EXTENSIONS
    ]

    if nouveaux_fichiers:
        logger.info(f"  {len(nouveaux_fichiers)} nouveau(x) CV(s) téléchargé(s)")
        for f in nouveaux_fichiers:
            logger.info(f"    → {os.path.basename(f)}")

    return nouveaux_fichiers


# ══════════════════════════════════════════════════════════════════
# ÉTAPE 2 : Extraction CV
# ══════════════════════════════════════════════════════════════════
def extraire_cvs(fichiers: list) -> list:
    """Extrait les données des CVs. Retourne les chemins JSON générés."""
    if not fichiers:
        return []

    os.makedirs(DOSSIER_RESULTATS, exist_ok=True)
    json_generes = []

    for chemin in fichiers:
        nom = os.path.basename(chemin)
        logger.info(f"  Extraction : {nom}")

        try:
            resultat = extraire_cv_pipeline(
                chemin,
                mistral_ok=_mistral_ok,
                groq_ok=_groq_ok,
            )

            nom_json = os.path.splitext(nom)[0] + ".json"
            chemin_json = os.path.join(DOSSIER_RESULTATS, nom_json)

            with open(chemin_json, "w", encoding="utf-8") as f:
                json.dump(resultat, f, ensure_ascii=False, indent=2)

            if resultat.get("succes"):
                logger.info(f"  ✓ Extrait via {resultat.get('methode_utilisee', '?')}")
                json_generes.append(chemin_json)
            else:
                logger.warning(f"  ✗ Extraction échouée pour {nom}")

        except Exception as e:
            logger.error(f"  Erreur extraction {nom} : {e}")

    return json_generes


# ══════════════════════════════════════════════════════════════════
# ÉTAPE 3 : Injection Elasticsearch
# ══════════════════════════════════════════════════════════════════
def injecter_dans_es(json_files: list) -> int:
    """Injecte les JSONs dans ES. Retourne le nombre de docs injectés."""
    if not json_files or _es_client is None:
        return 0

    try:
        # Nettoyer et charger uniquement les nouveaux JSONs
        docs = nettoyer_dossier(DOSSIER_RESULTATS, DOSSIER_PROPRE)

        # Filtrer uniquement les docs correspondant aux nouveaux fichiers
        noms_nouveaux = {
            os.path.splitext(os.path.basename(f))[0]
            for f in json_files
        }
        docs_nouveaux = [
            d for d in docs
            if os.path.splitext(
                os.path.basename(d.get("cv_filename", ""))
            )[0] in noms_nouveaux
            or any(n in d.get("cv_filename", "") for n in noms_nouveaux)
        ]

        if not docs_nouveaux:
            # Si le filtre ne marche pas, injecter tous les docs nettoyés
            docs_nouveaux = docs

        nb_succes, nb_erreurs = injecter(_es_client, docs_nouveaux)
        _es_client.indices.refresh(index=INDEX_CVS)

        if nb_succes > 0:
            logger.info(f"  ✓ {nb_succes} document(s) injecté(s) dans ES")
        if nb_erreurs > 0:
            logger.warning(f"  ✗ {nb_erreurs} erreur(s) d'injection")

        return nb_succes

    except Exception as e:
        logger.error(f"Erreur injection ES : {e}")
        return 0


# ══════════════════════════════════════════════════════════════════
# CYCLE COMPLET
# ══════════════════════════════════════════════════════════════════
def cycle_complet():
    """Un cycle complet : email → extraction → injection → notification auto."""
    with _lock:
        now = datetime.now().strftime("%d/%m/%Y %H:%M:%S")
        logger.info(f"\n{'='*50}")
        logger.info(f"  CYCLE — {now}")
        logger.info(f"{'='*50}")

        # 1. Récupérer emails
        logger.info("[1/3] Récupération des emails...")
        nouveaux_cvs = recuperer_emails()

        if not nouveaux_cvs:
            logger.info("  → Aucun nouveau CV — fin du cycle\n")
            return

        # 2. Extraire les CVs
        logger.info(f"[2/3] Extraction de {len(nouveaux_cvs)} CV(s)...")
        json_files = extraire_cvs(nouveaux_cvs)

        if not json_files:
            logger.warning("  → Aucune extraction réussie — fin du cycle\n")
            return

        # 3. Injecter dans ES
        logger.info(f"[3/3] Injection dans Elasticsearch...")
        nb = injecter_dans_es(json_files)

        # La notification est automatique via le polling de notifications.py
        # (détecte les nouveaux _id dans ES toutes les 30s)
        logger.info(f"\n✅ Cycle terminé : {nb} CV(s) injecté(s)")
        logger.info(f"   → Notification automatique dans ≤30s via l'app web\n")


# ══════════════════════════════════════════════════════════════════
# POINT D'ENTRÉE
# ══════════════════════════════════════════════════════════════════
if __name__ == "__main__":
    ONCE = "--once" in sys.argv

    # Initialisation des services
    init_services()

    if ONCE:
        logger.info("[MODE] Cycle unique (--once)")
        cycle_complet()
        logger.info("Terminé.")
    else:
        logger.info(f"[MODE] Continu — vérification toutes les {INTERVAL_MINUTES} min")
        logger.info("Ctrl+C pour arrêter\n")

        # Premier cycle immédiat
        cycle_complet()

        # Planification des cycles suivants
        schedule.every(INTERVAL_MINUTES).minutes.do(cycle_complet)

        try:
            while True:
                schedule.run_pending()
                time.sleep(30)
        except KeyboardInterrupt:
            logger.info("\nPipeline arrêté par l'utilisateur.")