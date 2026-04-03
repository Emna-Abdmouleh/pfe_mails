"""
verifier_apis.py
----------------
Vérifie en temps réel si Mistral et Groq sont joignables.
Importé par pipeline_hybride.py.
"""

import os
import requests
from dotenv import load_dotenv

load_dotenv(r"C:\Users\user\pfe_mails\.env")


def mistral_disponible() -> bool:
    api_key = os.getenv("MISTRAL_API_KEY")
    if not api_key:
        print("  [WARN] MISTRAL_API_KEY manquante dans .env")
        return False
    try:
        r = requests.get(
            "https://api.mistral.ai/v1/models",
            headers={"Authorization": f"Bearer {api_key}"},
            timeout=5,
        )
        return r.status_code == 200
    except Exception as e:
        print(f"  [WARN] Mistral injoignable : {e}")
        return False


def groq_disponible() -> bool:
    api_key = os.getenv("GROQ_API_KEY")
    if not api_key:
        print("  [WARN] GROQ_API_KEY manquante dans .env")
        return False
    try:
        r = requests.get(
            "https://api.groq.com/openai/v1/models",
            headers={"Authorization": f"Bearer {api_key}"},
            timeout=5,
        )
        return r.status_code == 200
    except Exception as e:
        print(f"  [WARN] Groq injoignable : {e}")
        return False


if __name__ == "__main__":
    print("Mistral :", "OK" if mistral_disponible() else "KO")
    print("Groq    :", "OK" if groq_disponible()    else "KO")