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
# Toutes les combien de minutes on vérifie
# 1 = chaque minute / 5 = toutes les 5 min

FORCE_ALL = False
# False = nouveaux emails seulement (UNSEEN)
# True  = récupère TOUS les emails
# ══════════════════════════════════════════════════════


def check_emails():
    logger.info("=" * 40)
    logger.info("Début vérification des emails")
    logger.info("=" * 40)

    mail = None

    try:
        # ── Connexion ─────────────────────────────────
        mail = connect_imap()
        mail = ensure_connected(mail)

        # ── Choix du filtre ───────────────────────────
        filtre = "ALL" if FORCE_ALL else "UNSEEN"

        if FORCE_ALL:
            logger.warning(
                "Mode FORCE activé — récupération "
                "de TOUS les emails"
            )

        # ── Récupération ──────────────────────────────
        email_ids = fetch_emails(
            mail,
            folder="INBOX",
            filter=filtre
        )

        # ── Traitement ────────────────────────────────
        if len(email_ids) > 0:
            logger.info(f"{len(email_ids)} email(s) à traiter")
            for eid in email_ids:
                logger.info(
                    f"Email ID {eid.decode()} traité"
                )
        else:
            logger.info(
                "Aucun nouveau email — "
                "en attente du prochain cycle"
            )

    except Exception as e:
        logger.error(f"Erreur durant la vérification : {e}")

    finally:
        # finally = s'exécute TOUJOURS même si erreur
        # → on s'assure de toujours fermer la connexion
        if mail:
            disconnect_imap(mail)

    logger.info(
        f"Prochaine vérification "
        f"dans {INTERVAL_MINUTES} minute(s)"
    )


def start_scheduler():
    logger.info("Scheduler PFE démarré")
    logger.info(f"Intervalle : {INTERVAL_MINUTES} minute(s)")
    logger.info(
        f"Mode : "
        f"{'FORCE (tous)' if FORCE_ALL else 'Nouveaux seulement'}"
    )
    logger.info("Appuie sur Ctrl+C pour arrêter")

    # Vérification immédiate au démarrage
    # Sans ça tu attendrais 1 minute avant la 1ère vérif
    check_emails()

    # Planification des vérifications suivantes
    schedule.every(INTERVAL_MINUTES).minutes.do(check_emails)

    # Boucle infinie
    while True:
        schedule.run_pending()
        # Vérifie si une tâche doit être exécutée
        time.sleep(30)
        # Attend 30 sec avant de revérifier
        # 30 sec = bon équilibre réactivité / CPU


if __name__ == "__main__":
    try:
        start_scheduler()
    except KeyboardInterrupt:
        logger.info("Scheduler arrêté par l'utilisateur")
        print("\n[✓] À bientôt ! 👋")