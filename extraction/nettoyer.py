import re

def nettoyer_cv(data):

    # 1. Normaliser les langues (format uniforme)
    langues = data.get("langues", [])
    langues_propres = []
    for l in langues:
        if isinstance(l, dict):
            langues_propres.append(l.get("langue", "").capitalize())
        elif isinstance(l, str):
            langues_propres.append(l.capitalize())
    data["langues"] = langues_propres

    # 2. Normaliser le téléphone
    tel = data.get("informations_personnelles", {}).get("telephone", "")
    tel = re.sub(r"[^\d+]", "", tel)
    data["informations_personnelles"]["telephone"] = tel

    # 3. Normaliser la ville
    ville = data.get("informations_personnelles", {}).get("ville", "")
    data["informations_personnelles"]["ville"] = ville.capitalize()

    # 4. Normaliser les dates de formation
    for f in data.get("formation", []):
        f["ecole"] = f.get("ecole", "").strip()
        f["diplome"] = f.get("diplome", "").strip().capitalize()
        f["domaine"] = f.get("domaine", "").strip().capitalize()

    # 5. Supprimer les champs vides
    def supprimer_vides(obj):
        if isinstance(obj, dict):
            return {k: supprimer_vides(v) for k, v in obj.items()
                    if v not in [None, "", [], {}]}
        elif isinstance(obj, list):
            return [supprimer_vides(i) for i in obj
                    if i not in [None, "", [], {}]]
        return obj

    data = supprimer_vides(data)

    return data


# Test
if __name__ == "__main__":
    from lire_cv import lire_cv
    from extraire import extraire_cv
    import json
    import os

    dossier = r"C:\Users\user\pfe_mails\cv_attachments\attachments"
    for fichier in os.listdir(dossier):
        chemin = os.path.join(dossier, fichier)
        texte = lire_cv(chemin)
        if texte:
            data = extraire_cv(texte, fichier)
            if data:
                data_propre = nettoyer_cv(data)
                print(f"✅ {fichier} nettoyé")
                print(json.dumps(data_propre, ensure_ascii=False, indent=2))
                print("---")