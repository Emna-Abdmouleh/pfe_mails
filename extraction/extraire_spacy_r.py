"""
extraire_spacy_r.py
-------------------
Méthode OFFLINE d'extraction CV : SpaCy + Regex
Produit la même structure JSON que les méthodes online (Groq/Gemini/Mistral).

Dépendances :
    pip install spacy pdfplumber
    python -m spacy download fr_core_news_lg
"""

import re
import json
import time
import os
from pathlib import Path

# ── SpaCy ────────────────────────────────────────────────────────────────────
try:
    import spacy
    try:
        nlp = spacy.load("fr_core_news_lg")
    except OSError:
        try:
            nlp = spacy.load("fr_core_news_md")
        except OSError:
            nlp = spacy.load("fr_core_news_sm")
except ImportError:
    nlp = None
    print("[WARN] SpaCy non installé – les entités NER ne seront pas utilisées.")

# ── PDF reader ────────────────────────────────────────────────────────────────
try:
    import pdfplumber
except ImportError:
    pdfplumber = None
    print("[WARN] pdfplumber non installé – seuls les fichiers .txt seront lus.")


# =============================================================================
# 1.  LECTURE DU FICHIER
# =============================================================================

def lire_cv(chemin: str) -> str:
    chemin = Path(chemin)
    if chemin.suffix.lower() == ".pdf":
        if pdfplumber is None:
            raise ImportError("pdfplumber requis pour lire les PDF.")
        texte = ""
        with pdfplumber.open(chemin) as pdf:
            for page in pdf.pages:
                t = page.extract_text(x_tolerance=3, y_tolerance=3)
                if t and len(t.strip()) > 20:
                    texte += t + "\n"
                else:
                    words = page.extract_words(
                        x_tolerance=5, y_tolerance=5,
                        keep_blank_chars=False, use_text_flow=True,
                    )
                    if words:
                        ligne_courante = []
                        y_courant = None
                        for w in words:
                            if y_courant is None:
                                y_courant = w["top"]
                            if abs(w["top"] - y_courant) > 5:
                                texte += " ".join(ligne_courante) + "\n"
                                ligne_courante = []
                                y_courant = w["top"]
                            ligne_courante.append(w["text"])
                        if ligne_courante:
                            texte += " ".join(ligne_courante) + "\n"
                    texte += "\n"
        return texte
    else:
        return chemin.read_text(encoding="utf-8", errors="ignore")


# =============================================================================
# 2.  UTILITAIRES
# =============================================================================

MOTS_EXCLUS_NOM = {
    "formation", "experience", "competences", "projets", "langues",
    "certifications", "profil", "skills", "education", "summary",
    "contact", "objectif", "about", "logiciel", "systeme", "information",
    "informatique", "ingenierie", "cv", "curriculum", "vitae", "resume",
}

def nettoyer(texte: str) -> str:
    texte = re.sub(r'\r\n', '\n', texte)
    texte = re.sub(r'^[\s|*\-]+$', '', texte, flags=re.MULTILINE)
    texte = re.sub(r'\n{3,}', '\n\n', texte)
    return texte.strip()


def trouver_section(texte: str, titres: list) -> str | None:
    toutes = [
        r"informations?\s*personnelles?", r"coordonn[ee]es?", r"profil", r"about\s*me",
        r"formation", r"[ee]ducation", r"dipl[oo]mes?", r"parcours\s*acad[ee]mique",
        r"exp[ee]riences?\s*professionnelles?", r"exp[ee]riences?", r"stages?",
        r"comp[ee]tences?\s*techniques?", r"comp[ee]tences?", r"skills?", r"technologies?",
        r"projets?", r"r[ee]alisations?", r"projets?\s*acad[ee]miques?",
        r"langues?", r"certifications?", r"loisirs?", r"r[ee]f[ee]rences?",
    ]
    pattern_debut = r"(?im)^[\s*\-|]*(?:" + "|".join(titres) + r")[\s:*\-|]*$"
    pattern_fin   = r"(?im)^[\s*\-|]*(?:" + "|".join(toutes) + r")[\s:*\-|]*$"

    m = re.search(pattern_debut, texte)
    if not m:
        return None
    debut = m.end()
    suite = texte[debut:]
    fins = list(re.finditer(pattern_fin, suite))
    if fins:
        return suite[:fins[0].start()].strip()
    return suite.strip()


