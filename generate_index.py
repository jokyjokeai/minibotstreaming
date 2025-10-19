#!/usr/bin/env python3
"""
Génère un fichier index.csv référençant tous les fichiers du projet
avec leur chemin, nom et description
"""

import os
import csv
from pathlib import Path

# Configuration
# Détecter automatiquement le répertoire du projet
PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))
OUTPUT_FILE = os.path.join(PROJECT_ROOT, "index.csv")

# Dossiers à exclure
EXCLUDE_DIRS = {
    "__pycache__",
    "logs",
    "transcripts",
    "assembled_audio",
    ".git",
    "venv",
    "env",
    ".cache",
    "node_modules"
}

# Extensions à inclure
INCLUDE_EXTENSIONS = {
    ".py", ".sh", ".md", ".json", ".txt", ".sql",
    ".yaml", ".yml", ".conf", ".ini", ".csv"
}

# Descriptions des fichiers (mappé manuellement)
FILE_DESCRIPTIONS = {
    # Racine
    "main.py": "Point d'entrée FastAPI - Démarre l'API web et les routes",
    "robot_ari.py": "Robot principal - Gère les appels via Asterisk ARI",
    "scenarios.py": "Définition des scénarios d'appel (production et test)",
    "scenario_cache.py": "Pré-chargement et validation des scénarios au démarrage",
    "database.py": "Configuration SQLAlchemy - Connexion PostgreSQL",
    "models.py": "Modèles de données SQLAlchemy (Call, Contact, Campaign, etc.)",
    "config.py": "Configuration générale du système (BDD, Asterisk, etc.)",
    "logger_config.py": "Configuration centralisée des logs",
    "requirements.txt": "Dépendances Python du projet",
    "audio_texts.json": "Transcriptions Whisper des fichiers audio du bot",

    # Scripts système
    "start_system.sh": "Lance tous les services (robot_ari, API, batch_caller)",
    "stop_system.sh": "Arrête tous les services en cours",
    "monitor_logs.sh": "Affiche les logs en temps réel (tail -f)",

    # Dossier system/
    "system/install.py": "Installation complète du système (Asterisk, PostgreSQL, dépendances)",
    "system/uninstall.py": "Désinstallation complète du système",
    "system/setup_audio.sh": "Conversion et copie des fichiers audio + transcription Whisper",
    "system/import_contacts.py": "Import de contacts depuis CSV vers PostgreSQL",
    "system/export_contacts.py": "Export de contacts depuis PostgreSQL vers CSV",
    "system/launch_campaign.py": "CLI pour lancer des campagnes d'appels",
    "system/batch_caller.py": "Service de gestion des appels en batch avec throttling",
    "system/cleanup_recordings.sh": "Nettoyage automatique des enregistrements anciens",

    # Dossier api/
    "api/__init__.py": "Initialisation du package API",
    "api/calls.py": "Routes API pour gérer les appels individuels",
    "api/campaigns.py": "Routes API pour gérer les campagnes d'appels",
    "api/stats.py": "Routes API pour les statistiques et analytics",

    # Dossier services/
    "services/__init__.py": "Initialisation du package services",
    "services/whisper_service.py": "Service de transcription audio avec Whisper (faster-whisper)",
    "services/sentiment_service.py": "Analyse de sentiment par mots-clés (positif/négatif/interrogatif)",
    "services/call_launcher.py": "Service de lancement d'appels via ARI",
    "services/audio_assembly_service.py": "Assemblage des fichiers audio bot + client en un seul WAV",
    "services/transcript_service.py": "Génération de transcriptions complètes (JSON et TXT)",

    # Dossier read/ (documentation)
    "read/README.md": "Documentation principale du projet",
    "read/GUIDE_COMPLET.md": "Guide complet d'installation, configuration et utilisation (installation, setup audio, campagnes, monitoring, troubleshooting)",
    "read/VERIFICATION_INSTALL.md": "Guide de vérification post-installation",
    "read/CONFIGURATION_CALLER_ID.md": "Configuration du Caller ID pour l'émission d'appels",
    "read/SYSTEME_QUEUE.md": "Documentation du système de queue d'appels",

    # Fichiers Claude Code
    ".claude/settings.local.json": "Configuration locale de Claude Code",
}

