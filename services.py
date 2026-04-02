import httpx


def check_mistral(api_key: str) -> dict:
    if not api_key:
        return {"available": False, "reason": "Clé API manquante"}
    try:
        r = httpx.get(
            "https://api.mistral.ai/v1/models",
            headers={"Authorization": f"Bearer {api_key}"},
            timeout=5,
        )
        if r.status_code == 200:
            return {"available": True, "reason": "Connecté", "quota": "OK"}
        elif r.status_code == 401:
            return {"available": False, "reason": "Clé invalide (401)"}
        elif r.status_code == 429:
            return {"available": False, "reason": "Quota épuisé (429)"}
        else:
            return {"available": False, "reason": f"HTTP {r.status_code}"}
    except httpx.TimeoutException:
        return {"available": False, "reason": "Timeout — service inaccessible"}
    except Exception as e:
        return {"available": False, "reason": str(e)}


def check_groq(api_key: str) -> dict:
    if not api_key:
        return {"available": False, "reason": "Clé API manquante"}
    try:
        r = httpx.get(
            "https://api.groq.com/openai/v1/models",
            headers={"Authorization": f"Bearer {api_key}"},
            timeout=5,
        )
        if r.status_code == 200:
            return {"available": True, "reason": "Connecté", "quota": "OK"}
        elif r.status_code == 401:
            return {"available": False, "reason": "Clé invalide (401)"}
        elif r.status_code == 429:
            return {"available": False, "reason": "Quota épuisé (429)"}
        else:
            return {"available": False, "reason": f"HTTP {r.status_code}"}
    except httpx.TimeoutException:
        return {"available": False, "reason": "Timeout — service inaccessible"}
    except Exception as e:
        return {"available": False, "reason": str(e)}