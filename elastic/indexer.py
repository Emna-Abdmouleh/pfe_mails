import json
from pathlib import Path
from elasticsearch import Elasticsearch
import fitz
from docx import Document

es = Elasticsearch(
    "https://localhost:9200",
    basic_auth=("elastic", "ydwylvm9PMD6ruZd2aJO"),
    verify_certs=False
)

INDEX_NAME = "cvs"

def create_index():
    if es.indices.exists(index=INDEX_NAME):
        es.indices.delete(index=INDEX_NAME)
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

def extract_text(filepath):
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

def index_cvs():
    data_path = Path("data/raw")
    indexed = 0
    skipped = 0

    for json_file in sorted(data_path.glob("*.json")):
        with open(json_file, "r", encoding="utf-8") as f:
            email = json.load(f)

        if not email.get("attachments"):
            print(f"⏭️  {json_file.name} — sans CV, ignoré")
            skipped += 1
            continue

        for attachment in email["attachments"]:
            filepath = attachment.get("filepath", "")
            filename = attachment.get("filename", "")
            cv_text = extract_text(filepath)

            doc = {
                "email_id":    email["id"],
                "expediteur":  email["from"],
                "sujet":       email["subject"],
                "date":        email["date"],
                "contenu":     email["body"],
                "cv_filename": filename,
                "cv_text":     cv_text,
            }

            es.index(index=INDEX_NAME, id=email["id"], document=doc)
            print(f"✅ Indexé : {filename}")
            indexed += 1

    print(f"\n🎉 {indexed} CV(s) indexé(s), {skipped} ignoré(s)")

if __name__ == "__main__":
    create_index()
    index_cvs()