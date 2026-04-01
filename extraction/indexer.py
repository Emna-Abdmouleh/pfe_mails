from elasticsearch import Elasticsearch
import os
import sys
from dotenv import load_dotenv

# Ajouter cv_attachments au path
sys.path.insert(0, r"C:\Users\user\pfe_mails\cv_attachments")

load_dotenv(r"C:\Users\user\pfe_mails\.env")

es = Elasticsearch(os.getenv("ES_URL", "http://10.0.2.15:9200"))

INDEX_NAME = "cvs_structured"

def creer_index():
    if not es.indices.exists(index=INDEX_NAME):
        es.indices.create(index=INDEX_NAME)
        print(f"✅ Index '{INDEX_NAME}' créé")
    else:
        print(f"ℹ️ Index '{INDEX_NAME}' existe déjà")

def indexer_cv(data):
    res = es.index(index=INDEX_NAME, document=data)
    print(f"✅ {data['cv_filename']} indexé — ID: {res['_id']}")

if __name__ == "__main__":
    from lire_cv import lire_cv
    from extraire import extraire_cv
    from nettoyer import nettoyer_cv
    from classifier import classifier_profil

    creer_index()

    dossier = r"C:\Users\user\pfe_mails\cv_attachments\attachments"
    for fichier in os.listdir(dossier):
        chemin = os.path.join(dossier, fichier)
        print(f"\n📄 Traitement de {fichier}...")
        texte = lire_cv(chemin)
        if texte:
            data = extraire_cv(texte, fichier)
            if data:
                data = nettoyer_cv(data)
                data = classifier_profil(data)
                indexer_cv(data)

    print("\n🎉 Pipeline terminé !")