from mail.connector import connect_imap, disconnect_imap, ensure_connected
from mail.fetcher   import fetch_emails
from mail.parser    import parse_email
from config.logger  import logger

def recover():
    logger.info("RECUPERATION — tous les emails (ALL)")
    mail = None
    try:
        mail = connect_imap()
        mail = ensure_connected(mail)
        email_ids = fetch_emails(mail, folder="INBOX", filter="ALL")

        if not email_ids:
            logger.info("Aucun email trouvé.")
            return

        logger.info(f"{len(email_ids)} email(s) trouvé(s)")

        for idx, eid in enumerate(email_ids, start=1):
            eid_str = eid.decode() if isinstance(eid, bytes) else str(eid)
            logger.info(f"[{idx}/{len(email_ids)}] Email ID {eid_str}")
            parse_email(mail, eid)

    except Exception as e:
        logger.error(f"Erreur : {e}")
    finally:
        if mail:
            disconnect_imap(mail)

if __name__ == "__main__":
    recover()