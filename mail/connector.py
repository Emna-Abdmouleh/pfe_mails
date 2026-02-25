import imaplib
from config.settings import EMAIL_ADDRESS, EMAIL_PASSWORD, IMAP_SERVER, IMAP_PORT

def connect_imap():
    try:
        mail = imaplib.IMAP4_SSL(IMAP_SERVER, IMAP_PORT)
        mail.login(EMAIL_ADDRESS, EMAIL_PASSWORD)
        print(f"Connecté : {EMAIL_ADDRESS}")
        return mail
    except imaplib.IMAP4.error as e:
        print(f"Erreur : {e}")
        raise

def disconnect_imap(mail):
    mail.logout()
    print("Déconnecté")