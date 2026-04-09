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
    nlp = None
    for model in ["fr_core_news_lg", "fr_core_news_md", "fr_core_news_sm"]:
        try:
            nlp = spacy.load(model)
            break
        except OSError:
            continue
    if nlp is None:
        print("[WARN] Aucun modèle SpaCy français trouvé – NER désactivé, regex seul actif.")
except ImportError:
    nlp = None
    print("[WARN] SpaCy non installé – regex seul actif.")

# ── PDF reader ────────────────────────────────────────────────────────────────
try:
    import pdfplumber
except ImportError:
    pdfplumber = None
    print("[WARN] pdfplumber non installé – seuls les fichiers .txt seront lus.")


# =============================================================================
# 1.  LECTURE DU FICHIER
# =============================================================================

def _nettoyer_unicode(texte: str) -> str:
    """Supprime les icones/caracteres prives Unicode (FontAwesome, etc.)."""
    texte = re.sub(r'[\uE000-\uF8FF]', ' ', texte)
    texte = re.sub(r'[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]', '', texte)
    return texte


def _mots_vers_texte(mots: list) -> str:
    """Convertit une liste de mots positionnés en texte ligne par ligne."""
    if not mots:
        return ""
    lignes = []
    ligne_courante = []
    y_courant = mots[0]["top"]
    for w in sorted(mots, key=lambda x: (round(x["top"] / 5) * 5, x["x0"])):
        if abs(w["top"] - y_courant) > 6:
            if ligne_courante:
                lignes.append(" ".join(ligne_courante))
            ligne_courante = []
            y_courant = w["top"]
        ligne_courante.append(w["text"])
    if ligne_courante:
        lignes.append(" ".join(ligne_courante))
    return "\n".join(lignes)


def _reconstruire_depuis_mots(page) -> str:
    """
    Reconstruction bi-colonne via crop() de pdfplumber.
    Extrait chaque colonne dans son propre bbox pour eviter le melange.
    Colonne droite en premier (contenu principal), puis gauche (contact/competences).
    """
    largeur = page.width
    hauteur = page.height
    milieu  = largeur / 2

    # Crop precise par bbox : (x0, top, x1, bottom)
    try:
        page_gauche = page.crop((0,      0, milieu,  hauteur))
        page_droite = page.crop((milieu, 0, largeur, hauteur))

        t_gauche = page_gauche.extract_text(x_tolerance=3, y_tolerance=3) or ""
        t_droite = page_droite.extract_text(x_tolerance=3, y_tolerance=3) or ""

        # Si extraction directe donne du texte, l'utiliser
        if len(t_gauche.strip()) > 10 or len(t_droite.strip()) > 10:
            # Colonne droite d'abord (formations, expériences) puis gauche (compétences)
            parties = []
            if t_droite.strip():
                parties.append(t_droite)
            if t_gauche.strip():
                parties.append(t_gauche)
            return "\n".join(parties)
    except Exception:
        pass

    # Fallback : extraction par mots
    words = page.extract_words(x_tolerance=5, y_tolerance=5,
                                keep_blank_chars=False, use_text_flow=False)
    if not words:
        return ""

    col_gauche = [w for w in words if w["x0"] < milieu]
    col_droite = [w for w in words if w["x0"] >= milieu]

    if col_droite and len(col_droite) > 3:
        return _mots_vers_texte(col_droite) + "\n" + _mots_vers_texte(col_gauche)
    return _mots_vers_texte(words)


def _est_bicolonne(page) -> bool:
    """Detecte si une page a 2 colonnes en analysant la distribution X des mots."""
    words = page.extract_words()
    if len(words) < 10:
        return False
    milieu = page.width / 2
    gauche = sum(1 for w in words if w["x0"] < milieu - 20)
    droite = sum(1 for w in words if w["x0"] > milieu + 20)
    # Bi-colonne si les deux moitiés ont au moins 20% des mots chacune
    total = gauche + droite
    if total == 0:
        return False
    return (gauche / total > 0.2) and (droite / total > 0.2)


