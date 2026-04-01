import json
import os
from elasticsearch import Elasticsearch

# ============================================================
#  CONFIGURATION
# ============================================================
ES_HOST = "http://127.0.0.1:9200"

INDEX_NAME = "emails"
DATA_FOLDER = "data/raw"

# ============================================================
#  CONNEXION À ELASTICSEARCH
# ============================================================
print("🔌 Connexion à ElasticSearch...")

es = Elasticsearch(
    ES_HOST,
    verify_certs=False,
    ssl_show_warn=False
)

try:
    info = es.info()
    print("✅ Connexion réussie !")
except Exception as e:
    print(f"❌ Impossible de se connecter : {e}")
    exit(1)

# ============================================================
#  CRÉATION DE L'INDEX AVEC UN MAPPING ADAPTÉ
# ============================================================
mapping = {
    "mappings": {
        "properties": {
            "id":          {"type": "keyword"},
            "from":        {"type": "text",    "fields": {"keyword": {"type": "keyword"}}},
            "to":          {"type": "text",    "fields": {"keyword": {"type": "keyword"}}},
            "subject":     {"type": "text"},
            "date":        {"type": "text"},
            "body":        {"type": "text"},
            "attachments": {"type": "object", "enabled": False}

        }
    }
}

# Supprimer l'index s'il existe déjà (pour repartir proprement)
if es.indices.exists(index=INDEX_NAME):
    es.indices.delete(index=INDEX_NAME)
    print(f"🗑️  Index '{INDEX_NAME}' supprimé (nettoyage)")

es.indices.create(index=INDEX_NAME, body=mapping)
print(f"📁 Index '{INDEX_NAME}' créé avec succès !")

# ============================================================
#  INJECTION DES EMAILS
# ============================================================
print(f"\n📨 Injection des emails depuis '{DATA_FOLDER}'...\n")

success = 0
errors = 0

# Parcourir tous les fichiers JSON du dossier data/raw
json_files = sorted([f for f in os.listdir(DATA_FOLDER) if f.endswith(".json")])

if not json_files:
    print(f"❌ Aucun fichier JSON trouvé dans '{DATA_FOLDER}'")
    exit(1)

for filename in json_files:
    filepath = os.path.join(DATA_FOLDER, filename)
    
    try:
        with open(filepath, "r", encoding="utf-8") as f:
            email_data = json.load(f)
        
        # Utiliser l'id du JSON comme identifiant dans ES
        doc_id = email_data.get("id", filename.replace(".json", ""))
        
        # Injecter le document dans ElasticSearch
        es.index(index=INDEX_NAME, id=doc_id, document=email_data)
        
        print(f"  ✅ {filename} — Sujet: '{email_data.get('subject', 'N/A')}'")
        success += 1
        
    except Exception as e:
        print(f"  ❌ Erreur sur {filename}: {e}")
        errors += 1

# ============================================================
#  RÉSUMÉ FINAL
# ============================================================
print(f"\n{'='*50}")
print(f"📊 RÉSUMÉ DE L'INJECTION")
print(f"{'='*50}")
print(f"  ✅ Emails injectés avec succès : {success}")
print(f"  ❌ Erreurs                     : {errors}")
print(f"  📁 Index ElasticSearch         : {INDEX_NAME}")
print(f"{'='*50}")

# Vérification finale
count = es.count(index=INDEX_NAME)["count"]
print(f"\n🔍 Vérification : {count} document(s) dans l'index '{INDEX_NAME}'")
print(f"\n🌐 Kibana : http://192.168.1.18:5601")


















