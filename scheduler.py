import time
import schedule
from datetime import datetime
from mail.connector import connect_imap, disconnect_imap, ensure_connected
from mail.fetcher   import fetch_emails
from mail.parser    import parse_email
from config.logger  import logger

# ══════════════════════════════════════════════════════
# CONFIGURATION — modifie selon tes besoins
# ══════════════════════════════════════════════════════
INTERVAL_MINUTES = 1       # Fréquence de vérification
FORCE_ALL        = False   # True = récupère TOUS les emails (même déjà lus)

MAX_RETRIES  = 3           # Tentatives de connexion max
RETRY_DELAY  = 5           # Secondes entre chaque tentative
# ══════════════════════════════════════════════════════


# ── Compteurs globaux de session ──────────────────────
_session_stats = {
    "cycles":         0,
    "total_traites":  0,
    "total_fichiers": 0,
    "total_echecs":   0,
    "debut":          datetime.now(),
}


def connect_with_retry() -> object | None:
    """
    Tente de se connecter jusqu'à MAX_RETRIES fois.
    Retourne l'objet mail si succès, None si échec total.
    """
    for i in range(1, MAX_RETRIES + 1):
        try:
            logger.info(f"Tentative de connexion {i}/{MAX_RETRIES}...")
            mail = connect_imap()
            mail = ensure_connected(mail)
            logger.info("Connexion établie avec succès")
            return mail

        except Exception as e:
            logger.warning(f"Échec tentative {i}/{MAX_RETRIES} : {e}")
            if i < MAX_RETRIES:
                logger.info(f"Nouvelle tentative dans {RETRY_DELAY}s...")
                time.sleep(RETRY_DELAY)
            else:
                logger.error("Nombre maximum de tentatives atteint — abandon")
                return None


def print_session_stats():
    """Affiche les statistiques globales de la session."""
    duree = datetime.now() - _session_stats["debut"]
    heures, reste = divmod(int(duree.total_seconds()), 3600)
    minutes, secondes = divmod(reste, 60)

    logger.info("╔══════════════════════════════════════╗")
    logger.info("║        STATISTIQUES DE SESSION       ║")
    logger.info("╠══════════════════════════════════════╣")
    logger.info(f"║  Durée         : {heures:02d}h {minutes:02d}m {secondes:02d}s")
    logger.info(f"║  Cycles        : {_session_stats['cycles']}")
    logger.info(f"║  Emails traités: {_session_stats['total_traites']}")
    logger.info(f"║  Pièces jointes: {_session_stats['total_fichiers']}")
    logger.info(f"║  Échecs        : {_session_stats['total_echecs']}")
    logger.info("╚══════════════════════════════════════╝")


def check_emails():
    """
    Cycle principal :
      1. Connexion avec retry
      2. Récupération des emails (UNSEEN ou ALL)
      3. Parsing complet + sauvegarde pièces jointes
      4. Marquage comme LU (évite re-traitement)
      5. Résumé du cycle
      6. Déconnexion propre
    """
    _session_stats["cycles"] += 1
    cycle_num = _session_stats["cycles"]

    logger.info("=" * 42)
    logger.info(f"  CYCLE #{cycle_num} — {datetime.now().strftime('%d/%m/%Y %H:%M:%S')}")
    logger.info("=" * 42)

    mail      = None
    traites   = 0
    echecs    = 0
    fichiers  = 0

    try:
        # ── 1. Connexion ──────────────────────────────
        mail = connect_with_retry()

        if mail is None:
            logger.error(
                f"Impossible de se connecter après "
                f"{MAX_RETRIES} tentatives — cycle #{cycle_num} ignoré"
            )
            _session_stats["total_echecs"] += 1
            return

        # ── 2. Choix du filtre ────────────────────────
        filtre = "ALL" if FORCE_ALL else "UNSEEN"

        if FORCE_ALL:
            logger.warning("Mode FORCE_ALL actif — recuperation de TOUS les emails")

        # ── 3. Récupération des IDs ───────────────────
        email_ids = fetch_emails(mail, folder="INBOX", filter=filtre)

        # ── 4. Traitement de chaque email ─────────────
        if len(email_ids) == 0:
            logger.info("Aucun nouveau email — en attente du prochain cycle")

        else:
            logger.info(f"{len(email_ids)} email(s) a traiter")
            logger.info("-" * 42)

            for idx, eid in enumerate(email_ids, start=1):
                eid_str = eid.decode() if isinstance(eid, bytes) else str(eid)
                logger.info(f"[{idx}/{len(email_ids)}] Traitement email ID {eid_str}...")

                # Parsing complet + sauvegarde pièces jointes + marquage LU
                result = parse_email(mail, eid)

                if result:
                    traites  += 1
                    fichiers += len(result["fichiers"])
                    logger.info(f"  Email ID {eid_str} traite avec succes")
                else:
                    echecs += 1
                    logger.warning(f"  Echec traitement email ID {eid_str}")

                logger.info("-" * 42)

        # ── 5. Résumé du cycle ────────────────────────
        logger.info(f"Résumé cycle #{cycle_num}")
        logger.info(f"  Emails traites  : {traites}")
        logger.info(f"  Pieces jointes  : {fichiers}")
        if echecs:
            logger.warning(f"  Echecs          : {echecs}")

        # ── Mise à jour stats session ─────────────────
        _session_stats["total_traites"]  += traites
        _session_stats["total_fichiers"] += fichiers
        _session_stats["total_echecs"]   += echecs

    except Exception as e:
        logger.error(f"Erreur inattendue durant le cycle #{cycle_num} : {e}")
        _session_stats["total_echecs"] += 1

    finally:
        # ── 6. Déconnexion propre ─────────────────────
        if mail:
            disconnect_imap(mail)

    logger.info(f"Prochain cycle dans {INTERVAL_MINUTES} minute(s)\n")


def start_scheduler():
    """
    Point d'entrée principal.
    Lance un premier cycle immédiatement,
    puis planifie les suivants selon INTERVAL_MINUTES.
    """
    logger.info("=" * 42)
    logger.info("     SCHEDULER PFE — DEMARRAGE")
    logger.info("=" * 42)
    logger.info(f"Intervalle      : {INTERVAL_MINUTES} minute(s)")
    logger.info(f"Reconnexion     : {MAX_RETRIES} tentatives / {RETRY_DELAY}s d'intervalle")
    logger.info(f"Mode            : {'FORCE (tous)' if FORCE_ALL else 'Nouveaux seulement (UNSEEN)'}")
    logger.info("Ctrl+C pour arreter")
    logger.info("=" * 42 + "\n")

    # Premier cycle immédiat au démarrage
    check_emails()

    # Planification des cycles suivants
    schedule.every(INTERVAL_MINUTES).minutes.do(check_emails)

    while True:
        schedule.run_pending()
        time.sleep(30)


if __name__ == "__main__":
    try:
        start_scheduler()
    except KeyboardInterrupt:
        logger.info("Scheduler arrete par l'utilisateur")
        print_session_stats()
        print("\n[✓] A bientot !")