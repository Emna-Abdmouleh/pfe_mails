import fitz  # PyMuPDF
from docx import Document
import os

def lire_pdf(chemin):
    doc = fitz.open(chemin)
    texte = ""
    for page in doc:
        texte += page.get_text()
    return texte.strip()

def lire_docx(chemin):
    doc = Document(chemin)
    texte = "\n".join([p.text for p in doc.paragraphs if p.text.strip()])
    return texte.strip()

def lire_cv(chemin):
    extension = os.path.splitext(chemin)[1].lower()
    if extension == ".pdf":
        return lire_pdf(chemin)
    elif extension == ".docx":
        return lire_docx(chemin)
    else:
        print(f"⚠️ Format non supporté : {chemin}")
        return ""

# Test
if __name__ == "__main__":
    dossier = r"C:\Users\user\pfe_mails\cv_attachments\attachments"
    for fichier in os.listdir(dossier):
        chemin = os.path.join(dossier, fichier)
        texte = lire_cv(chemin)
        print(f"✅ {fichier} — {len(texte)} caractères extraits")
        print(texte[:200])
        print("---")