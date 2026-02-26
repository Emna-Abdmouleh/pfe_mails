import imaplib
from config.settings import EMAIL_ADDRESS, EMAIL_PASSWORD, IMAP_SERVER, IMAP_PORT
from config.logger import logger


def connect_imap():
    try:
        logger.info("Tentative de connexion IMAP...")
        mail = imaplib.IMAP4_SSL(IMAP_SERVER, IMAP_PORT)
        mail.login(EMAIL_ADDRESS, EMAIL_PASSWORD)
        logger.info(f"Connecté avec succès : {EMAIL_ADDRESS}")
        return mail

    except imaplib.IMAP4.error as e:
        logger.error(f"Échec connexion IMAP : {e}")
        raise
        # raise = on relance l'erreur pour que
        # le scheduler puisse la capturer

    except Exception as e:
        logger.critical(f"Erreur inattendue : {e}")
        raise


def is_connected(mail):
    try:
        status = mail.noop()
        # noop() = ping au serveur Gmail
        # si le serveur répond → connexion active
        return status[0] == 'OK'
    except Exception:
        logger.warning("Connexion perdue détectée")
        return False


def ensure_connected(mail):
    if not is_connected(mail):
        logger.warning("Reconnexion automatique en cours...")
        mail = connect_imap()
        logger.info("Reconnexion réussie !")
    return mail


def disconnect_imap(mail):
    try:
        mail.logout()
        logger.info("Déconnexion propre réussie")
    except Exception as e:
        logger.warning(f"Déconnexion forcée : {e}")