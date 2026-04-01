import email
import json
import os
from email.header import decode_header
from config.logger import logger
from elastic.indexer import index_email   # ← indexation automatique

# ══════════════════════════════════════════════════════
# CONFIGURATION
# ══════════════════════════════════════════════════════
BASE_DIR        = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ATTACHMENTS_DIR = os.path.join(BASE_DIR, "attachments")
EMAILS_DIR      = os.path.join(BASE_DIR, "data", "raw")
# Extensions considérées comme des CV
CV_EXTENSIONS = {".pdf", ".doc", ".docx"}

# Mots-clés détectant un CV dans le nom du fichier ou le sujet
CV_KEYWORDS = [
    "cv", "curriculum", "resume", "candidature",
    "lettre", "motivation", "profil", "portfolio"
]
# ══════════════════════════════════════════════════════


def decode_mime_words(s):
    if not s:
        return "(sans sujet)"
    decoded = decode_header(s)
    result = []
    for part, enc in decoded:
        if isinstance(part, bytes):
            result.append(part.decode(enc or "utf-8", errors="replace"))
        else:
            result.append(part)
    return "".join(result)


def is_cv_file(filename: str, sujet: str = "") -> bool:
    if not filename:
        return False
    ext = os.path.splitext(filename)[1].lower()
    if ext not in CV_EXTENSIONS:
        return False
    combined = (filename + " " + sujet).lower()
    return any(kw in combined for kw in CV_KEYWORDS)


def get_email_body(msg) -> str:
    body = ""
    if msg.is_multipart():
        for part in msg.walk():
            content_type = part.get_content_type()
            disposition  = str(part.get("Content-Disposition", ""))
            if "attachment" in disposition:
                continue
            if content_type == "text/plain":
                charset = part.get_content_charset() or "utf-8"
                body = part.get_payload(decode=True).decode(charset, errors="replace")
                break
            elif content_type == "text/html" and not body:
                charset = part.get_content_charset() or "utf-8"
                body = part.get_payload(decode=True).decode(charset, errors="replace")
    else:
        charset = msg.get_content_charset() or "utf-8"
        body = msg.get_payload(decode=True).decode(charset, errors="replace")
    return body.strip()


def save_cv_attachments(msg, sujet: str) -> list:
    saved_files = []
    os.makedirs(ATTACHMENTS_DIR, exist_ok=True)

    for part in msg.walk():
        disposition = str(part.get("Content-Disposition", ""))
        if "attachment" not in disposition:
            continue

        filename = part.get_filename()
        if not filename:
            continue

        filename = decode_mime_words(filename)

        if not is_cv_file(filename, sujet):
            logger.info(f"  Ignore (pas un CV) : {filename}")
            continue

        filepath = os.path.join(ATTACHMENTS_DIR, filename)

        # Anti-écrasement
        if os.path.exists(filepath):
            base, ext = os.path.splitext(filename)
            counter = 1
            while os.path.exists(filepath):
                filepath = os.path.join(ATTACHMENTS_DIR, f"{base}_{counter}{ext}")
                counter += 1

        try:
            with open(filepath, "wb") as f:
                f.write(part.get_payload(decode=True))

            mime_type = part.get_content_type() or "application/octet-stream"
            saved_files.append({
                "filename": os.path.basename(filepath),
                "filepath": filepath.replace("\\", "/"),
                "type":     mime_type,
            })
            logger.info(f"  CV sauvegarde : {filepath}")

        except Exception as e:
            logger.error(f"  Erreur sauvegarde '{filename}' : {e}")

    return saved_files


def save_email_json(email_data: dict, email_id: str):
    os.makedirs(EMAILS_DIR, exist_ok=True)
    json_path = os.path.join(EMAILS_DIR, f"email_{email_id}.json")
    try:
        with open(json_path, "w", encoding="utf-8") as f:
            json.dump(email_data, f, ensure_ascii=False, indent=4)
        logger.info(f"  JSON sauvegarde : {json_path}")
    except Exception as e:
        logger.error(f"  Erreur sauvegarde JSON email {email_id} : {e}")


def parse_email(mail, email_id) -> dict | None:
    """
    Récupère et parse un email complet :
    1. Extrait les métadonnées + corps
    2. Sauvegarde les CV dans attachments/
    3. Génère data/raw/email_<id>.json
    4. Indexe dans Elasticsearch automatiquement
    5. Marque l'email comme LU
    """
    try:
        status, data = mail.fetch(email_id, "(RFC822)")

        if status != "OK" or not data or data[0] is None:
            logger.error(f"Impossible de recuperer l'email ID {email_id}")
            return None

        raw_email = data[0][1]
        msg       = email.message_from_bytes(raw_email)

        eid_str = email_id.decode() if isinstance(email_id, bytes) else str(email_id)

        # ── Métadonnées ───────────────────────────────
        sujet      = decode_mime_words(msg.get("Subject", ""))
        expediteur = msg.get("From", "Inconnu")
        destinat   = msg.get("To", "")
        date_email = msg.get("Date", "")
        corps      = get_email_body(msg)

        logger.info(f"  Sujet      : {sujet}")
        logger.info(f"  De         : {expediteur}")
        logger.info(f"  Date       : {date_email}")

        # ── Sauvegarde CV ─────────────────────────────
        fichiers = save_cv_attachments(msg, sujet)

        if fichiers:
            logger.info(f"  {len(fichiers)} CV sauvegarde(s)")
        else:
            logger.info("  Aucun CV detecte — aucun fichier cree")

        # ── Construire le dict email ──────────────────
        email_data = {
            "id":          eid_str,
            "from":        expediteur,
            "to":          destinat,
            "subject":     sujet,
            "date":        date_email,
            "body":        corps,
            "attachments": fichiers,
        }

        # ── Sauvegarder JSON dans data/raw/ ──────────
        save_email_json(email_data, eid_str)

        # ── Indexer dans Elasticsearch ────────────────
        try:
            index_email(email_data)
            logger.info(f"  Indexe dans Elasticsearch")
        except Exception as e:
            logger.error(f"  Erreur indexation Elasticsearch : {e}")

        # ── Marquer comme LU ──────────────────────────
        mail.store(email_id, "+FLAGS", "\\Seen")

        return email_data

    except Exception as e:
        logger.error(f"Erreur parsing email ID {email_id} : {e}")
        return None