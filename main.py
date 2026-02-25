from mail.connector import connect_imap, disconnect_imap
from mail.fetcher   import fetch_emails, parse_and_save_email
from config.settings import ATTACHMENTS_DIR

def main():
    mail      = connect_imap()
    email_ids = fetch_emails(mail, folder="INBOX", filter="ALL")

    for eid in email_ids:
        print(f"\n[→] Email ID : {eid.decode()}")
        data = parse_and_save_email(mail, eid, ATTACHMENTS_DIR)
        print(f"    Objet : {data['subject']}")
        print(f"    De    : {data['from']}")
        print(f"    PJ    : {len(data['attachments'])} fichier(s)")

    disconnect_imap(mail)
    print(f"\n Terminé — {len(email_ids)} email(s) traités")

if __name__ == "__main__":
    main()
    