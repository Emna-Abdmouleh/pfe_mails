import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "cv_attachments"))

from mail.connector import connect_imap, disconnect_imap, ensure_connected
from mail.fetcher import fetch_emails
from mail.parser import parse_email

def main():

    # ÉTAPE 1 : Connexion
    mail = connect_imap()

    # ÉTAPE 2 : Vérifier la connexion
    mail = ensure_connected(mail)

    # ÉTAPE 3 : Récupérer les emails
    email_ids = fetch_emails(mail, folder="INBOX", filter="ALL")
    print(f"\n[✓] {len(email_ids)} email(s) dans la boite mail")

    # ÉTAPE 4 : Parser chaque email et sauvegarder les CVs
    cvs_sauvegardes = 0
    for email_id in email_ids:
        email_data = parse_email(mail, email_id)
        if email_data and email_data.get("attachments"):
            cvs_sauvegardes += len(email_data["attachments"])

    print(f"\n[✓] {cvs_sauvegardes} CV(s) sauvegardé(s) dans attachments/")

    # ÉTAPE 5 : Déconnexion
    disconnect_imap(mail)

if __name__ == "__main__":
    main()