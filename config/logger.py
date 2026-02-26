import logging
import os
from datetime import datetime

# ══════════════════════════════════════════════════════
# CONFIGURATION
# ══════════════════════════════════════════════════════

LOGS_DIR   = "logs"
LOG_FORMAT  = "%(asctime)s | %(levelname)-8s | %(message)s"
DATE_FORMAT = "%Y-%m-%d %H:%M:%S"

# ══════════════════════════════════════════════════════


def setup_logger():

    # ── Créer le dossier logs/ automatiquement ────────
    os.makedirs(LOGS_DIR, exist_ok=True)
    # Si le dossier existe déjà → pas d'erreur

    # ── Date du jour pour le nom des fichiers ─────────
    today = datetime.now().strftime("%Y-%m-%d")
    # Ex: "2025-02-20"
    # Chaque jour → un nouveau fichier de log

    # ── Créer le logger ───────────────────────────────
    logger = logging.getLogger("PFE_MAIL")
    logger.setLevel(logging.DEBUG)
    # Les niveaux du moins grave au plus grave :
    # DEBUG → INFO → WARNING → ERROR → CRITICAL

    # ── Fichier 1 : app.log — tout tracer ─────────────
    app_handler = logging.FileHandler(
        filename=f"{LOGS_DIR}/app_{today}.log",
        encoding="utf-8"
    )
    app_handler.setLevel(logging.DEBUG)
    app_handler.setFormatter(
        logging.Formatter(LOG_FORMAT, DATE_FORMAT)
    )

    # ── Fichier 2 : errors.log — erreurs seulement ────
    error_handler = logging.FileHandler(
        filename=f"{LOGS_DIR}/errors_{today}.log",
        encoding="utf-8"
    )
    error_handler.setLevel(logging.ERROR)
    # Reçoit uniquement ERROR et CRITICAL
    error_handler.setFormatter(
        logging.Formatter(LOG_FORMAT, DATE_FORMAT)
    )

    # ── Fichier 3 : connexions.log ────────────────────
    connexion_handler = logging.FileHandler(
        filename=f"{LOGS_DIR}/connexions_{today}.log",
        encoding="utf-8"
    )
    connexion_handler.setLevel(logging.INFO)
    connexion_handler.setFormatter(
        logging.Formatter(LOG_FORMAT, DATE_FORMAT)
    )

    # ── Terminal : afficher aussi dans la console ──────
    console_handler = logging.StreamHandler()
    console_handler.setLevel(logging.DEBUG)
    console_handler.setFormatter(
        logging.Formatter(LOG_FORMAT, DATE_FORMAT)
    )

    # ── Ajouter les handlers au logger ────────────────
    if not logger.handlers:
        # On vérifie avant d'ajouter pour éviter les doublons
        # si setup_logger() est appelé plusieurs fois
        logger.addHandler(app_handler)
        logger.addHandler(error_handler)
        logger.addHandler(connexion_handler)
        logger.addHandler(console_handler)

    return logger


# ── Instance globale ──────────────────────────────────
logger = setup_logger()
# On crée une seule instance ici
# Dans tous les autres fichiers on fait juste :
# from config.logger import logger


# Étape 2 — Mettre à jour `.gitignore`

