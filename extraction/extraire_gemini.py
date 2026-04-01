from google import genai
import os
import json
from dotenv import load_dotenv

load_dotenv(r"C:\Users\user\pfe_mails\.env")

client = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))

def extraire_cv_gemini(texte_cv, nom_fichier=""):
    prompt = f"""
    Analyse ce CV et extrais les informations en JSON.
    Réponds UNIQUEMENT avec le JSON, sans texte avant ou après, sans ```json```.

    Format attendu :
    {{
        "informations_personnelles": {{
            "nom": "",
            "email": "",
            "telephone": "",
            "ville": ""
        }},
        "formation": [
            {{
                "ecole": "",
                "diplome": "",
                "domaine": "",
                "date_debut": "",
                "date_fin": ""
            }}
        ],
        "experiences": [
            {{
                "entreprise": "",
                "poste": "",
                "date_debut": "",
                "date_fin": "",
                "description": ""
            }}
        ],
        "competences_techniques": [],
        "domaines_competence": [],
        "projets": [
            {{
                "titre": "",
                "technologies": [],
                "description": ""
            }}
        ],
        "langues": []
    }}

    CV :
    {texte_cv}
    """

    try:
        response = client.models.generate_content(
            model="gemini-2.0-flash",
            contents=prompt
        )
        texte = response.text.strip()
        texte = texte.replace("```json", "").replace("```", "").strip()
        data = json.loads(texte)
        data["cv_filename"] = nom_fichier
        data["extraction_method"] = "llm_gemini"
        print(f"✅ Extraction Gemini réussie pour {nom_fichier}")
        return data
    except Exception as e:
        print(f"❌ Erreur Gemini {nom_fichier} : {e}")
        return None


# Test
if __name__ == "__main__":
    from lire_cv import lire_cv

    dossier = r"C:\Users\user\pfe_mails\cv_attachments\attachments"
    for fichier in os.listdir(dossier):
        chemin = os.path.join(dossier, fichier)
        texte = lire_cv(chemin)
        if texte:
            data = extraire_cv_gemini(texte, fichier)
            if data:
                print(json.dumps(data, ensure_ascii=False, indent=2))
                print("---")