def lire_cv(chemin: str) -> str:
    chemin = Path(chemin)
    if chemin.suffix.lower() == ".pdf":
        if pdfplumber is None:
            raise ImportError("pdfplumber requis pour lire les PDF.")
        texte = ""
        with pdfplumber.open(chemin) as pdf:
            for page in pdf.pages:
                if _est_bicolonne(page):
                    # Lecture bi-colonne : colonne gauche puis colonne droite
                    t = _reconstruire_depuis_mots(page)
                    texte += _nettoyer_unicode(t) + "\n"
                else:
                    t = page.extract_text(x_tolerance=3, y_tolerance=3)
                    if t and len(t.strip()) > 20:
                        texte += _nettoyer_unicode(t) + "\n"
                    else:
                        t2 = _reconstruire_depuis_mots(page)
                        texte += _nettoyer_unicode(t2) + "\n"
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

def _normaliser_texte_espace(texte: str) -> str:
    """
    Normalise les textes où chaque lettre est séparée par un espace.
    "S A M A R  S A A D A O U I" -> "Samar Saadaoui"
    "E T U D I A N T E  E N  3 È M E" -> "Etudiante En 3ème"
    Gère aussi les lettres accentuées et les chiffres isolés.
    """
    lignes = texte.splitlines()
    resultat = []
    for ligne in lignes:
        mots = ligne.strip().split()
        # Détecte si la ligne est espacée : chaque token = 1 caractère
        # (lettre, chiffre, ou ponctuation courte)
        if len(mots) >= 4 and sum(1 for m in mots if len(m) == 1) / len(mots) > 0.7:
            # Sépare par double-espace pour trouver les "mots" originaux
            groupes = re.split(r'  +', ligne.strip())
            mots_reconst = []
            for g in groupes:
                tokens = g.strip().split()
                if not tokens:
                    continue
                # Groupe de lettres isolées -> fusionner
                if all(len(t) <= 2 for t in tokens):
                    mot = "".join(tokens)
                    mots_reconst.append(mot.capitalize() if mot.isupper() else mot)
                else:
                    mots_reconst.append(g.strip())
            resultat.append(" ".join(mots_reconst))
        else:
            resultat.append(ligne)
    return "\n".join(resultat)


def _normaliser_nom_espace(texte: str) -> str:
    """Alias pour compatibilité."""
    return _normaliser_texte_espace(texte)


def nettoyer(texte: str) -> str:
    texte = re.sub(r'\r\n', '\n', texte)
    texte = _normaliser_texte_espace(texte)
    texte = re.sub(r'^[\s|*\-]+$', '', texte, flags=re.MULTILINE)
    texte = re.sub(r'\n{3,}', '\n\n', texte)
    return texte.strip()


