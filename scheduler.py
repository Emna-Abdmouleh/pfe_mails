import time
import schedule
from datetime import datetime
from mail.connector import connect_imap, disconnect_imap, ensure_connected
from mail.fetcher   import fetch_emails
from config.logger  import logger

# ══════════════════════════════════════════════════════
# CONFIGURATION — modifie selon tes besoins
# ══════════════════════════════════════════════════════
INTERVAL_MINUTES = 1
FORCE_ALL = False

# ── Reconnexion automatique ───────────────────────────
MAX_RETRIES    = 3      # Nombre de tentatives max
RETRY_DELAY    = 5      # Secondes entre chaque tentative
# ══════════════════════════════════════════════════════


def connect_with_retry() -> object | None:
    """
    Tente de se connecter jusqu'à MAX_RETRIES fois.
    Retourne l'objet mail si succès, None si échec total.
    """
    for attempt in range(1, MAX_RETRIES + 1):
        try:
            logger.info(f"Tentative de connexion {attempt}/{MAX_RETRIES}...")
            mail = connect_imap()
            mail = ensure_connected(mail)
            logger.info("Connexion établie avec succès")
            return mail

        except Exception as e:
            logger.warning(f"Échec tentative {attempt}/{MAX_RETRIES} : {e}")

            if attempt < MAX_RETRIES:
                logger.info(f"Nouvelle tentative dans {RETRY_DELAY}s...")
                time.sleep(RETRY_DELAY)
            else:
                logger.error("Nombre maximum de tentatives atteint — abandon")
                return None


def check_emails():
    logger.info("=" * 40)
    logger.info("Début vérification des emails")
    logger.info("=" * 40)

    mail = None

    try:
        # ── Connexion avec retry ──────────────────────
        mail = connect_with_retry()

        if mail is None:
            logger.error(
                "Impossible de se connecter après "
                f"{MAX_RETRIES} tentatives — cycle ignoré"
            )
            return

        # ── Choix du filtre ───────────────────────────
        filtre = "ALL" if FORCE_ALL else "UNSEEN"

        if FORCE_ALL:
            logger.warning(
                "Mode FORCE activé — récupération "
                "de TOUS les emails"
            )

        # ── Récupération ──────────────────────────────
        email_ids = fetch_emails(mail, folder="INBOX", filter=filtre)

        # ── Traitement ────────────────────────────────
        if len(email_ids) > 0:
            logger.info(f"{len(email_ids)} email(s) à traiter")
            for eid in email_ids:
                logger.info(f"Email ID {eid.decode()} traité")
        else:
            logger.info(
                "Aucun nouveau email — "
                "en attente du prochain cycle"
            )

    except Exception as e:
        logger.error(f"Erreur durant la vérification : {e}")

    finally:
        if mail:
            disconnect_imap(mail)

    logger.info(f"Prochaine vérification dans {INTERVAL_MINUTES} minute(s)")


def start_scheduler():
    logger.info("Scheduler PFE démarré")
    logger.info(f"Intervalle      : {INTERVAL_MINUTES} minute(s)")
    logger.info(f"Reconnexion     : {MAX_RETRIES} tentatives / {RETRY_DELAY}s d'intervalle")
    logger.info(f"Mode            : {'FORCE (tous)' if FORCE_ALL else 'Nouveaux seulement'}")
    logger.info("Appuie sur Ctrl+C pour arrêter")

    check_emails()

    schedule.every(INTERVAL_MINUTES).minutes.do(check_emails)

    while True:
        schedule.run_pending()
        time.sleep(30)


if __name__ == "__main__":
    try:
        start_scheduler()
    except KeyboardInterrupt:
        logger.info("Scheduler arrêté par l'utilisateur")
        print("\n[✓] À bientôt ! 👋")