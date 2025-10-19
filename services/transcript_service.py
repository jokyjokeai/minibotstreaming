#!/usr/bin/env python3
"""
Service de génération de transcription complète
Combine les textes du bot + transcriptions Whisper en un rapport complet
"""

import json
from datetime import datetime
from pathlib import Path
from logger_config import get_logger

logger = get_logger(__name__)

class TranscriptService:
    """Génère des transcriptions complètes d'appels"""

    def __init__(self):
        # Détecter automatiquement le répertoire du projet
        import os
        project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        self.config_path = os.path.join(project_root, "audio_texts.json")
        self.output_path = os.path.join(project_root, "transcripts")

        # Créer le dossier de transcriptions s'il n'existe pas
        Path(self.output_path).mkdir(parents=True, exist_ok=True)

        # Charger les textes des messages audio
        with open(self.config_path, 'r', encoding='utf-8') as f:
            self.audio_texts = json.load(f)

    def generate_transcript(self, call_data, interactions):
        """
        Génère une transcription complète de l'appel

        Args:
            call_data: Dict avec les infos de l'appel (call_id, phone, duration, etc.)
            interactions: Liste des interactions dans l'ordre
                         Format: [{"speaker": "bot"|"client", "audio_file": "intro"|"test_*.wav",
                                   "transcription": "...", "sentiment": "positive", "timestamp": ...}]

        Returns:
            dict: Transcription complète formatée
        """
        try:
            call_id = call_data.get("call_id")
            logger.info(f"📝 Generating complete transcript for call {call_id}")

            transcript = {
                "call_id": call_id,
                "phone_number": call_data.get("phone_number"),
                "campaign_id": call_data.get("campaign_id"),
                "amd_result": call_data.get("amd_result"),
                "duration_seconds": call_data.get("duration"),
                "started_at": call_data.get("started_at").isoformat() if call_data.get("started_at") else None,
                "ended_at": call_data.get("ended_at").isoformat() if call_data.get("ended_at") else None,
                "final_sentiment": call_data.get("final_sentiment"),
                "interested": call_data.get("interested"),
                "assembled_audio": call_data.get("assembled_audio"),
                "conversation": []
            }

            # Construire la conversation
            for idx, interaction in enumerate(interactions, 1):
                if interaction["speaker"] == "bot":
                    # Message du bot
                    audio_key = interaction["audio_file"].replace(".wav", "")
                    text_info = self.audio_texts.get(audio_key, {})

                    entry = {
                        "turn": idx,
                        "speaker": "BOT",
                        "audio_file": interaction["audio_file"],
                        "text": text_info.get("text", f"[Audio: {audio_key}]"),
                        "duration": text_info.get("duration", 0),
                        "timestamp": interaction.get("timestamp")
                    }
                else:
                    # Réponse du client
                    entry = {
                        "turn": idx,
                        "speaker": "CLIENT",
                        "audio_file": interaction["audio_file"],
                        "transcription": interaction.get("transcription", ""),
                        "sentiment": interaction.get("sentiment", "unclear"),
                        "confidence": interaction.get("confidence", 0),
                        "timestamp": interaction.get("timestamp")
                    }

                transcript["conversation"].append(entry)

            # Sauvegarder en JSON
            output_file = f"{self.output_path}/transcript_{call_id}.json"
            with open(output_file, 'w', encoding='utf-8') as f:
                json.dump(transcript, f, indent=2, ensure_ascii=False)

            logger.info(f"✅ Transcript saved: {output_file}")

            # Générer aussi une version texte lisible
            text_output = self._generate_text_version(transcript)
            text_file = f"{self.output_path}/transcript_{call_id}.txt"
            with open(text_file, 'w', encoding='utf-8') as f:
                f.write(text_output)

            logger.info(f"✅ Text transcript saved: {text_file}")

            return transcript

        except Exception as e:
            logger.error(f"❌ Error generating transcript: {e}", exc_info=True)
            return None

    def _generate_text_version(self, transcript):
        """Génère une version texte lisible de la transcription"""
        lines = []
        lines.append("=" * 80)
        lines.append(f"TRANSCRIPTION COMPLÈTE DE L'APPEL")
        lines.append("=" * 80)
        lines.append(f"Call ID: {transcript['call_id']}")
        lines.append(f"Téléphone: {transcript['phone_number']}")
        lines.append(f"Durée: {transcript['duration_seconds']}s")
        lines.append(f"AMD: {transcript['amd_result']}")
        lines.append(f"Sentiment final: {transcript['final_sentiment']}")
        lines.append(f"Intéressé: {'Oui' if transcript['interested'] else 'Non'}")
        lines.append(f"Date: {transcript['started_at']}")
        lines.append("=" * 80)
        lines.append("")

        for entry in transcript["conversation"]:
            if entry["speaker"] == "BOT":
                lines.append(f"🤖 BOT (Tour {entry['turn']}):")
                lines.append(f"   Audio: {entry['audio_file']}")
                lines.append(f"   Texte: {entry['text']}")
                lines.append("")
            else:
                lines.append(f"👤 CLIENT (Tour {entry['turn']}):")
                lines.append(f"   Audio: {entry['audio_file']}")
                lines.append(f"   Transcription: {entry['transcription']}")
                lines.append(f"   Sentiment: {entry['sentiment']}")
                lines.append("")

        lines.append("=" * 80)
        lines.append(f"Audio complet assemblé: {transcript.get('assembled_audio', 'N/A')}")
        lines.append("=" * 80)

        return "\n".join(lines)


# Singleton
transcript_service = TranscriptService()
