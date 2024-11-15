import logging
import os

os.makedirs('_log', exist_ok=True)

def get_logger(name: str, filename: str) -> logging.Logger:

    logger = logging.getLogger(name)
    logger.propagate = False

    if not logger.hasHandlers():
        handler = logging.FileHandler(os.path.join("_log", filename))
        handler.setFormatter(
            logging.Formatter("%(asctime)s - %(levelname)s - %(message)s")
        )
        logger.addHandler(handler)
        logger.setLevel(logging.DEBUG)

    return logger