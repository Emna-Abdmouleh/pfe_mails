from mail.connector import connect_imap, disconnect_imap, ensure_connected
from mail.fetcher   import fetch_emails

def main():

    # ÉTAPE 1 : Connexion
    mail = connect_imap()

    # ÉTAPE 2 : Vérifier la connexion
    mail = ensure_connected(mail)

    # ÉTAPE 3 : Récupérer les emails
    email_ids = fetch_emails(mail, folder="INBOX", filter="ALL")

    print(f"\n[✓] {len(email_ids)} email(s) dans la boite mail")

    # ÉTAPE 4 : Déconnexion
    disconnect_imap(mail)

if __name__ == "__main__":
    main()