# =============================================================================
# 3.  EXTRACTION DES CHAMPS
# =============================================================================

# ---- 3a. Informations personnelles ------------------------------------------

def extraire_email(texte: str) -> str:
    m = re.search(r'[\w.\-+]+@[\w.\-]+\.[a-zA-Z]{2,}', texte)
    return m.group(0).strip() if m else ""


def extraire_telephone(texte: str) -> str:
    patterns = [
        r'\+216[\s.\-]?\d{2}[\s.\-]?\d{3}[\s.\-]?\d{3}',
        r'\(\+216\)[\s.\-]?\d{2}[\s.\-]?\d{3}[\s.\-]?\d{3}',
        r'(?<!\d)\d{2}[\s.\-]\d{3}[\s.\-]\d{3}(?!\d)',
        r'\+\d{1,3}[\s.\-]?\(?\d{1,4}\)?[\s.\-]?\d{3,5}[\s.\-]?\d{4,6}',
    ]
    for p in patterns:
        m = re.search(p, texte)
        if m:
            return m.group(0).strip()
    return ""


def extraire_ville(texte: str) -> str:
    villes = [
        "Tunis", "Sfax", "Sousse", "Monastir", "Bizerte", "Nabeul", "Gabes",
        "Ariana", "Ben Arous", "Manouba", "Kairouan", "Kasserine", "Gafsa",
        "Medenine", "Tataouine", "Tozeur", "Kebili", "Siliana", "Zaghouan",
        "Jendouba", "Le Kef", "Beja", "Mahdia", "Hammamet", "Djerba",
        "Paris", "Lyon", "Marseille", "Bordeaux", "Toulouse",
        "Montreal", "Geneve", "Bruxelles", "Casablanca", "Rabat",
    ]
    for ville in villes:
        if re.search(r'\b' + re.escape(ville) + r'\b', texte, re.IGNORECASE):
            return ville
    return ""


def extraire_nom(texte: str) -> str:
    candidat = ""

    # 1) SpaCy NER
    if nlp:
        doc = nlp(texte[:800])
        for ent in doc.ents:
            if ent.label_ == "PER":
                mots = ent.text.strip().split()
                if (2 <= len(mots) <= 4
                        and not re.search(r'\d', ent.text)
                        and not any(m.lower() in MOTS_EXCLUS_NOM for m in mots)):
                    candidat = ent.text.strip()
                    break

    # 2) Heuristique
    if not candidat:
        for ligne in texte.splitlines()[:20]:
            ligne = ligne.strip()
            if not ligne or re.search(r'[@/\\|]', ligne) or len(ligne) > 50 or len(ligne) < 4:
                continue
            mots = ligne.split()
            if not (2 <= len(mots) <= 4):
                continue
            if not all(m[0].isupper() for m in mots if m):
                continue
            if any(m.lower().replace('\u00e9', 'e').replace('\u00e8', 'e') in MOTS_EXCLUS_NOM for m in mots):
                continue
            if ligne == ligne.upper():
                continue
            if re.search(r'\d', ligne):
                continue
            candidat = ligne
            break

    # 3) Supprimer doublons dans le nom
    if candidat:
        mots = candidat.split()
        vus = []
        vus_lower = set()
        for m in mots:
            if m.lower() not in vus_lower:
                vus.append(m)
                vus_lower.add(m.lower())
        candidat = " ".join(vus)

    return candidat


def extraire_informations_personnelles(texte: str) -> dict:
    return {
        "nom":       extraire_nom(texte),
        "email":     extraire_email(texte),
        "telephone": extraire_telephone(texte),
        "ville":     extraire_ville(texte),
    }


