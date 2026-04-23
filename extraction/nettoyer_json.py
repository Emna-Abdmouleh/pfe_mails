"""
nettoyer_json.py
----------------
Nettoie et normalise les JSONs extraits par le pipeline hybride.
"""

import re
import json
import os
import glob
from datetime import datetime


# =============================================================================
# UTILITAIRES
# =============================================================================

def nettoyer_chaine(s) -> str:
    if not isinstance(s, str):
        return ""
    return re.sub(r'\s+', ' ', s.strip())


def normaliser_annee(valeur) -> int | None:
    if not valeur:
        return None
    s = str(valeur).strip().lower()
    if s in ("présent", "present", "actuel", "current", "en cours", ""):
        return None
    m = re.search(r'((?:19|20)\d{2})', s)
    return int(m.group(1)) if m else None


def dedupliquer(lst: list) -> list:
    vus, result = set(), []
    for item in lst:
        if isinstance(item, str):
            item = nettoyer_chaine(item)
        if not item:
            continue
        cle = item.lower() if isinstance(item, str) else str(item)
        if cle not in vus:
            vus.add(cle)
            result.append(item)
    return result


# =============================================================================
# NETTOYAGE PAR SECTION
# =============================================================================

def nettoyer_infos_personnelles(data: dict) -> dict:
    infos = data.get("informations_personnelles", {})
    return {
        "nom":       nettoyer_chaine(infos.get("nom", "")),
        "email":     nettoyer_chaine(infos.get("email", "")).lower(),
        "telephone": nettoyer_chaine(infos.get("telephone", "")),
        "ville":     nettoyer_chaine(infos.get("ville", "")),
    }


def nettoyer_formation(data: dict) -> list:
    result = []
    for f in data.get("formation", []):
        if isinstance(f, str):
            continue
        ecole   = nettoyer_chaine(f.get("ecole", ""))
        diplome = nettoyer_chaine(f.get("diplome", ""))
        if not ecole and not diplome:
            continue
        result.append({
            "ecole":      ecole,
            "diplome":    diplome,
            "domaine":    nettoyer_chaine(f.get("domaine", "")),
            "date_debut": normaliser_annee(f.get("date_debut")),
            "date_fin":   normaliser_annee(f.get("date_fin")),
        })
    return result


def nettoyer_experiences(data: dict) -> list:
    result = []
    for e in data.get("experiences", []):
        if isinstance(e, str):
            continue
        entreprise = nettoyer_chaine(e.get("entreprise", ""))
        poste      = nettoyer_chaine(e.get("poste", ""))
        if not entreprise and not poste:
            continue
        result.append({
            "entreprise":  entreprise,
            "poste":       poste,
            "date_debut":  normaliser_annee(e.get("date_debut")),
            "date_fin":    normaliser_annee(e.get("date_fin")),
            "description": nettoyer_chaine(e.get("description", "")),
        })
    return result


def nettoyer_projets(data: dict) -> list:
    result = []
    for p in data.get("projets", []):
        if isinstance(p, str):
            continue
        titre = nettoyer_chaine(p.get("titre", ""))
        if not titre:
            continue
        result.append({
            "titre":        titre,
            "technologies": dedupliquer(p.get("technologies", [])),
            "description":  nettoyer_chaine(p.get("description", "")),
        })
    return result


def nettoyer_certificats(data: dict) -> list:
    result = []
    for c in data.get("certificats", []):
        # Si c'est une string directement
        if isinstance(c, str):
            titre = nettoyer_chaine(c)
            if titre:
                result.append({"titre": titre, "organisme": "", "date": None})
            continue
        if isinstance(c, dict):
            titre = nettoyer_chaine(c.get("titre", ""))
            if not titre:
                continue
            result.append({
                "titre":     titre,
                "organisme": nettoyer_chaine(c.get("organisme", "")),
                "date":      normaliser_annee(c.get("date")),
            })
    return result


def nettoyer_langues(data: dict) -> list:
    result = []
    for l in data.get("langues", []):
        # Si c'est une string directement
        if isinstance(l, str):
            val = nettoyer_chaine(l)
            if val:
                result.append(val)
            continue
        # Si c'est un objet {"langue": "Arabe", "niveau": "avancé"}
        if isinstance(l, dict):
            val = nettoyer_chaine(l.get("langue", "") or l.get("nom", ""))
            if val:
                result.append(val)
    return dedupliquer(result)


def nettoyer_experiences_associatives(data: dict) -> list:
    result = []
    for e in data.get("experiences_associatives", []):
        if isinstance(e, str):
            continue
        titre = nettoyer_chaine(e.get("titre", ""))
        if not titre:
            continue
        result.append({
            "titre": titre,
            "date":  normaliser_annee(e.get("date")),
        })
    return result


# =============================================================================
# FONCTION PRINCIPALE
# =============================================================================

def nettoyer_cv(data: dict) -> dict:
    infos = nettoyer_infos_personnelles(data)
    return {
        "cv_filename":               nettoyer_chaine(data.get("cv_filename", "")),
        "nom":                       infos["nom"],
        "email":                     infos["email"],
        "telephone":                 infos["telephone"],
        "ville":                     infos["ville"],
        "formation":                 nettoyer_formation(data),
        "experiences":               nettoyer_experiences(data),
        "competences_techniques":    dedupliquer(data.get("competences_techniques", [])),
        "domaines_competence":       dedupliquer(data.get("domaines_competence", [])),
        "projets":                   nettoyer_projets(data),
        "langues":                   nettoyer_langues(data),
        "certificats":               nettoyer_certificats(data),
        "experiences_associatives":  nettoyer_experiences_associatives(data),
        "extraction_method":         data.get("extraction_method", ""),
        "methode_utilisee":          data.get("methode_utilisee", ""),
        "date_indexation":           datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ"),
    }


# =============================================================================
# TRAITEMENT EN LOT
# =============================================================================

def nettoyer_dossier(dossier_entree: str, dossier_sortie: str) -> list:
    os.makedirs(dossier_sortie, exist_ok=True)

    fichiers = [
        f for f in glob.glob(os.path.join(dossier_entree, "*.json"))
        if not os.path.basename(f).startswith("_")
    ]

    if not fichiers:
        print(f"[ERREUR] Aucun JSON trouvé dans : {dossier_entree}")
        return []

    print(f"[INFO] {len(fichiers)} JSON(s) à nettoyer")
    docs = []

    for chemin in fichiers:
        nom = os.path.basename(chemin)
        try:
            with open(chemin, "r", encoding="utf-8") as f:
                data = json.load(f)

            if not data.get("succes", False):
                print(f"  ⚠ ignoré (succes=false) : {nom}")
                continue

            doc = nettoyer_cv(data)
            docs.append(doc)

            with open(os.path.join(dossier_sortie, nom), "w", encoding="utf-8") as f:
                json.dump(doc, f, ensure_ascii=False, indent=2)

            print(f"  ✓ {nom}")

        except Exception as e:
            print(f"  ✗ {nom} : {e}")

    print(f"\n✅ {len(docs)} document(s) nettoyés → {dossier_sortie}")
    return docs


if __name__ == "__main__":
    DOSSIER_ENTREE = r"C:\Users\user\pfe_mails\resultats\pipeline_hybride"
    DOSSIER_SORTIE = r"C:\Users\user\pfe_mails\resultats\json_propres"
    nettoyer_dossier(DOSSIER_ENTREE, DOSSIER_SORTIE)