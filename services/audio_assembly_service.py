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
        Assemble tous les fichiers audio d'un appel avec amplification des réponses clients

        Args:
            call_id: ID de l'appel
            audio_sequence: Liste des fichiers audio dans l'ordre de lecture
                            Format: [{"type": "bot"|"client", "file": "intro.wav"|"test_*.wav", "timestamp": datetime}]

        Returns:
            str: Chemin du fichier assemblé ou None si erreur
        """
        temp_files = []  # Pour nettoyer après
        try:
            logger.info(f"🎬 Assembling audio for call {call_id}")
            logger.info(f"📊 {len(audio_sequence)} audio segments to assemble")

            # 1. Construire la liste des fichiers dans l'ordre avec amplification des clients
            audio_files = []
            for idx, item in enumerate(audio_sequence):
                item_type = item.get("type")
                filename = item.get("file")

                if item_type == "bot":
                    # Fichier audio du bot (dans /var/lib/asterisk/sounds/minibot/)
                    file_path = f"{self.bot_audio_path}/{filename}"

                    # Vérifier que le fichier existe
                    if os.path.exists(file_path):
                        audio_files.append(file_path)
                        logger.debug(f"  ✅ BOT: {filename}")
                    else:
                        logger.warning(f"  ⚠️  Bot file not found: {file_path}")

                elif item_type == "client":
                    # Enregistrement client (dans /var/spool/asterisk/recording/)
                    original_path = f"{self.recordings_path}/{filename}"

                    # Vérifier que le fichier existe
                    if not os.path.exists(original_path):
                        logger.warning(f"  ⚠️  Client file not found: {original_path}")
                        continue

                    # Créer une version amplifiée temporaire (+8dB pour entendre mieux les clients)
                    temp_amplified = f"{self.assembled_path}/temp_amplified_{idx}_{filename}"
                    temp_files.append(temp_amplified)

                    # Amplifier avec sox : vol +8dB
                    amplify_cmd = [
                        "sox", original_path, temp_amplified,
                        "vol", "8dB"  # Augmentation de +8dB (recommandé pour voix téléphone)
                    ]

                    result = subprocess.run(amplify_cmd, capture_output=True, text=True, timeout=10)

                    if result.returncode == 0:
                        audio_files.append(temp_amplified)
                        logger.debug(f"  ✅ CLIENT (amplified +8dB): {filename}")
                    else:
                        logger.warning(f"  ⚠️  Amplification failed for {filename}, using original")
                        audio_files.append(original_path)  # Fallback sur original
                else:
                    logger.warning(f"⚠️  Unknown type: {item_type}")
                    continue

            if not audio_files:
                logger.error("❌ No audio files found to assemble")
                return None

            # 2. Nom du fichier de sortie
            output_file = f"{self.assembled_path}/full_call_assembled_{call_id}.wav"

            # 3. Utiliser sox pour concaténer tous les fichiers (bot normal + client amplifié)
            cmd = ["sox"] + audio_files + [output_file]

            logger.info(f"🔧 Running: sox {len(audio_files)} files -> {output_file}")
            logger.info(f"   (Client audio amplified +8dB for better clarity)")
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
        finally:
            # Nettoyer les fichiers temporaires amplifiés
            for temp_file in temp_files:
                try:
                    if os.path.exists(temp_file):
                        os.remove(temp_file)
                        logger.debug(f"🧹 Cleaned temp file: {temp_file}")
                except Exception as e:
                    logger.warning(f"Could not remove temp file {temp_file}: {e}")

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
