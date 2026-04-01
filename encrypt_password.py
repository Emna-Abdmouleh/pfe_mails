from cryptography.fernet import Fernet

def generate_and_encrypt():
    print("=" * 55)
    print("Chiffrement du mot de passe PFE")
    print("=" * 55)
    key = Fernet.generate_key()
    print("\n  Clé secrète générée avec succès !")
    pwd = input("\n Colle ton App Password Gmail ici : ")
    pwd = pwd.replace(" ", "")
    f = Fernet(key)
    encrypted = f.encrypt(pwd.encode())
    print("\n" + "=" * 55)
    print("  Copie exactement ces 2 lignes dans ton .env :")
    print("=" * 55)
    print(f"\nENCRYPTION_KEY={key.decode()}")
    print(f"EMAIL_PASSWORD={encrypted.decode()}")
    print("\n" + "=" * 55)
    print("  IMPORTANT :")
    print("   • Supprime l'ancienne ligne EMAIL_PASSWORD")
    print("   • Remplace par les 2 lignes ci-dessus")
    print("   • Ne partage JAMAIS ENCRYPTION_KEY")
    print("=" * 55)

if __name__ == "__main__":
    generate_and_encrypt()