# ---- 3b. Formation ----------------------------------------------------------

RE_DIPLOME = re.compile(
    r'\b(Baccalaur[ee]at|Bac\b|Licence|Master\b|'
    r'Ing[ee]nieur|Doctorat|BTS|DUT|DEUG|'
    r'Pr[ee]pa(?:ratoire)?|'
    r"Cycle\s+pr[ee]paratoire|Cycle\s+ing[ee]nierie|Cycle\s+d['\u2019]ing[ee]nierie|"
    r'PhD|HDR|Mastère)',
    re.IGNORECASE,
)

RE_ECOLE = re.compile(
    r'\b(Facult[ee]|Institut|Universit[ee]|[EE]cole|Lyc[ee]e|'
    r'ISET|ENIS|ESPRIT|INSAT|ENSI|IIT|ISIMS|ISBS|FSEGS|FSEG|FSJEG|'
    r"SUP['\u2019]COM|Polytechnique|ISSATSO|ISSAT|ISGI|ISAMM|IHEC)",
    re.IGNORECASE,
)

RE_ANNEE_COMPLETE = re.compile(r'\b((?:19|20)\d{2})\b')

RE_DATE_PERIODE = re.compile(
    r'((?:19|20)\d{2})\s*[–\-/]\s*((?:19|20)\d{2}|[Pp]r[ée]sent|[Aa]ctuel|[Cc]urrent|[Ee]n\s+cours)',
)

RE_DOMAINE_FORM = re.compile(
    r'\b(G[ee]nie\s+logiciel|Informatique|R[ee]seaux?|'
    r'Intelligence\s+artificielle|S[ee]curit[ee]\s+informatique|'
    r"Sciences?\s+de\s+l['\u2019]informatique|Big\s+Data|"
    r'D[ee]veloppement\s+web|Cybers[ee]curit[ee]|Multim[ee]dia)',
    re.IGNORECASE,
)


def extraire_dates(texte: str):
    m = RE_DATE_PERIODE.search(texte)
    if m:
        debut = m.group(1)
        fin_raw = m.group(2)
        fin = "" if re.match(r'(?i)(pr[ée]sent|actuel|current|en\s+cours)', fin_raw) else fin_raw
        return debut, fin
    annees = RE_ANNEE_COMPLETE.findall(texte)
    return (annees[0] if annees else ""), (annees[1] if len(annees) > 1 else "")


def parser_bloc_formation(bloc: str) -> list:
    formations = []
    entrees = re.split(r'\n{2,}', bloc)
    if len(entrees) <= 1:
        entrees = re.split(r'(?=\b(?:19|20)\d{2}\b)', bloc)

    for entree in entrees:
        entree = entree.strip()
        if not entree or len(entree) < 5:
            continue

        diplome = ""
        ecole   = ""
        domaine = ""

        for ligne in entree.splitlines():
            if RE_DIPLOME.search(ligne) and not diplome:
                diplome = ligne.strip()
            if RE_ECOLE.search(ligne) and not ecole:
                ecole = ligne.strip()

        if not diplome:
            lignes = [l.strip() for l in entree.splitlines() if l.strip()]
            diplome = lignes[0] if lignes else ""

        m_dom = RE_DOMAINE_FORM.search(entree)
        if m_dom:
            domaine = m_dom.group(0).strip()

        debut, fin = extraire_dates(entree)

        if not diplome and not ecole:
            continue

        formations.append({
            "ecole":      ecole,
            "diplome":    diplome,
            "domaine":    domaine,
            "date_debut": debut,
            "date_fin":   fin,
        })

    return formations


def extraire_formation(texte: str) -> list:
    bloc = trouver_section(texte, [
        r"formation", r"[ee]ducation", r"dipl[oo]mes?",
        r"parcours\s*acad[ee]mique", r"cursus",
    ])
    if not bloc:
        lignes = [l for l in texte.splitlines() if RE_DIPLOME.search(l) or RE_ECOLE.search(l)]
        bloc = "\n".join(lignes) if lignes else None
    return parser_bloc_formation(bloc) if bloc else []


