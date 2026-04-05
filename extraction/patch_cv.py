# patch_cv.py - colle ce fichier dans extraction\ et lance-le
src = open("extraire_spacy_r.py", encoding="utf-8").read()

# Patch 1: _page_vers_texte
if "_page_vers_texte" not in src:
    old = "def lire_cv(chemin: str) -> str:\n    import fitz  # PyMuPDF"
    new = '''def _page_vers_texte(page) -> str:
    import fitz
    largeur = page.rect.width
    milieu = largeur / 2
    blocs = page.get_text("blocks", sort=False)
    if not blocs:
        return ""
    blocs_gauche, blocs_droite, blocs_centre = [], [], []
    for b in blocs:
        if len(b) < 5 or not b[4].strip():
            continue
        x0, y0, x1, y1, contenu = b[0], b[1], b[2], b[3], b[4]
        larg_bloc = x1 - x0
        if larg_bloc > largeur * 0.55 or (x0 < milieu * 0.3 and x1 > milieu * 1.3):
            blocs_centre.append((y0, x0, contenu))
        elif x1 <= milieu + 20:
            blocs_gauche.append((y0, x0, contenu))
        elif x0 >= milieu - 20:
            blocs_droite.append((y0, x0, contenu))
        else:
            blocs_centre.append((y0, x0, contenu))
    est_bicolonne = len(blocs_gauche) > 2 and len(blocs_droite) > 2
    if est_bicolonne:
        blocs_centre.sort(key=lambda b: (b[0], b[1]))
        blocs_droite.sort(key=lambda b: (b[0], b[1]))
        blocs_gauche.sort(key=lambda b: (b[0], b[1]))
        tous = blocs_centre + blocs_droite + blocs_gauche
    else:
        tous = blocs_gauche + blocs_droite + blocs_centre
        tous.sort(key=lambda b: (round(b[0] / 8) * 8, b[1]))
    return "\\n".join(c.strip() for _, _, c in tous if c.strip())


def lire_cv(chemin: str) -> str:
    import fitz  # PyMuPDF'''
    src = src.replace(old, new)
    print("✓ Patch _page_vers_texte appliqué")
else:
    print("✓ _page_vers_texte déjà présent")

# Patch 2: _normaliser_texte_espace complète
if "_normaliser_texte_espace" not in src:
    old2 = "def _normaliser_nom_espace(texte: str) -> str:"
    new2 = '''def _normaliser_texte_espace(texte: str) -> str:
    import re as _re
    lignes = texte.splitlines()
    resultat = []
    for ligne in lignes:
        mots = ligne.strip().split()
        if len(mots) >= 4 and sum(1 for m in mots if len(m) == 1) / len(mots) > 0.7:
            groupes = _re.split(r"  +", ligne.strip())
            mots_reconst = []
            for g in groupes:
                tokens = g.strip().split()
                if not tokens:
                    continue
                if all(len(t) <= 2 for t in tokens):
                    mot = "".join(tokens)
                    mots_reconst.append(mot.capitalize() if mot.isupper() else mot)
                else:
                    mots_reconst.append(g.strip())
            resultat.append(" ".join(mots_reconst))
        else:
            resultat.append(ligne)
    return "\\n".join(resultat)


def _normaliser_nom_espace(texte: str) -> str:'''
    src = src.replace(old2, new2)
    print("✓ Patch _normaliser_texte_espace appliqué")
else:
    print("✓ _normaliser_texte_espace déjà présent")

# Patch 3: lire_cv utilise _page_vers_texte
if "_page_vers_texte(page)" not in src:
    old3 = '''                    page_text = page.get_text("text", sort=True)
                    if page_text and page_text.strip():
                        texte += _nettoyer_unicode(page_text) + "\\n"'''
    new3 = '''                    page_text = _page_vers_texte(page)
                    if page_text:
                        texte += _nettoyer_unicode(page_text) + "\\n"'''
    src = src.replace(old3, new3)
    print("✓ Patch lire_cv appliqué")
else:
    print("✓ lire_cv déjà patché")

# Patch 4: supprimer .txt du glob
src = src.replace(
    'glob.glob("*.pdf") + glob.glob("*.txt") +',
    'glob.glob("*.pdf") +'
)

open("extraire_spacy_r.py", "w", encoding="utf-8").write(src)
print("\\n✅ Fichier mis à jour avec succès!")
print(f"Taille: {len(src)} bytes")