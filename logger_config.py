#!/usr/bin/env python3
"""
Configuration logging centralisée pour MiniBotPanel v2
Utilisé par tous les modules du projet
"""

import logging
import os
from datetime import datetime
from logging.handlers import RotatingFileHandler

def setup_logger(name: str, log_file: str = None, level=logging.INFO):
    """
    Configure un logger avec fichier + console

    Args:
        name: Nom du logger (généralement __name__)
        log_file: Chemin fichier log (auto si None)
        level: Niveau de log (DEBUG, INFO, WARNING, ERROR)

    Returns:
        Logger configuré
    """

    # Détecter automatiquement le répertoire du projet
    current_file = os.path.abspath(__file__)
    project_root = os.path.dirname(current_file)
    log_dir = os.path.join(project_root, "logs")
    os.makedirs(log_dir, exist_ok=True)

    # Nom fichier automatique si non fourni
    if log_file is None:
        # Utiliser le nom du module pour le fichier
        module_name = name.replace('.', '_') if name != '__main__' else 'main'

        # Un seul fichier de log principal pour tout le projet
        # Plus facile à suivre et évite la fragmentation
        log_file = f"{log_dir}/minibot_{datetime.now().strftime('%Y%m%d')}.log"

    # Créer logger
    logger = logging.getLogger(name)
    logger.setLevel(level)

    # Éviter duplication si déjà configuré
    if logger.handlers:
        return logger

    # Format détaillé pour fichier
    file_formatter = logging.Formatter(
        '%(asctime)s | %(name)s | %(levelname)-8s | %(funcName)s:%(lineno)d | %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )

    # Handler fichier (rotation 50MB, 10 fichiers max)
    file_handler = RotatingFileHandler(
        log_file,
        maxBytes=50*1024*1024,  # 50MB pour capturer plus d'infos
        backupCount=10,
        encoding='utf-8'
    )
    file_handler.setLevel(logging.DEBUG)  # Tout dans le fichier
    file_handler.setFormatter(file_formatter)

    # Handler console (plus simple et coloré)
    console_handler = logging.StreamHandler()
    console_handler.setLevel(logging.INFO)  # Moins verbeux en console
    console_formatter = logging.Formatter(
        '%(asctime)s | %(levelname)-8s | %(message)s',
        datefmt='%H:%M:%S'
    )
    console_handler.setFormatter(console_formatter)

    # Ajouter handlers
    logger.addHandler(file_handler)
    logger.addHandler(console_handler)

    # Log d'initialisation
    logger.debug(f"Logger initialized for module: {name}")

    return logger

def get_logger(name: str):
    """Récupère ou crée un logger"""
    return setup_logger(name)
