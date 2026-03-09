import json
from pathlib import Path
from elasticsearch import Elasticsearch
import fitz
from docx import Document

# ══════════════════════════════════════════════════════
# CONFIGURATION ELASTICSEARCH
# ══════════════════════════════════════════════════════
ES_HOST    = "https://127.0.0.1:9200"
ES_USER    = "elastic"
ES_PASS    = "mDgS=2yd5nKhagb7eH4O"
INDEX_NAME = "cvs"
# ══════════════════════════════════════════════════════

es = Elasticsearch(
    ES_HOST,
    basic_auth=(ES_USER, ES_PASS),
    verify_certs=False
)


def create_index_if_not_exists():
    """Crée l'index seulement s'il n'existe pas encore."""
    if es.indices.exists(index=INDEX_NAME):
        return

    mapping = {
        "properties": {
            "email_id":    {"type": "keyword"},
            "expediteur":  {"type": "text"},
            "sujet":       {"type": "text"},
            "date":        {"type": "text"},
            "contenu":     {"type": "text"},
            "cv_filename": {"type": "keyword"},
            "cv_text":     {"type": "text"},
        }
    }
    es.indices.create(index=INDEX_NAME, mappings=mapping)
    print("✅ Index 'cvs' créé !")


def extract_text(filepath: str) -> str:
    """Extrait le texte brut d'un PDF ou DOCX."""
    if filepath.endswith(".pdf"):
        try:
            doc = fitz.open(filepath)
            return "\n".join(page.get_text() for page in doc).strip()
        except Exception as e:
            print(f"❌ Erreur PDF : {e}")
            return ""
    elif filepath.endswith(".docx"):
        try:
            doc = Document(filepath)
            return "\n".join(p.text for p in doc.paragraphs).strip()
        except Exception as e:
            print(f"❌ Erreur DOCX : {e}")
            return ""
    return ""


def index_email(email_data: dict):
    """
    Indexe UN email dans Elasticsearch.
    Appelé automatiquement depuis parser.py après chaque email reçu.
    Si l'email n'a pas de CV, il est quand même indexé (cv_text vide).
    """
    create_index_if_not_exists()

    email_id   = email_data.get("id", "")
    attachments = email_data.get("attachments", [])

    if attachments:
        # Indexer chaque CV séparément
        for attachment in attachments:
            filepath   = attachment.get("filepath", "")
            filename   = attachment.get("filename", "")
            cv_text    = extract_text(filepath)

            doc = {
                "email_id":    email_id,
                "expediteur":  email_data.get("from", ""),
                "sujet":       email_data.get("subject", ""),
                "date":        email_data.get("date", ""),
                "contenu":     email_data.get("body", ""),
                "cv_filename": filename,
                "cv_text":     cv_text,
            }

            # ID unique = email_id + filename pour éviter les doublons
            doc_id = f"{email_id}_{filename}"
            es.index(index=INDEX_NAME, id=doc_id, document=doc)
            print(f"✅ Indexé dans Elasticsearch : {filename}")
    else:
        # Email sans CV — indexer quand même le message
        doc = {
            "email_id":    email_id,
            "expediteur":  email_data.get("from", ""),
            "sujet":       email_data.get("subject", ""),
            "date":        email_data.get("date", ""),
            "contenu":     email_data.get("body", ""),
            "cv_filename": "",
            "cv_text":     "",
        }
        es.index(index=INDEX_NAME, id=email_id, document=doc)
        print(f"✅ Indexé dans Elasticsearch : email {email_id} (sans CV)")


def index_cvs():
    """
    Indexe TOUS les emails depuis data/raw/*.json.
    À utiliser pour une indexation manuelle complète.
    """
    create_index_if_not_exists()

    data_path = Path("data/raw")
    indexed   = 0
    skipped   = 0

    for json_file in sorted(data_path.glob("*.json")):
        with open(json_file, "r", encoding="utf-8") as f:
            email_data = json.load(f)

        print(f"📄 Traitement : {json_file.name}")
        index_email(email_data)
        indexed += 1

    print(f"\n🎉 {indexed} email(s) indexé(s), {skipped} ignoré(s)")


if __name__ == "__main__":
    # Lancement manuel : indexe tous les JSON existants
    index_cvs()