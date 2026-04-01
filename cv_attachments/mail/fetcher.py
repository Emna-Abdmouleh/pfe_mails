from email.header import decode_header
from config.logger import logger

def decode_mime_words(s):
    """
    Décode les sujets encodés en Base64.
    Ex: =?utf-8?B?Qm9uam91cg==?= → 'Bonjour'
    """
    decoded = decode_header(s)
    return ''.join(
        part.decode(enc or 'utf-8') if isinstance(part, bytes) else part
        for part, enc in decoded
    )
def fetch_emails(mail, folder="INBOX", filter="UNSEEN"):
    """
    Récupère les emails selon le filtre :
    UNSEEN = nouveaux emails seulement (par défaut)
    ALL    = tous les emails (mode force)
    """
    try:
        mail.select(folder)
        status, messages = mail.search(None, filter)

        if status != "OK":
            logger.error(f"Échec recherche emails dans {folder}")
            return []

        email_ids = messages[0].split()

        if len(email_ids) == 0:
            logger.info("Aucun nouveau email trouvé")
        else:
            logger.info(
                f"{len(email_ids)} nouveau(x) email(s) "
                f"trouvé(s) dans {folder}"
            )
        return email_ids

    except Exception as e:
        logger.error(f"Erreur récupération emails : {e}")
        return []