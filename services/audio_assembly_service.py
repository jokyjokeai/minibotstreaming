#!/usr/bin/env python3
"""
Service d'assemblage audio
Combine les fichiers audio du bot + enregistrements clients en un seul fichier
"""

import os
import subprocess
import json
from pathlib import Path
from logger_config import get_logger

logger = get_logger(__name__)

class AudioAssemblyService:
    """Assemble tous les fichiers audio d'un appel en un seul fichier WAV"""

    def __init__(self):
        # Chemins Asterisk (fixes, toujours les mêmes)
        self.bot_audio_path = "/var/lib/asterisk/sounds/minibot"
        self.recordings_path = "/var/spool/asterisk/recording"

        # Chemins relatifs au projet (détection automatique)
        project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        self.assembled_path = os.path.join(project_root, "assembled_audio")
        self.config_path = os.path.join(project_root, "audio_texts.json")

        # Créer le dossier d'assemblage s'il n'existe pas
        os.makedirs(self.assembled_path, exist_ok=True)

        # Charger les textes des messages audio
        with open(self.config_path, 'r', encoding='utf-8') as f:
            self.audio_texts = json.load(f)

    def assemble_call_audio(self, call_id, audio_sequence):
        """
        Assemble tous les fichiers audio d'un appel

        Args:
            call_id: ID de l'appel
            audio_sequence: Liste des fichiers audio dans l'ordre de lecture
                            Format: [{"type": "bot"|"client", "file": "intro.wav"|"test_*.wav", "timestamp": datetime}]

        Returns:
            str: Chemin du fichier assemblé ou None si erreur
        """
        try:
            logger.info(f"🎬 Assembling audio for call {call_id}")
            logger.info(f"📊 {len(audio_sequence)} audio segments to assemble")

            # 1. Construire la liste des fichiers dans l'ordre
            audio_files = []
            for item in audio_sequence:
                item_type = item.get("type")
                filename = item.get("file")

                if item_type == "bot":
                    # Fichier audio du bot (dans /var/lib/asterisk/sounds/minibot/)
                    file_path = f"{self.bot_audio_path}/{filename}"
                elif item_type == "client":
                    # Enregistrement client (dans /var/spool/asterisk/recording/)
                    file_path = f"{self.recordings_path}/{filename}"
                else:
                    logger.warning(f"⚠️  Unknown type: {item_type}")
                    continue

                # Vérifier que le fichier existe
                if os.path.exists(file_path):
                    audio_files.append(file_path)
                    logger.debug(f"  ✅ {item_type.upper()}: {filename}")
                else:
                    logger.warning(f"  ⚠️  File not found: {file_path}")

            if not audio_files:
                logger.error("❌ No audio files found to assemble")
                return None

            # 2. Nom du fichier de sortie
            output_file = f"{self.assembled_path}/full_call_assembled_{call_id}.wav"

            # 3. Utiliser sox pour concaténer tous les fichiers
            cmd = ["sox"] + audio_files + [output_file]

            logger.info(f"🔧 Running: sox {len(audio_files)} files -> {output_file}")
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)

            if result.returncode == 0:
                file_size = os.path.getsize(output_file) / 1024  # KB
                duration = self.get_audio_duration(output_file)
                logger.info(f"✅ Audio assembled successfully: {output_file}")
                logger.info(f"   Size: {file_size:.1f} KB | Duration: {duration:.1f}s | Files: {len(audio_files)}")
                return output_file
            else:
                logger.error(f"❌ sox failed: {result.stderr}")
                return None

        except Exception as e:
            logger.error(f"❌ Error assembling audio: {e}", exc_info=True)
            return None

    def get_audio_duration(self, file_path):
        """Obtient la durée d'un fichier audio avec soxi"""
        try:
            result = subprocess.run(
                ["soxi", "-D", file_path],
                capture_output=True,
                text=True,
                timeout=5
            )
            if result.returncode == 0:
                return float(result.stdout.strip())
            return 0.0
        except Exception as e:
            logger.warning(f"Could not get duration for {file_path}: {e}")
            return 0.0


# Singleton
audio_assembly_service = AudioAssemblyService()
