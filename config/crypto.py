from cryptography.fernet import Fernet, InvalidToken
import os

def get_decrypted_password():
    key = os.getenv("ENCRYPTION_KEY")
    encrypted_pwd = os.getenv("EMAIL_PASSWORD")

    print(f"[DEBUG] Clé lue       : {key}")
    print(f"[DEBUG] PWD chiffré   : {encrypted_pwd}")

    f = Fernet(key.encode())
    decrypted = f.decrypt(encrypted_pwd.encode())

    print(f"[DEBUG] PWD déchiffré (bytes) : {decrypted}")
    print(f"[DEBUG] PWD déchiffré (str)   : {decrypted.decode()}")

    return decrypted.decode()