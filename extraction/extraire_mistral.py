from mistralai import Mistral
import os
import json
import time
from dotenv import load_dotenv

load_dotenv(r"C:\Users\user\pfe_mails\.env")
client = Mistral(api_key=os.getenv("MISTRAL_API_KEY"))

def extraire_cv_mistral(texte_cv, nom_fichier=""):
    """Alias appelé par pipeline_hybride.py"""
    prompt = f"""
Analyse ce CV et extrais les informations en JSON.
Réponds UNIQUEMENT avec le JSON, sans texte avant ou après, sans ```json```.
 
Format attendu :
{{
    "informations_personnelles": {{"nom":"","email":"","telephone":"","ville":""}},
    "formation": [{{"ecole":"","diplome":"","domaine":"","date_debut":"","date_fin":""}}],
    "experiences": [{{"entreprise":"","poste":"","date_debut":"","date_fin":"","description":""}}],
    "competences_techniques": [],
    "domaines_competence": [],
    "projets": [{{"titre":"","technologies":[],"description":""}}],
    "langues": []
}}
 
CV :
{texte_cv}
"""
    debut = time.time()
    try:
        response = client.chat.complete(
            model="mistral-small-latest",
            messages=[{"role": "user", "content": prompt}]
        )
        duree = round(time.time() - debut, 2)
        texte = response.choices[0].message.content.strip()
        texte = texte.replace("```json", "").replace("```", "").strip()
        data  = json.loads(texte)
        data.update({
            "cv_filename":       nom_fichier,
            "extraction_method": "llm_mistral",
            "temps_reponse_sec": duree,
            "succes":            True,
            "erreur":            None,
        })
        print(f"  ✅ Extraction Mistral réussie pour {nom_fichier} ({duree}s)")
        return data
    except Exception as e:
        duree = round(time.time() - debut, 2)
        print(f"  ✗ Erreur Mistral pour {nom_fichier} : {e}")
        return {
            "cv_filename":       nom_fichier,
            "extraction_method": "llm_mistral",
            "temps_reponse_sec": duree,
            "succes":            False,
            "erreur":            str(e),
        }

if __name__ == "__main__":
    from lire_cv import lire_cv

    dossier        = r"C:\Users\user\pfe_mails\cv_attachments\attachments"
    dossier_sortie = r"C:\Users\user\pfe_mails\resultats\mistral"
    os.makedirs(dossier_sortie, exist_ok=True)

    tous_les_resultats = []
    temps_list = []
    nb_succes  = 0
    nb_erreurs = 0

    for fichier in os.listdir(dossier):
        chemin = os.path.join(dossier, fichier)
        texte  = lire_cv(chemin)
        if texte:
            data = extraire_cv_mistral(texte, fichier)
            if data:
                if data.get("succes", False):
                    nb_succes += 1
                    temps_list.append(data["temps_reponse_sec"])
                else:
                    nb_erreurs += 1

                nom_json      = os.path.splitext(fichier)[0] + ".json"
                chemin_sortie = os.path.join(dossier_sortie, nom_json)
                with open(chemin_sortie, "w", encoding="utf-8") as f:
                    json.dump(data, f, ensure_ascii=False, indent=2)

                tous_les_resultats.append(data)

    nb_total    = nb_succes + nb_erreurs
    taux_succes = round(nb_succes  / nb_total * 100, 1) if nb_total > 0 else 0
    taux_erreur = round(nb_erreurs / nb_total * 100, 1) if nb_total > 0 else 0
    temps_moyen = round(sum(temps_list) / len(temps_list), 2) if temps_list else 0
    temps_min   = min(temps_list) if temps_list else 0
    temps_max   = max(temps_list) if temps_list else 0

    metriques = {
        "methode"         : "llm_mistral",
        "nb_cvs_traites"  : nb_total,
        "nb_succes"       : nb_succes,
        "nb_erreurs"      : nb_erreurs,
        "taux_succes_pct" : taux_succes,
        "taux_erreur_pct" : taux_erreur,
        "temps_moyen_sec" : temps_moyen,
        "temps_min_sec"   : temps_min,
        "temps_max_sec"   : temps_max,
    }

    print("\n" + "="*45)
    print("       MÉTRIQUES MISTRAL")
    print("="*45)
    print(f"  CVs traités   : {nb_total}")
    print(f"  Succès        : {nb_succes} ({taux_succes}%)")
    print(f"  Erreurs       : {nb_erreurs} ({taux_erreur}%)")
    print(f"  Temps moyen   : {temps_moyen}s")
    print(f"  Temps min/max : {temps_min}s / {temps_max}s")
    print("="*45)

    sortie_globale = {
        "metriques" : metriques,
        "resultats" : tous_les_resultats
    }
    with open(os.path.join(dossier_sortie, "_tous_les_resultats_mistral.json"), "w", encoding="utf-8") as f:
        json.dump(sortie_globale, f, ensure_ascii=False, indent=2)

    with open(os.path.join(dossier_sortie, "_metriques_mistral.json"), "w", encoding="utf-8") as f:
        json.dump(metriques, f, ensure_ascii=False, indent=2)

    print(f"\n✅ Résultats + métriques sauvegardés dans : {dossier_sortie}")