def trouver_section(texte: str, titres: list) -> str | None:
    toutes = [
        r"informations?\s*personnelles?", r"coordonn[ee]es?", r"profil", r"about\s*me",
        r"formation", r"[ee]ducation", r"dipl[oo]mes?", r"parcours\s*acad[ee]mique",
        r"exp[ee]riences?\s*professionnelles?", r"exp[ee]riences?", r"stages?",
        r"exp[ee]rience\s*associative", r"exp[ee]rience\s*acad[ee]mique",
        r"comp[ee]tences?\s*techniques?", r"comp[ee]tences?", r"skills?", r"technologies?",
        r"projets?", r"r[ee]alisations?", r"projets?\s*acad[ee]miques?", r"projects?",
        r"langues?", r"languages?", r"certifications?", r"loisirs?", r"r[ee]f[ee]rences?",
        r"[ee]ducation\s*et\s*formation", r"formation\s*acad[ee]mique",
        r"comp[ee]tences?\s*transversales?", r"comp[ee]tences?\s*linguistiques?",
        r"je\s*me\s*pr[ee]sente", r"[àa]\s*propos",
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
    # Cherche tous les emails et prend le premier valide
    matches = re.findall(r'[\w.\-+]+@[\w.\-]+\.[a-zA-Z]{2,}', texte)
    for m in matches:
        # Ignore les emails tronqués (doivent avoir un domaine reconnaissable)
        if len(m) > 8 and '.' in m.split('@')[-1]:
            return m.strip()
    return ""


def extraire_telephone(texte: str) -> str:
    patterns = [
        r'\+216[\s.\-]?\d{2}[\s.\-]?\d{3}[\s.\-]?\d{3}',      # +216 XX XXX XXX
        r'\(\+216\)[\s.\-]?\d{2}[\s.\-]?\d{3}[\s.\-]?\d{3}', # (+216) XX XXX XXX
        r'(?<!\d)\d{2}[\s.\-]\d{3}[\s.\-]\d{3}(?!\d)',           # XX XXX XXX
        r'(?<!\d)[2-9]\d{7}(?!\d)',                                      # 8 chiffres tunisiens (ex: 29409009)
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
    # Detecte aussi "sfax,tunis" ou "sfax, tunis" (format compact)
    m = re.search(r'\b(' + '|'.join(re.escape(v) for v in villes) + r')\b', texte, re.IGNORECASE)
    if m:
        return m.group(0).capitalize()
    return ""


def extraire_nom(texte: str) -> str:
    candidat = ""

    # 1) SpaCy NER — sur le texte nettoyé (noms espacés déjà normalisés)
    texte_norm = _normaliser_nom_espace(texte[:800])
    if nlp:
        doc = nlp(texte_norm)
        for ent in doc.ents:
            if ent.label_ == "PER":
                mots = ent.text.strip().split()
                if (2 <= len(mots) <= 4
                        and not re.search(r'\d', ent.text)
                        and len(ent.text.strip()) > 4
                        and not any(m.lower() in MOTS_EXCLUS_NOM for m in mots)):
                    candidat = ent.text.strip()
                    break

    # 2) Heuristique
    if not candidat:
        for ligne in texte.splitlines()[:25]:
            ligne = ligne.strip()
            if not ligne or re.search(r'[@/\\|]', ligne) or len(ligne) > 60 or len(ligne) < 4:
                continue
            # Normalise les noms espacés "S A M A R" avant de tester
            mots_test = ligne.split()
            if len(mots_test) >= 3 and all(len(m) == 1 and m.isupper() for m in mots_test):
                ligne = "".join(mots_test).capitalize()
                mots_test = [ligne]
            mots = ligne.split()
            if not (2 <= len(mots) <= 4):
                continue
            if not all(m[0].isupper() for m in mots if m):
                continue
            mots_lower = [m.lower().replace('\u00e9','e').replace('\u00e8','e').replace('\u00ea','e') for m in mots]
            if any(m in MOTS_EXCLUS_NOM for m in mots_lower):
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

    # 4) Normaliser casse : "SAADAOUI" -> "Saadaoui"
    if candidat:
        mots = candidat.split()
        mots_norm = []
        for m in mots:
            if m.isupper() and len(m) > 1:
                mots_norm.append(m.capitalize())
            else:
                mots_norm.append(m)
        candidat = " ".join(mots_norm)

    # 5) Filtre final: rejette si contient des mots parasites
    MOTS_PARASITES = {
        "domicile", "recherche", "contact", "adresse", "profil",
        "stage", "pfe", "linkedin", "github", "portfolio",
        "etudiant", "etudiante", "ingenieu", "developpeur",
    }
    if candidat:
        mots_c = [m.lower() for m in candidat.split()]
        if any(m in MOTS_PARASITES for m in mots_c):
            candidat = ""

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
            ligne_nette = re.sub(r'^\s*\[\s*[\d/.\s–\-]+(?:En cours|en cours)?\s*\]\s*', '', ligne).strip()
            if RE_DIPLOME.search(ligne_nette) and not diplome:
                diplome = ligne_nette
            if RE_ECOLE.search(ligne) and not ecole:
                # Nettoie aussi les URLs et métadonnées
                ecole_nette = re.sub(r'https?://\S+', '', ligne).strip()
                ecole_nette = re.sub(r'Localit[eé].*$', '', ecole_nette).strip()
                if ecole_nette:
                    ecole = ecole_nette

        if not diplome:
            lignes = [l.strip() for l in entree.splitlines() if l.strip()]
            # Nettoie le préfixe date Europass
            for l in lignes:
                l_nette = re.sub(r'^\s*\[\s*[\d/.\s–\-]+(?:En cours|en cours)?\s*\]\s*', '', l).strip()
                if l_nette:
                    diplome = l_nette
                    break

        m_dom = RE_DOMAINE_FORM.search(entree)
        if m_dom:
            domaine = m_dom.group(0).strip()

        debut, fin = extraire_dates(entree)

        if not diplome and not ecole:
            continue

        # Filtre : diplome trop court
        if diplome and len(diplome) < 8 and not RE_DIPLOME.search(diplome):
            continue
        # Filtre : entree qui ne contient que des dates/tirets/crochets
        if re.match(r"^[\d\s\-–/\[\]:.]+$", diplome.strip()):
            continue
        # Filtre : diplome commence par [ (fragment de date Europass)
        if diplome.strip().startswith("[") and len(diplome) < 15:
            continue
        # Filtre : diplome commence par "je me présente" ou "je suis"
        if re.match(r"(?i)^(je\s+me\s+pr[eé]sente|je\s+suis|etudiante?\s+en)", diplome.strip()):
            continue
        # Filtre : diplome sans mot-clé diplôme ET trop long (> 80 chars) = description
        if not RE_DIPLOME.search(diplome) and not RE_ECOLE.search(diplome) and len(diplome) > 80:
            continue
        # Filtre : ecole qui ressemble à une date ou fragment date
        if ecole and re.match(r"^[\d\s\-–/()\[\]IIT,Sfax.]+$", ecole.strip()):
            ecole = ""
        # Filtre : ecole contenant IEEE, WIE, AIESEC (associations, pas ecoles)
        if ecole and re.search(r"(IEEE|WIE|AIESEC|Club|Manager|Secr[eé]taire)", ecole, re.IGNORECASE):
            ecole = ""
        # Filtre : ecole commence par année "2025 – IIT..."
        if ecole and re.match(r"^\d{4}\s*[–\-]", ecole.strip()):
            # Tente d'extraire le nom de l'établissement après la date
            m_ecole = re.sub(r"^\d{4}\s*[–\-]\s*", "", ecole).strip()
            ecole = m_ecole if RE_ECOLE.search(m_ecole) else ""
        # Filtre : diplome contenant IEEE, WIE, AIESEC
        if diplome and re.search(r"(IEEE|WIE|AIESEC|Club|Manager|Secr[eé]taire)", diplome, re.IGNORECASE):
            if not RE_DIPLOME.search(diplome):
                continue
        # Filtre : diplome = phrase descriptive sans mot-clé diplome (ex: "Etudiante en...")
        if diplome and not RE_DIPLOME.search(diplome) and len(diplome) > 60:
            # Garde seulement si contient un nom d'école
            if not RE_ECOLE.search(diplome):
                diplome = ecole  # utilise l'école comme fallback
                ecole = ""

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
        r"[ee]ducation\s*et\s*formation", r"formation\s*acad[ee]mique",
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

        # Nettoie chaque ligne des préfixes de date type "2025 ] " ou "[ 19/06/2025 – 08/08/2025 ]"
        def nettoyer_ligne(l):
            l = re.sub(r"^[\[\d\s/.\-–:]+\]\s*", "", l).strip()
            l = re.sub(r"^\d{4}\s*[\]\)]\s*", "", l).strip()
            return l

        lignes_brutes = [l.strip() for l in entree.splitlines() if l.strip()]
        lignes = [nettoyer_ligne(l) for l in lignes_brutes]
        lignes = [l for l in lignes if l]

        poste = ""
        entreprise = ""

        for l in lignes:
            if RE_POSTE.search(l) and not poste:
                poste = l
        for l in lignes:
            if RE_ENTREPRISE.search(l) and not entreprise:
                entreprise = l

        if not entreprise and lignes:
            for l in lignes:
                if l == poste:
                    continue
                # Ignore les lignes de localité/pays/métadonnées
                if re.search(r'Localit[eé]|Pays\s*:|Adresse\s+[eé]lectronique', l, re.IGNORECASE):
                    continue
                if len(l) < 60 and not re.match(r"^[\d\s\-–/\[\]():]+$", l):
                    entreprise = l
                    break
            if not entreprise:
                entreprise = lignes[0] if lignes[0] != poste else (lignes[1] if len(lignes) > 1 else "")

        desc_lines = [l for l in lignes if l not in (poste, entreprise) and len(l) > 15]
        description = " ".join(desc_lines).strip()

        debut, fin = extraire_dates(entree)

        if not poste and not entreprise:
            continue

        # Filtre bruit
        if entreprise and re.match(r"^[\d\s\-–/\[\]():.]+$", entreprise.strip()):
            entreprise = ""
        if poste and re.match(r"^[\d\s\-–/\[\]():.]+$", poste.strip()):
            poste = ""
        # Filtre: entreprise = fragment de compétences
        if entreprise and re.search(r"Langages\s+de\s+programmation|Bases\s+de\s+données|Développement\s+Web", entreprise, re.IGNORECASE):
            entreprise = ""
        # Filtre: IEEE/AIESEC = expérience associative, pas professionnelle
        if entreprise and re.search(r"(IEEE|WIE|AIESEC)", entreprise):
            if not re.search(r"(stage|stagiaire|intern|developer|engineer)", poste, re.IGNORECASE):
                continue
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
        r"stage\s*professionnel",
        r"exp[ee]rience\s*professionnelle",
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
        r"langages?\s*de\s*programmation",
    ])
    cible = bloc if bloc else texte

    seen = set()
    techs = []
    for m in RE_COMPETENCES.finditer(cible):
        n = normaliser_competence(m.group(0))
        if n.lower() not in seen:
            seen.add(n.lower())
            techs.append(n)

    # Si peu de compétences trouvées dans le bloc, scanner aussi tout le texte
    if len(techs) < 5 and cible != texte:
        for m in RE_COMPETENCES.finditer(texte):
            n = normaliser_competence(m.group(0))
            if n.lower() not in seen:
                seen.add(n.lower())
                techs.append(n)

    domaines = list(dict.fromkeys(m.group(0) for m in RE_DOMAINES.finditer(texte)))
    return techs, domaines