def get_relative_path(file_path):
    """Retourne le chemin relatif depuis la racine du projet"""
    return os.path.relpath(file_path, PROJECT_ROOT)

def get_directory(file_path):
    """Retourne le chemin du dossier parent"""
    rel_path = get_relative_path(file_path)
    directory = os.path.dirname(rel_path)
    return directory if directory else "."

def get_filename(file_path):
    """Retourne le nom du fichier"""
    return os.path.basename(file_path)

def get_description(file_path):
    """Retourne la description du fichier"""
    rel_path = get_relative_path(file_path)

    # Description explicite si disponible
    if rel_path in FILE_DESCRIPTIONS:
        return FILE_DESCRIPTIONS[rel_path]

    # Descriptions génériques basées sur l'emplacement/nom
    filename = get_filename(file_path)

    if filename == "__init__.py":
        return "Initialisation du package Python"
    elif filename.endswith(".pyc"):
        return "Bytecode Python compilé"
    elif filename.endswith(".md"):
        return "Documentation Markdown"
    elif filename.endswith(".json"):
        return "Fichier de configuration JSON"
    elif filename.endswith(".txt"):
        return "Fichier texte"
    elif filename.endswith(".sh"):
        return "Script shell Bash"
    elif filename.endswith(".sql"):
        return "Script SQL"
    elif filename.endswith(".csv"):
        return "Fichier CSV (données tabulaires)"
    elif filename.endswith(".yaml") or filename.endswith(".yml"):
        return "Fichier de configuration YAML"

    return "Fichier du projet"

def should_include_file(file_path):
    """Détermine si un fichier doit être inclus dans l'index"""
    # Exclure les dossiers spécifiques
    for exclude_dir in EXCLUDE_DIRS:
        if f"/{exclude_dir}/" in file_path or file_path.endswith(f"/{exclude_dir}"):
            return False

    # Inclure seulement les extensions définies
    ext = os.path.splitext(file_path)[1]
    return ext in INCLUDE_EXTENSIONS

def generate_index():
    """Génère le fichier index.csv"""
    print("=" * 80)
    print("GÉNÉRATION DE L'INDEX DU PROJET")
    print("=" * 80)
    print(f"Racine: {PROJECT_ROOT}")
    print(f"Output: {OUTPUT_FILE}")
    print()

    files_data = []

    # Parcourir tous les fichiers du projet
    for root, dirs, files in os.walk(PROJECT_ROOT):
        # Exclure les dossiers à ignorer
        dirs[:] = [d for d in dirs if d not in EXCLUDE_DIRS]

        for filename in files:
            file_path = os.path.join(root, filename)

            if should_include_file(file_path):
                directory = get_directory(file_path)
                name = get_filename(file_path)
                description = get_description(file_path)

                files_data.append({
                    "directory": directory,
                    "filename": name,
                    "description": description
                })

    # Trier par chemin puis par nom
    files_data.sort(key=lambda x: (x["directory"], x["filename"]))

    # Écrire le CSV
    with open(OUTPUT_FILE, 'w', newline='', encoding='utf-8') as csvfile:
        fieldnames = ['directory', 'filename', 'description']
        writer = csv.DictWriter(csvfile, fieldnames=fieldnames)

        # En-tête
        writer.writeheader()

        # Données
        for file_data in files_data:
            writer.writerow(file_data)

    print(f"✅ Index généré avec {len(files_data)} fichiers")
    print(f"📄 Fichier créé: {OUTPUT_FILE}")
    print()

    # Afficher un aperçu
    print("📊 APERÇU (10 premiers fichiers):")
    print("-" * 80)
    for i, file_data in enumerate(files_data[:10], 1):
        print(f"{i}. {file_data['directory']}/{file_data['filename']}")
        print(f"   → {file_data['description']}")
        print()

if __name__ == "__main__":
    generate_index()
