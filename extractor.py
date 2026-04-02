import json
import re
import httpx
import spacy

from config import get_config
from services import check_mistral, check_groq

EXTRACTION_PROMPT = """
Tu es un extracteur de CV. Analyse le texte suivant et retourne UNIQUEMENT un JSON valide
avec exactement ces champs (sans texte autour) :
{
  "nom": "",
  "prenom": "",
  "email": "",
  "telephone": "",
  "date_naissance": "",
  "competences": [],
  "experiences": [{"poste": "", "entreprise": "", "debut": "", "fin": ""}],
  "formations": [{"diplome": "", "etablissement": "", "annee": ""}]
}

Texte du CV :
"""

_nlp = None


def _get_nlp():
    global _nlp
    if _nlp is None:
        try:
            _nlp = spacy.load("fr_core_news_sm")
        except OSError:
            _nlp = spacy.load("en_core_web_sm")
    return _nlp


# ─── Méthode 1 : Mistral ───────────────────────────────────────────────────

def extract_with_mistral(text: str, api_key: str, model: str) -> dict:
    response = httpx.post(
        "https://api.mistral.ai/v1/chat/completions",
        headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
        json={
            "model": model,
            "messages": [{"role": "user", "content": EXTRACTION_PROMPT + text}],
            "temperature": 0,
        },
        timeout=30,
    )
    response.raise_for_status()
    content = response.json()["choices"][0]["message"]["content"]
    return json.loads(content)


# ─── Méthode 2 : Groq ──────────────────────────────────────────────────────

def extract_with_groq(text: str, api_key: str, model: str) -> dict:
    response = httpx.post(
        "https://api.groq.com/openai/v1/chat/completions",
        headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
        json={
            "model": model,
            "messages": [{"role": "user", "content": EXTRACTION_PROMPT + text}],
            "temperature": 0,
        },
        timeout=30,
    )
    response.raise_for_status()
    content = response.json()["choices"][0]["message"]["content"]
    return json.loads(content)


# ─── Méthode 3 : Offline (SpaCy + Regex) ───────────────────────────────────

def extract_offline(text: str) -> dict:
    nlp = _get_nlp()
    doc = nlp(text)

    email = re.search(r"[\w.+-]+@[\w-]+\.[a-zA-Z]{2,}", text)
    phone = re.search(r"(?:\+?\d[\d\s\-().]{7,}\d)", text)
    date  = re.search(r"\b(\d{2}[/-]\d{2}[/-]\d{4}|\d{4})\b", text)

    persons = [ent.text for ent in doc.ents if ent.label_ in ("PER", "PERSON")]
    name_parts = persons[0].split() if persons else ["", ""]

    skill_keywords = [
        "python", "java", "javascript", "sql", "react", "django", "flask",
        "machine learning", "deep learning", "nlp", "docker", "git", "aws",
        "gestion de projet", "agile", "scrum",
    ]
    found_skills = [kw for kw in skill_keywords if kw.lower() in text.lower()]

    return {
        "nom":            name_parts[-1] if len(name_parts) > 1 else "",
        "prenom":         name_parts[0] if name_parts else "",
        "email":          email.group(0) if email else "",
        "telephone":      phone.group(0).strip() if phone else "",
        "date_naissance": date.group(0) if date else "",
        "competences":    found_skills,
        "experiences":    [],
        "formations":     [],
        "_methode":       "offline",
    }


# ─── Pipeline en cascade ────────────────────────────────────────────────────

def extract_cv(text: str) -> dict:
    """
    Cascade : Mistral (si enabled + dispo) → Groq (si enabled + dispo) → SpaCy
    Retourne le résultat enrichi d'un champ '_methode' pour traçabilité.
    """
    cfg = get_config()

    # 1. Mistral
    if cfg["mistral"]["enabled"]:
        status = check_mistral(cfg["mistral"]["api_key"])
        if status["available"]:
            try:
                result = extract_with_mistral(
                    text,
                    cfg["mistral"]["api_key"],
                    cfg["mistral"]["model"],
                )
                result["_methode"] = "mistral"
                return result
            except Exception as e:
                print(f"[Mistral] Erreur extraction : {e} → fallback Groq")

    # 2. Groq
    if cfg["groq"]["enabled"]:
        status = check_groq(cfg["groq"]["api_key"])
        if status["available"]:
            try:
                result = extract_with_groq(
                    text,
                    cfg["groq"]["api_key"],
                    cfg["groq"]["model"],
                )
                result["_methode"] = "groq"
                return result
            except Exception as e:
                print(f"[Groq] Erreur extraction : {e} → fallback offline")

    # 3. Offline — toujours disponible
    print("[Offline] SpaCy + Regex activé")
    return extract_offline(text)