# ---- 3c. Expériences --------------------------------------------------------

RE_POSTE = re.compile(
    r'\b(stage(?:\s+de\s+fin\s+d["\u2019](?:[ee]tudes?|ann[ee]e))?|stagiaire|'
    r'ing[ee]nieur|d[ee]veloppeur|d[ee]veloppeuse|chef\s+de\s+projet|'
    r'consultant|technicien|assistant|analyste|responsable|directeur|'
    r'manager|architecte|data\s+scientist|devops|qa|testeur|'
    r'full[\s\-]?stack|back[\s\-]?end|front[\s\-]?end|intern|developer|engineer)',
    re.IGNORECASE,
)

RE_ENTREPRISE = re.compile(
    r'\b(soci[ee]t[ee]|entreprise|company|corp|SARL|SAS\b|SA\b|'
    r'startup|agence|cabinet|groupe|technologies|solutions|systems)',
    re.IGNORECASE,
)


def parser_bloc_experience(bloc: str) -> list:
    experiences = []
    entrees = re.split(r'\n{2,}', bloc)
    if len(entrees) <= 1:
        entrees = re.split(r'(?=\b(?:19|20)\d{2}\b)', bloc)

    for entree in entrees:
        entree = entree.strip()
        if not entree or len(entree) < 5:
            continue

        lignes = [l.strip() for l in entree.splitlines() if l.strip()]
        poste = ""
        entreprise = ""

        for l in lignes:
            if RE_POSTE.search(l) and not poste:
                poste = l
        for l in lignes:
            if RE_ENTREPRISE.search(l) and not entreprise:
                entreprise = l

        if not entreprise and lignes:
            entreprise = lignes[0] if lignes[0] != poste else (lignes[1] if len(lignes) > 1 else "")

        desc_lines = [l for l in lignes if l not in (poste, entreprise) and len(l) > 10]
        description = " ".join(desc_lines).strip()

        debut, fin = extraire_dates(entree)

        if not poste and not entreprise:
            continue

        experiences.append({
            "entreprise":  entreprise,
            "poste":       poste,
            "date_debut":  debut,
            "date_fin":    fin,
            "description": description,
        })

    return experiences


def extraire_experiences(texte: str) -> list:
    bloc = trouver_section(texte, [
        r"exp[ee]riences?\s*professionnelles?",
        r"exp[ee]riences?",
        r"stages?",
        r"parcours\s*professionnel",
    ])
    if not bloc:
        lignes = [l for l in texte.splitlines() if RE_POSTE.search(l)]
        bloc = "\n".join(lignes) if lignes else None
    return parser_bloc_experience(bloc) if bloc else []


# ---- 3d. Compétences techniques ---------------------------------------------

COMPETENCES_CONNUES = [
    r"Python", r"Java(?!Script)\b", r"JavaScript", r"TypeScript", r"PHP",
    r"C\+\+", r"C#", r"\bC\b", r"Ruby", r"Go\b", r"Rust", r"Kotlin",
    r"Swift", r"Scala", r"Dart", r"Matlab",
    r"HTML5?", r"CSS3?", r"React(?:\.js)?", r"Angular(?:JS)?", r"Vue(?:\.js)?",
    r"Node\.js", r"Django", r"Flask", r"Laravel", r"Spring(?:\s+Boot)?",
    r"Express(?:\.js)?", r"FastAPI", r"Bootstrap", r"Tailwind",
    r"Next\.js", r"Nuxt\.js",
    r"MySQL", r"PostgreSQL", r"MongoDB", r"SQLite", r"Redis", r"Oracle",
    r"Elasticsearch", r"Cassandra", r"MariaDB", r"Firebase",
    r"Docker", r"Kubernetes", r"Git\b", r"GitHub", r"GitLab",
    r"Jenkins", r"Maven", r"Gradle", r"Ansible", r"Terraform", r"Linux", r"Bash",
    r"TensorFlow", r"PyTorch", r"Keras", r"Scikit-learn", r"OpenCV",
    r"NLTK", r"Transformers", r"Pandas", r"NumPy", r"Matplotlib", r"Jupyter",
    r"UML", r"Merise", r"XML", r"JSON", r"REST(?:\s*API)?", r"GraphQL", r"SOAP",
    r"SFML", r"Unity", r"Arduino", r"Flutter", r"Ionic",
]

