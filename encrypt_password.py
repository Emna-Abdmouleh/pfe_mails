from cryptography.fernet import Fernet

def generate_and_encrypt():
    print("=" * 55)
    print("   🔐  Chiffrement du mot de passe PFE")
    print("=" * 55)

    # ── Étape A : Générer une clé secrète ─────────────────
    key = Fernet.generate_key()
    # Cette clé est unique et aléatoire à chaque génération.
    # C'est avec elle qu'on va chiffrer et déchiffrer le pwd.
    # Si tu la perds → impossible de récupérer le pwd !

    print("\n✅  Clé secrète générée avec succès !")

    # ── Étape B : Demander le mot de passe ────────────────
    pwd = input("\n👉  Colle ton App Password Gmail ici : ")
    pwd = pwd.replace(" ", "")
    # On enlève les espaces car Gmail les affiche parfois
    # ex: "abcd efgh ijkl mnop" → "abcdefghijklmnop"

    # ── Étape C : Chiffrer ────────────────────────────────
    f = Fernet(key)
    encrypted = f.encrypt(pwd.encode())
    # .encode()  → convertit le texte en bytes
    # .encrypt() → chiffre les bytes avec la clé
    # résultat   → bytes illisibles sans la clé

    # ── Étape D : Afficher le résultat ────────────────────
    print("\n" + "=" * 55)
    print("📋  Copie exactement ces 2 lignes dans ton .env :")
    print("=" * 55)
    print(f"\nENCRYPTION_KEY={key.decode()}")
    print(f"EMAIL_PASSWORD={encrypted.decode()}")
    print("\n" + "=" * 55)
    print("⚠️  IMPORTANT :")
    print("   • Supprime l'ancienne ligne EMAIL_PASSWORD")
    print("   • Remplace par les 2 lignes ci-dessus")
    print("   • Ne partage JAMAIS ENCRYPTION_KEY")
    print("=" * 55)

if __name__ == "__main__":
    generate_and_encrypt()