# ---- 3e. Projets ------------------------------------------------------------

def extraire_projets(texte: str) -> list:
    bloc = trouver_section(texte, [
        r"projets?", r"r[ee]alisations?",
        r"projets?\s+acad[ee]miques?", r"projets?\s+personnels?",
        r"projects?",
    ])
    if not bloc:
        return []

    projets = []
    # Essai 1 : séparation par lignes vides
    entrees = re.split(r'\n{2,}', bloc)

    # Séparer par date en début de ligne (format MM/YYYY ou YYYY)
    if len(entrees) <= 2:
        entrees = re.split(
            r'(?=(?:\n|^)(?:(?:0[1-9]|1[0-2])/(?:19|20)\d{2})|(?:19|20)\d{2}\s*[–\-\s])',
            bloc,
            flags=re.MULTILINE
        )
    # Dernier recours : chaque ligne non-vide = projet potentiel
    if len(entrees) <= 1:
        entrees = [l for l in bloc.splitlines() if l.strip() and len(l.strip()) > 5]

    for entree in entrees:
        entree = entree.strip()
        if not entree or len(entree) < 5:
            continue

        lignes = [l.strip() for l in entree.splitlines() if l.strip()]
        if not lignes:
            continue

        # Titre : première ligne, nettoyer la date en tête
        titre = lignes[0]
        # Supprime la date en début de titre "06/2025 – 08/2025 CARPART –"
        titre = re.sub(r'^[\d/\s–\-]+', '', titre).strip()
        # Supprime le tiret long en début "— Full-Stack..."
        titre = re.sub(r'^[–\-—]+\s*', '', titre).strip()
        # Coupe au premier "," ou "–" si titre trop long
        if len(titre) > 60:
            m = re.search(r'[,–—]', titre)
            if m:
                titre = titre[:m.start()].strip()

        if not titre or len(titre) < 3:
            continue

        description = " ".join(lignes[1:]).strip()
        # Extrait technologies
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
    bloc = trouver_section(texte, [r"langues?", r"languages?", r"comp[ee]tences?\s*linguistiques?"])
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
            glob.glob("*.pdf") +
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