RE_COMPETENCES = re.compile(
    r'(?:' + '|'.join(COMPETENCES_CONNUES) + r')',
    re.IGNORECASE,
)

DOMAINES_CONNUS = [
    "Génie logiciel", "Intelligence Artificielle", "Réseau",
    "Bases de données", "Développement web", "Développement Web",
    "Cybersécurité", "Big Data", "Systèmes embarqués", "Cloud",
    "Multimédia", "Data Science", "DevOps",
]

RE_DOMAINES = re.compile(
    r'(?:' + '|'.join(re.escape(d) for d in DOMAINES_CONNUS) + r')',
    re.IGNORECASE,
)

NORMALISATION = {
    "tensorflow": "TensorFlow", "pytorch": "PyTorch",
    "javascript": "JavaScript", "typescript": "TypeScript",
    "mysql": "MySQL", "mongodb": "MongoDB", "postgresql": "PostgreSQL",
    "opencv": "OpenCV", "github": "GitHub", "gitlab": "GitLab",
    "html5": "HTML", "html": "HTML", "css3": "CSS", "css": "CSS",
    "node.js": "Node.js", "react.js": "React", "vue.js": "Vue.js",
    "scikit-learn": "Scikit-learn", "c++": "C++", "c#": "C#",
}


def normaliser_competence(nom: str) -> str:
    return NORMALISATION.get(nom.lower(), nom)


def extraire_competences_techniques(texte: str):
    bloc = trouver_section(texte, [
        r"comp[ee]tences?\s*techniques?", r"comp[ee]tences?",
        r"skills?", r"technologies?", r"outils?",
    ])
    cible = bloc if bloc else texte

    seen = set()
    techs = []
    for m in RE_COMPETENCES.finditer(cible):
        n = normaliser_competence(m.group(0))
        if n.lower() not in seen:
            seen.add(n.lower())
            techs.append(n)

    domaines = list(dict.fromkeys(m.group(0) for m in RE_DOMAINES.finditer(cible)))
    return techs, domaines


# ---- 3e. Projets ------------------------------------------------------------

def extraire_projets(texte: str) -> list:
    bloc = trouver_section(texte, [
        r"projets?", r"r[ee]alisations?",
        r"projets?\s+acad[ee]miques?", r"projets?\s+personnels?",
    ])
    if not bloc:
        return []

    projets = []
    for entree in re.split(r'\n{2,}', bloc):
        entree = entree.strip()
        if not entree or len(entree) < 5:
            continue
        lignes = [l.strip() for l in entree.splitlines() if l.strip()]
        titre = lignes[0] if lignes else ""
        if not titre or len(titre) > 80:
            continue
        description = " ".join(lignes[1:]).strip()
        seen = set()
        techs = []
        for m in RE_COMPETENCES.finditer(entree):
            n = normaliser_competence(m.group(0))
            if n.lower() not in seen:
                seen.add(n.lower())
                techs.append(n)
        projets.append({"titre": titre, "technologies": techs, "description": description})

    return projets


# ---- 3f. Langues ------------------------------------------------------------

LANGUES_CONNUES = [
    "Arabe", "Anglais", "Français", "Allemand", "Espagnol",
    "Italien", "Chinois", "Japonais", "Russe", "Turc",
    "Arabic", "English", "French", "German", "Spanish",
    "Italian", "Chinese", "Japanese", "Russian", "Turkish",
]

RE_LANGUES = re.compile(
    r'\b(?:' + '|'.join(re.escape(l) for l in LANGUES_CONNUES) + r')\b',
    re.IGNORECASE,
)

