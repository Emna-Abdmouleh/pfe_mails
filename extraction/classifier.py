def classifier_profil(data):
    
    formations = data.get("formation", [])
    experiences = data.get("experiences", [])
    competences = [c.lower() for c in data.get("competences_techniques", [])]

    # 1. Niveau académique
    niveau = "Bac"
    for f in formations:
        diplome = f.get("diplome", "").lower()
        if any(x in diplome for x in ["master", "ingénieur", "ingenieur"]):
            niveau = "Bac+5"
        elif any(x in diplome for x in ["licence", "bachelor"]):
            niveau = "Bac+3"
        elif any(x in diplome for x in ["bts", "bac+2", "dut"]):
            niveau = "Bac+2"

    # 2. Niveau expérience
    nb_exp = len(experiences)
    if nb_exp == 0:
        exp_niveau = "Débutant"
    elif nb_exp <= 2:
        exp_niveau = "Junior"
    else:
        exp_niveau = "Senior"

    # 3. Domaine principal
    domaine = "Général"
    if any(x in competences for x in ["python", "machine learning", "data", "pandas", "power bi", "elasticsearch"]):
        domaine = "Data / IA"
    elif any(x in competences for x in ["react", "angular", "vue", "html", "css", "javascript"]):
        domaine = "Frontend"
    elif any(x in competences for x in ["java", "spring", "flask", "django", "node", "laravel", "php"]):
        domaine = "Backend"
    elif any(x in competences for x in ["docker", "kubernetes", "aws", "devops", "linux"]):
        domaine = "DevOps"

    # 4. Ecole principale
    ecole = ""
    if formations:
        ecole = formations[0].get("ecole", "")

    # 5. Categorie age (basée sur date bac)
    categorie_age = "Inconnu"
    for f in formations:
        diplome = f.get("diplome", "").lower()
        date_fin = f.get("date_fin", "")
        if "bac" in diplome and date_fin:
            try:
                annee = int(date_fin[-4:])
                age_approx = 2026 - annee + 18
                if age_approx <= 22:
                    categorie_age = "18-22 ans"
                elif age_approx <= 25:
                    categorie_age = "23-25 ans"
                else:
                    categorie_age = "26+ ans"
            except:
                pass

    data["classification"] = {
        "niveau_academique": niveau,
        "niveau_experience": exp_niveau,
        "domaine_principal": domaine,
        "ecole_principale": ecole,
        "categorie_age": categorie_age
    }

    return data


# Test
if __name__ == "__main__":
    from lire_cv import lire_cv
    from extraire import extraire_cv
    from nettoyer import nettoyer_cv
    import json
    import os

    dossier = r"C:\Users\user\pfe_mails\cv_attachments\attachments"
    for fichier in os.listdir(dossier):
        chemin = os.path.join(dossier, fichier)
        texte = lire_cv(chemin)
        if texte:
            data = extraire_cv(texte, fichier)
            if data:
                data = nettoyer_cv(data)
                data = classifier_profil(data)
                print(f"✅ {fichier} classifié")
                print(json.dumps(data["classification"], ensure_ascii=False, indent=2))
                print("---")