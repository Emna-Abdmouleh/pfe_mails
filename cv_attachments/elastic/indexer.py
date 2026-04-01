from elasticsearch import Elasticsearch

ES_HOST = "http://127.0.0.1:9200"
INDEX_NAME = "emails"

es = Elasticsearch(
    ES_HOST,
    verify_certs=False,
    ssl_show_warn=False
)

def index_email(email_data):
    try:
        # Correction automatique de l'adresse
        if email_data.get("to") == "pfecandidatures@gmail.com":
            email_data["to"] = "pfe.candidatures@gmail.com"
            
        doc_id = email_data.get("id")
        if es.exists(index=INDEX_NAME, id=doc_id):
            print(f"  ⏭️  Email {doc_id} déjà indexé, ignoré.")
            return
        es.index(index=INDEX_NAME, id=doc_id, document=email_data)
        print(f"  ✅ Email {doc_id} indexé avec succès.")
    except Exception as e:
        print(f"  ❌ Erreur indexation : {e}")