TRADUCTION_LANGUES = {
    "arabic": "Arabe", "english": "Anglais", "french": "Français",
    "german": "Allemand", "spanish": "Espagnol", "italian": "Italien",
    "chinese": "Chinois", "japanese": "Japonais", "russian": "Russe",
    "turkish": "Turc",
}


def extraire_langues(texte: str) -> list:
    bloc = trouver_section(texte, [r"langues?", r"languages?"])
    cible = bloc if bloc else texte
    seen = set()
    langues = []
    for m in RE_LANGUES.finditer(cible):
        l_norm = TRADUCTION_LANGUES.get(m.group(0).lower(), m.group(0).capitalize())
        if l_norm.lower() not in seen:
            seen.add(l_norm.lower())
            langues.append(l_norm)
    return langues


# =============================================================================
# 4.  FONCTION PRINCIPALE
# =============================================================================

def extraire_cv_spacy(chemin_cv: str) -> dict:
    debut = time.time()
    try:
        texte_brut = lire_cv(chemin_cv)
        texte = nettoyer(texte_brut)

        infos_perso           = extraire_informations_personnelles(texte)
        formation             = extraire_formation(texte)
        experiences           = extraire_experiences(texte)
        competences, domaines = extraire_competences_techniques(texte)
        projets               = extraire_projets(texte)
        langues               = extraire_langues(texte)

        duree = round(time.time() - debut, 2)
        return {
            "informations_personnelles": infos_perso,
            "formation":                 formation,
            "experiences":               experiences,
            "competences_techniques":    competences,
            "domaines_competence":       domaines,
            "projets":                   projets,
            "langues":                   langues,
            "cv_filename":               os.path.basename(chemin_cv),
            "extraction_method":         "spacy_regex_offline",
            "temps_reponse_sec":         duree,
            "succes":                    True,
            "erreur":                    None,
        }
    except Exception as e:
        duree = round(time.time() - debut, 2)
        return {
            "informations_personnelles": {},
            "formation": [], "experiences": [],
            "competences_techniques": [], "domaines_competence": [],
            "projets": [], "langues": [],
            "cv_filename":       os.path.basename(chemin_cv),
            "extraction_method": "spacy_regex_offline",
            "temps_reponse_sec": duree,
            "succes":            False,
            "erreur":            str(e),
        }


# =============================================================================
# 5.  POINT D'ENTREE
# =============================================================================

if __name__ == "__main__":
    import sys
    import glob

    if len(sys.argv) > 1:
        arg = sys.argv[1]
        if os.path.isdir(arg):
            chemins = glob.glob(os.path.join(arg, "*.pdf")) + glob.glob(os.path.join(arg, "*.txt"))
        else:
            chemins = [arg]
    else:
        chemins = (
            glob.glob("*.pdf") + glob.glob("*.txt") +
            glob.glob("cv_attachments/attachments/*.pdf") +
            glob.glob("../cv_attachments/attachments/*.pdf") +
            glob.glob("cvs/*.pdf") + glob.glob("cv/*.pdf") +
            glob.glob("data/*.pdf") + glob.glob("uploads/*.pdf")
        )

    if not chemins:
        print("[ERREUR] Aucun CV trouvé. Usage : python extraire_spacy_r.py [fichier_ou_dossier]")
        sys.exit(1)

    print(f"[INFO] {len(chemins)} CV(s) trouvé(s).\n")
    resultats = []
    for chemin in chemins:
        print(f"[INFO] Traitement : {chemin} ...")
        resultat = extraire_cv_spacy(chemin)
        resultats.append(resultat)
        statut = "✓" if resultat["succes"] else "✗"
        print(f"  {statut} {resultat['cv_filename']} — {resultat['temps_reponse_sec']}s")

    sortie = "resultats_spacy.json"
    with open(sortie, "w", encoding="utf-8") as f:
        json.dump(resultats, f, ensure_ascii=False, indent=2)
    print(f"\n[OK] {len(resultats)} CV(s) traité(s) → {sortie}")