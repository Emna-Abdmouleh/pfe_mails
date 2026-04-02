import os
from dotenv import dotenv_values, set_key

ENV_FILE = os.path.join(os.path.dirname(__file__), ".env")


def get_config() -> dict:
    """Charge la configuration depuis le fichier .env"""
    vals = dotenv_values(ENV_FILE) if os.path.exists(ENV_FILE) else {}
    return {
        "mistral": {
            "enabled": vals.get("MISTRAL_ENABLED", "true").lower() == "true",
            "api_key": vals.get("MISTRAL_API_KEY", ""),
            "model": vals.get("MISTRAL_MODEL", "mistral-small-latest"),
        },
        "groq": {
            "enabled": vals.get("GROQ_ENABLED", "true").lower() == "true",
            "api_key": vals.get("GROQ_API_KEY", ""),
            "model": vals.get("GROQ_MODEL", "llama3-8b-8192"),
        },
        "offline": {
            "enabled": True,  # toujours actif, dernier recours
        },
    }


def save_config(data: dict) -> None:
    """Sauvegarde la configuration dans .env"""
    if not os.path.exists(ENV_FILE):
        open(ENV_FILE, "w").close()

    fields = {
        "MISTRAL_ENABLED": str(data.get("mistral_enabled", True)).lower(),
        "MISTRAL_API_KEY": data.get("mistral_api_key", ""),
        "MISTRAL_MODEL":   data.get("mistral_model", "mistral-small-latest"),
        "GROQ_ENABLED":    str(data.get("groq_enabled", True)).lower(),
        "GROQ_API_KEY":    data.get("groq_api_key", ""),
        "GROQ_MODEL":      data.get("groq_model", "llama3-8b-8192"),
    }
    for key, value in fields.items():
        if value:
            set_key(ENV_FILE, key, value)