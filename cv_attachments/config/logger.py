import logging
import os
from datetime import datetime

LOGS_DIR   = "logs"
LOG_FORMAT  = "%(asctime)s | %(levelname)-8s | %(message)s"
DATE_FORMAT = "%Y-%m-%d %H:%M:%S"

def setup_logger():
    os.makedirs(LOGS_DIR, exist_ok=True)
    today = datetime.now().strftime("%Y-%m-%d")
    logger = logging.getLogger("PFE_MAIL")
    logger.setLevel(logging.DEBUG)
    app_handler = logging.FileHandler(
        filename=f"{LOGS_DIR}/app_{today}.log",
        encoding="utf-8"
    )
    app_handler.setLevel(logging.DEBUG)
    app_handler.setFormatter(
        logging.Formatter(LOG_FORMAT, DATE_FORMAT)
    )
    error_handler = logging.FileHandler(
        filename=f"{LOGS_DIR}/errors_{today}.log",
        encoding="utf-8"
    )
    error_handler.setLevel(logging.ERROR)
    error_handler.setFormatter(
        logging.Formatter(LOG_FORMAT, DATE_FORMAT)
    )
    connexion_handler = logging.FileHandler(
        filename=f"{LOGS_DIR}/connexions_{today}.log",
        encoding="utf-8"
    )
    connexion_handler.setLevel(logging.INFO)
    connexion_handler.setFormatter(
        logging.Formatter(LOG_FORMAT, DATE_FORMAT)
    )
    console_handler = logging.StreamHandler()
    console_handler.setLevel(logging.DEBUG)
    console_handler.setFormatter(
        logging.Formatter(LOG_FORMAT, DATE_FORMAT)
    )
    if not logger.handlers:
        logger.addHandler(app_handler)
        logger.addHandler(error_handler)
        logger.addHandler(connexion_handler)
        logger.addHandler(console_handler)

    return logger
logger = setup_logger()

