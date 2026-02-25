import imaplib, email, os, json
from email.header import decode_header
from config.settings import ATTACHMENTS_DIR, RAW_DATA_DIR

def decode_mime_words(s):
    decoded = decode_header(s)
    return ''.join(
        part.decode(enc or 'utf-8') if isinstance(part, bytes) else part
        for part, enc in decoded
    )

def fetch_emails(mail, folder="INBOX", filter="ALL"):
    mail.select(folder)
    status, messages = mail.search(None, filter)
    if status != "OK":
        return []
    email_ids = messages[0].split()
    print(f"{len(email_ids)} email(s) trouvé(s)")
    return email_ids

def get_email_body(msg):
    body = ""
    if msg.is_multipart():
        for part in msg.walk():
            content_type = part.get_content_type()
            disposition  = str(part.get("Content-Disposition"))
            if content_type == "text/plain" and "attachment" not in disposition:
                body = part.get_payload(decode=True).decode(errors="replace")
                break
    else:
        body = msg.get_payload(decode=True).decode(errors="replace")
    return body

def parse_and_save_email(mail, email_id, attachments_dir):
    status, data = mail.fetch(email_id, "(RFC822)")
    msg = email.message_from_bytes(data[0][1])

    email_data = {
        "id"          : email_id.decode(),
        "from"        : msg.get("From"),
        "to"          : msg.get("To"),
        "subject"     : decode_mime_words(msg.get("Subject", "")),
        "date"        : msg.get("Date"),
        "body"        : get_email_body(msg),
        "attachments" : []
    }

    os.makedirs(attachments_dir, exist_ok=True)
    for part in msg.walk():
        if part.get_content_disposition() == "attachment":
            filename = decode_mime_words(part.get_filename())
            filepath = os.path.join(attachments_dir, filename)
            with open(filepath, "wb") as f:
                f.write(part.get_payload(decode=True))
            email_data["attachments"].append({
                "filename" : filename,
                "filepath" : filepath,
                "type"     : part.get_content_type()
            })
            print(f"PJ sauvegardée : {filename}")

    os.makedirs(RAW_DATA_DIR, exist_ok=True)
    with open(f"{RAW_DATA_DIR}email_{email_id.decode()}.json", "w", encoding="utf-8") as f:
        json.dump(email_data, f, ensure_ascii=False, indent=4)

    return email_data