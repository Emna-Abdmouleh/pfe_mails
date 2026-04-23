"""
reindexer_flat.py
-----------------
Lit les documents de l'index 'cvs' (nested)
et les réindexe dans 'cvs_flat' (à plat) pour Kibana.
"""

from elasticsearch import Elasticsearch

es = Elasticsearch("http://127.0.0.1:9200")

SOURCE_INDEX = "cvs"
TARGET_INDEX = "cvs_flat"

def flatten_doc(doc):
    return {
        "cv_filename":            doc.get("cv_filename", ""),
        "nom":                    doc.get("nom", ""),
        "email":                  doc.get("email", ""),
        "telephone":              doc.get("telephone", ""),
        "ville":                  doc.get("ville", ""),
        "competences_techniques": doc.get("competences_techniques", []),
        "langues":                doc.get("langues", []),
        "methode_utilisee":       doc.get("methode_utilisee", ""),
        "extraction_method":      doc.get("extraction_method", ""),
        "date_indexation":        doc.get("date_indexation", None),

        # Formation aplatie
        "formation_diplomes": [
            f.get("diplome", "") for f in doc.get("formation", []) if f.get("diplome")
        ],
        "formation_ecoles": [
            f.get("ecole", "") for f in doc.get("formation", []) if f.get("ecole")
        ],
        "formation_domaines": [
            f.get("domaine", "") for f in doc.get("formation", []) if f.get("domaine")
        ],

        # Expériences aplaties
        "experiences_postes": [
            e.get("poste", "") for e in doc.get("experiences", []) if e.get("poste")
        ],
        "experiences_entreprises": [
            e.get("entreprise", "") for e in doc.get("experiences", []) if e.get("entreprise")
        ],

        # Projets aplatis
        "projets_titres": [
            p.get("titre", "") for p in doc.get("projets", []) if p.get("titre")
        ],
        "projets_technologies": [
            t for p in doc.get("projets", [])
            for t in p.get("technologies", [])
        ],

        # Compteurs
        "nb_experiences":  len(doc.get("experiences", [])),
        "nb_competences":  len(doc.get("competences_techniques", [])),
        "nb_projets":      len(doc.get("projets", [])),
        "nb_certificats":  len(doc.get("certificats", [])),
    }

def reindexer():
    res = es.search(index=SOURCE_INDEX, body={"query": {"match_all": {}}}, size=1000)
    docs = res["hits"]["hits"]
    print(f"[INFO] {len(docs)} documents trouvés dans '{SOURCE_INDEX}'")

    succes = 0
    erreurs = 0
    for hit in docs:
        doc_flat = flatten_doc(hit["_source"])
        try:
            es.index(index=TARGET_INDEX, id=hit["_id"], body=doc_flat)
            print(f"  ✓ {doc_flat['cv_filename']}")
            succes += 1
        except Exception as e:
            print(f"  ✗ Erreur : {e}")
            erreurs += 1

    print(f"\n[OK] {succes} documents réindexés dans '{TARGET_INDEX}' | Erreurs : {erreurs}")

if __name__ == "__main__":
    reindexer()