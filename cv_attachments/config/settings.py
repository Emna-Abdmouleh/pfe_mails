import os
from dotenv import load_dotenv
from config.crypto import get_decrypted_password

load_dotenv()

EMAIL_ADDRESS   = os.getenv("EMAIL_ADDRESS")
IMAP_SERVER     = os.getenv("IMAP_SERVER", "imap.gmail.com")
IMAP_PORT       = int(os.getenv("IMAP_PORT", 993))
ATTACHMENTS_DIR = os.getenv("ATTACHMENTS_DIR", "attachments/")
RAW_DATA_DIR    = os.getenv("RAW_DATA_DIR", "data/raw/")
EMAIL_PASSWORD = get_decrypted_password()