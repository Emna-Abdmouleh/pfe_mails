from dotenv import load_dotenv
import os

load_dotenv()

print("EMAIL_ADDRESS  :", os.getenv("EMAIL_ADDRESS"))
print("ENCRYPTION_KEY :", os.getenv("ENCRYPTION_KEY"))
print("EMAIL_PASSWORD :", os.getenv("EMAIL_PASSWORD"))
# Test du déchiffrement
print("\n--- Test déchiffrement ---")
from config.crypto import get_decrypted_password
pwd = get_decrypted_password()
print("Mot de passe déchiffré :", pwd)
print("Longueur :", len(pwd))