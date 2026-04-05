"""
injecter_elasticsearch.py
--------------------------
Supprime les anciens index, nettoie les JSONs et injecte dans Elasticsearch.

Usage :
    python injecter_elasticsearch.py           # nettoie + injecte
    python injecter_elasticsearch.py --reset   # supprime TOUT et repart de zéro
"""


import os
import sys
import json
from elasticsearch import Elasticsearch, helpers
from nettoyer_json import nettoyer_dossier

# =============================================================================
# CONFIGURATION — adapte l'IP de ta VM
# =============================================================================

ES_HOST = "http://127.0.0.1:9200"
INDEX_CVS      = "cvs"
DOSSIER_BRUT   = r"C:\Users\user\pfe_mails\resultats\pipeline_hybride"
DOSSIER_PROPRE = r"C:\Users\user\pfe_mails\resultats\json_propres"


# =============================================================================
# MAPPING PROPRE
# =============================================================================

MAPPING = {
    "settings": {
        "number_of_shards":   1,
        "number_of_replicas": 0,
    },
    "mappings": {
        "properties": {
            # ── Identifiant ───────────────────────────────────────────────────
            "cv_filename":         {"type": "keyword"},

            # ── Infos personnelles à plat ─────────────────────────────────────
            "nom":                 {"type": "text", "fields": {"keyword": {"type": "keyword"}}},
            "email":               {"type": "keyword"},
            "telephone":           {"type": "keyword"},
            "ville":               {"type": "keyword"},

            # ── Listes simples ────────────────────────────────────────────────
            "competences_techniques": {"type": "keyword"},
            "domaines_competence":    {"type": "text"},
            "langues":                {"type": "keyword"},

            # ── Sections imbriquées ───────────────────────────────────────────
            "formation": {
                "type": "nested",
                "properties": {
                    "ecole":      {"type": "text"},
                    "diplome":    {"type": "text"},
                    "domaine":    {"type": "text"},
                    "date_debut": {"type": "integer"},
                    "date_fin":   {"type": "integer"},
                }
            },
            "experiences": {
                "type": "nested",
                "properties": {
                    "entreprise":  {"type": "text"},
                    "poste":       {"type": "text"},
                    "date_debut":  {"type": "integer"},
                    "date_fin":    {"type": "integer"},
                    "description": {"type": "text"},
                }
            },
            "projets": {
                "type": "nested",
                "properties": {
                    "titre":        {"type": "text"},
                    "technologies": {"type": "keyword"},
                    "description":  {"type": "text"},
                }
            },
            "certificats": {
                "type": "nested",
                "properties": {
                    "titre":     {"type": "text"},
                    "organisme": {"type": "keyword"},
                    "date":      {"type": "integer"},
                }
            },
            "experiences_associatives": {
                "type": "nested",
                "properties": {
                    "titre": {"type": "text"},
                    "date":  {"type": "integer"},
                }
            },

            # ── Métadonnées ───────────────────────────────────────────────────
            "extraction_method":  {"type": "keyword"},
            "methode_utilisee":   {"type": "keyword"},
            "date_indexation":    {"type": "date"},
        }
    }
}


# =============================================================================
# CONNEXION
# =============================================================================

def connecter() -> Elasticsearch:
    es = Elasticsearch(ES_HOST)
    if not es.ping():
        raise ConnectionError(
            f"\n[ERREUR] Impossible de joindre Elasticsearch sur {ES_HOST}\n"
            f"  → Vérifie que ES est démarré sur ta VM : sudo systemctl start elasticsearch\n"
            f"  → Et que network.host: 0.0.0.0 est dans /etc/elasticsearch/elasticsearch.yml"
        )
    info = es.info()
    print(f"  ✓ Connecté — Elasticsearch v{info['version']['number']} sur {ES_HOST}")
    return es


# =============================================================================
# GESTION DE L'INDEX
# =============================================================================

def supprimer_anciens_index(es: Elasticsearch):
    """Supprime tous les index liés aux CVs pour repartir proprement."""
    index_a_supprimer = ["cvs", "cvs_structured", "cv", "candidats"]
    for idx in index_a_supprimer:
        if es.indices.exists(index=idx):
            es.indices.delete(index=idx)
            print(f"  ✓ Index '{idx}' supprimé")


def creer_index(es: Elasticsearch):
    if es.indices.exists(index=INDEX_CVS):
        print(f"  Index '{INDEX_CVS}' existe déjà — ajout des documents")
        return
    es.indices.create(index=INDEX_CVS, body=MAPPING)
    print(f"  ✓ Index '{INDEX_CVS}' créé avec le mapping")


# =============================================================================
# INJECTION
# =============================================================================

def generer_actions(docs: list):
    for doc in docs:
        yield {
            "_index": INDEX_CVS,
            "_id":    doc.get("cv_filename", "").replace(" ", "_"),
            "_source": doc,
        }


def injecter(es: Elasticsearch, docs: list) -> tuple[int, int]:
    succes, erreurs = helpers.bulk(
        es,
        generer_actions(docs),
        raise_on_error=False,
    )
    nb_erreurs = len(erreurs) if isinstance(erreurs, list) else 0
    return succes, nb_erreurs


# =============================================================================
# PIPELINE COMPLET
# =============================================================================

def pipeline_complet(reset: bool = False):
    print("\n" + "=" * 55)
    print("   PIPELINE : Nettoyage + Injection Elasticsearch")
    print("=" * 55)

    # ── Étape 1 : Connexion ───────────────────────────────────────────────────
    print("\n[1/4] Connexion à Elasticsearch...")
    try:
        es = connecter()
    except ConnectionError as e:
        print(e)
        return

    # ── Étape 2 : Reset des anciens index ────────────────────────────────────
    if reset:
        print("\n[2/4] Suppression des anciens index...")
        supprimer_anciens_index(es)
    else:
        print("\n[2/4] Conservation des index existants (--reset pour tout effacer)")

    # ── Étape 3 : Création de l'index propre ─────────────────────────────────
    print(f"\n[3/4] Création de l'index '{INDEX_CVS}'...")
    creer_index(es)

    # ── Étape 4 : Nettoyage + injection ──────────────────────────────────────
    print("\n[4/4] Nettoyage des JSONs et injection...")
    docs = nettoyer_dossier(DOSSIER_BRUT, DOSSIER_PROPRE)

    if not docs:
        print("[ERREUR] Aucun document à injecter.")
        return

    nb_succes, nb_erreurs = injecter(es, docs)

    # ── Résumé ────────────────────────────────────────────────────────────────
    es.indices.refresh(index=INDEX_CVS)
    total = es.count(index=INDEX_CVS)["count"]

    print("\n" + "=" * 55)
    print("  RÉSUMÉ FINAL")
    print("=" * 55)
    print(f"  Documents nettoyés   : {len(docs)}")
    print(f"  Injectés avec succès : {nb_succes}")
    print(f"  Erreurs              : {nb_erreurs}")
    print(f"  Total dans l'index   : {total} document(s)")
    print(f"  Index                : {INDEX_CVS}")
    print(f"  Vérification         : {ES_HOST}/{INDEX_CVS}/_search?pretty")
    print("=" * 55)


# =============================================================================
# POINT D'ENTRÉE
# =============================================================================

if __name__ == "__main__":
    reset = "--reset" in sys.argv
    if reset:
        print("[INFO] Mode --reset : tous les anciens index CVs seront supprimés")
    pipeline_complet(reset=reset)