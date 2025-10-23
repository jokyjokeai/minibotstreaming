#!/usr/bin/env python3
"""
Service d'Enregistrement Post-Appel - MiniBotPanel v2
Traite les enregistrements complets MixMonitor avec transcription Vosk complète
Compatible avec streaming temps réel + enregistrement complet
"""

import os
import json
import subprocess
import tempfile
from pathlib import Path
from datetime import datetime
from typing import Optional, Dict, List, Tuple
import requests

# Ajouter le répertoire parent au PYTHONPATH pour les imports
import sys
from pathlib import Path
current_dir = Path(__file__).parent
parent_dir = current_dir.parent
sys.path.insert(0, str(parent_dir))

from logger_config import get_logger
from config import RECORDINGS_PATH

logger = get_logger(__name__)

class PostCallRecordingService:
    """
    Service de traitement post-appel pour enregistrements complets
    """

    def __init__(self):
        self.logger = get_logger(f"{__name__}.PostCallRecordingService")

        # Chemins
        self.recordings_path = RECORDINGS_PATH
        project_root = Path(__file__).parent.parent
        self.transcripts_path = project_root / "transcripts"
        self.audio_texts_path = project_root / "audio_texts.json"
        
        # Créer répertoires si nécessaires
        self.transcripts_path.mkdir(exist_ok=True)
        
        # Charger audio_texts.json pour mapping bot
        self.audio_texts = {}
        if self.audio_texts_path.exists():
            with open(self.audio_texts_path, 'r', encoding='utf-8') as f:
                self.audio_texts = json.load(f)
        
        # Initialiser Vosk si disponible
        self.vosk_available = self._init_vosk()
        
        # Configuration VPS pour liens download
        self.vps_ip = self._detect_vps_ip()
        
        self.logger.info(f"🎙️ PostCallRecordingService initialized")
        self.logger.info(f"   📁 Recordings: {self.recordings_path}")
        self.logger.info(f"   📝 Transcripts: {self.transcripts_path}")
        self.logger.info(f"   🎯 Vosk available: {self.vosk_available}")
        self.logger.info(f"   🌐 VPS IP: {self.vps_ip}")

    def _init_vosk(self) -> bool:
        """Initialise Vosk pour transcription complète"""
        try:
            import vosk
            import wave
            
            # Vérifier modèle français
            vosk_model_path = Path(__file__).parent.parent / "vosk-model-fr"
            if vosk_model_path.exists():
                self.vosk_model = vosk.Model(str(vosk_model_path))
                self.logger.info("✅ Vosk français model loaded")
                return True
            else:
                self.logger.warning("⚠️ Vosk model français non trouvé dans vosk-model-fr/")
                return False
                
        except ImportError:
            self.logger.warning("⚠️ Vosk non installé (pip install vosk)")
            return False

    def _detect_vps_ip(self) -> str:
        """Détecte automatiquement l'IP du VPS"""
        try:
            # Méthode 1: API externe
            response = requests.get("https://httpbin.org/ip", timeout=5)
            if response.status_code == 200:
                ip = response.json().get("origin", "").split(",")[0].strip()
                if ip:
                    return ip
        except:
            pass
            
        try:
            # Méthode 2: Interface réseau locale
            import socket
            s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            s.connect(("8.8.8.8", 80))
            ip = s.getsockname()[0]
            s.close()
            return ip
        except:
            return "localhost"

    def process_complete_call(self, call_id: str, uniqueid: str, phone_number: str) -> Dict:
        """
        Traite un enregistrement complet après appel
        
        Args:
            call_id: ID de l'appel en base
            uniqueid: Unique ID Asterisk  
            phone_number: Numéro appelé
            
        Returns:
            Dict avec transcription complète et lien download
        """
        try:
            self.logger.info(f"🎬 Processing complete call recording: {call_id}")
            
            # 1. Localiser fichier MixMonitor
            recording_file = f"{self.recordings_path}/complete_call_{uniqueid}.wav"
            
            if not os.path.exists(recording_file):
                self.logger.error(f"❌ Recording file not found: {recording_file}")
                return {"success": False, "error": "Recording file not found"}
            
            # 2. Obtenir infos de base
            duration = self._get_audio_duration(recording_file)
            file_size = os.path.getsize(recording_file)
            
            self.logger.info(f"📊 Recording found: {file_size/1024:.1f} KB, {duration:.1f}s")
            
            # 3. Transcription complète avec Vosk
            transcription_result = self._transcribe_complete_audio(recording_file)
            
            # 4. Analyse conversation (séparation bot/client)
            conversation_analysis = self._analyze_conversation_timing(
                transcription_result, duration
            )
            
            # 5. Génération lien download sécurisé
            download_link = self._generate_secure_download_link(recording_file, call_id)
            
            # 6. Sauvegarde transcription complète
            transcript_data = {
                "call_id": call_id,
                "uniqueid": uniqueid,
                "phone_number": phone_number,
                "processed_at": datetime.now().isoformat(),
                "recording_info": {
                    "file": recording_file,
                    "duration_seconds": duration,
                    "file_size_bytes": file_size,
                    "format": "wav_16khz_mono_mixmonitor"
                },
                "transcription": transcription_result,
                "conversation_analysis": conversation_analysis,
                "download_link": download_link,
                "vosk_used": self.vosk_available
            }
            
            # Sauvegarder JSON détaillé
            transcript_file = self.transcripts_path / f"complete_call_{call_id}.json"
            with open(transcript_file, 'w', encoding='utf-8') as f:
                json.dump(transcript_data, f, indent=2, ensure_ascii=False)
            
            # Générer version texte lisible
            readable_transcript = self._generate_readable_transcript(transcript_data)
            readable_file = self.transcripts_path / f"complete_call_{call_id}.txt"
            with open(readable_file, 'w', encoding='utf-8') as f:
                f.write(readable_transcript)
            
            self.logger.info(f"✅ Complete call processed successfully")
            self.logger.info(f"   📝 Transcript: {transcript_file}")
            self.logger.info(f"   📄 Readable: {readable_file}")
            self.logger.info(f"   🔗 Download: {download_link}")
            
            return {
                "success": True,
                "transcript_json": str(transcript_file),
                "transcript_txt": str(readable_file),
                "download_link": download_link,
                "duration": duration,
                "conversation_turns": len(conversation_analysis.get("turns", [])),
                "transcription_quality": transcription_result.get("confidence", 0.0)
            }
            
        except Exception as e:
            self.logger.error(f"❌ Error processing complete call: {e}", exc_info=True)
            return {"success": False, "error": str(e)}

    def _transcribe_complete_audio(self, audio_file: str) -> Dict:
        """Transcription complète avec Vosk"""
        if not self.vosk_available:
            return {
                "text": "[Transcription non disponible - Vosk non installé]",
                "confidence": 0.0,
                "segments": []
            }
        
        try:
            import vosk
            import wave
            
            self.logger.info(f"🎙️ Starting complete transcription with Vosk...")
            
            with wave.open(audio_file, 'rb') as wf:
                # Vérifier format
                if wf.getsampwidth() != 2 or wf.getnchannels() != 1:
                    self.logger.warning("⚠️ Audio format non optimal pour Vosk")
                
                # Recognizer Vosk
                rec = vosk.KaldiRecognizer(self.vosk_model, wf.getframerate())
                rec.SetWords(True)
                
                segments = []
                full_text_parts = []
                
                # Traitement par chunks avec timeline
                chunk_duration = 4000  # 4000 frames
                current_time = 0.0
                frame_rate = wf.getframerate()
                
                while True:
                    data = wf.readframes(chunk_duration)
                    if len(data) == 0:
                        break
                    
                    if rec.AcceptWaveform(data):
                        result = json.loads(rec.Result())
                        if result.get('text'):
                            segment = {
                                "start_time": current_time,
                                "end_time": current_time + (chunk_duration / frame_rate),
                                "text": result['text'],
                                "confidence": result.get('confidence', 0.8),
                                "words": result.get('word', [])
                            }
                            segments.append(segment)
                            full_text_parts.append(result['text'])
                    
                    current_time += chunk_duration / frame_rate
                
                # Résultat final
                final_result = json.loads(rec.FinalResult())
                if final_result.get('text'):
                    segment = {
                        "start_time": current_time,
                        "end_time": current_time + 2.0,
                        "text": final_result['text'],
                        "confidence": final_result.get('confidence', 0.8),
                        "words": final_result.get('word', [])
                    }
                    segments.append(segment)
                    full_text_parts.append(final_result['text'])
                
                full_text = ' '.join(full_text_parts).strip()
                avg_confidence = sum(s.get('confidence', 0.8) for s in segments) / len(segments) if segments else 0.0
                
                self.logger.info(f"✅ Transcription complete: {len(full_text)} chars, {len(segments)} segments")
                
                return {
                    "text": full_text,
                    "confidence": avg_confidence,
                    "segments": segments,
                    "total_segments": len(segments),
                    "method": "vosk_complete"
                }
                
        except Exception as e:
            self.logger.error(f"❌ Vosk transcription failed: {e}")
            return {
                "text": f"[Erreur transcription: {e}]",
                "confidence": 0.0,
                "segments": []
            }

    def _analyze_conversation_timing(self, transcription: Dict, total_duration: float) -> Dict:
        """
        Analyse temporelle pour séparer bot/client dans la conversation
        """
        try:
            segments = transcription.get("segments", [])
            if not segments:
                return {"turns": [], "bot_duration": 0.0, "client_duration": 0.0}
            
            turns = []
            bot_total_time = 0.0
            client_total_time = 0.0
            
            # Heuristique simple : segments courts = bot, segments longs = client
            for i, segment in enumerate(segments):
                duration = segment.get("end_time", 0) - segment.get("start_time", 0)
                text = segment.get("text", "")
                confidence = segment.get("confidence", 0.8)
                
                # Logique de classification bot vs client
                # Bot: phrases courtes, mots clés connus, haute confiance
                # Client: phrases longues, hésitations, confidence variable
                
                is_bot = self._classify_speaker(text, duration, confidence)
                speaker = "BOT" if is_bot else "CLIENT"
                
                if is_bot:
                    bot_total_time += duration
                else:
                    client_total_time += duration
                
                turn = {
                    "turn_number": i + 1,
                    "speaker": speaker,
                    "start_time": segment.get("start_time", 0),
                    "end_time": segment.get("end_time", 0),
                    "duration": duration,
                    "text": text,
                    "confidence": confidence,
                    "classification_score": self._get_classification_score(text, duration, confidence)
                }
                
                turns.append(turn)
            
            return {
                "turns": turns,
                "total_turns": len(turns),
                "bot_duration": bot_total_time,
                "client_duration": client_total_time,
                "bot_ratio": bot_total_time / total_duration if total_duration > 0 else 0,
                "client_ratio": client_total_time / total_duration if total_duration > 0 else 0
            }
            
        except Exception as e:
            self.logger.error(f"❌ Conversation analysis failed: {e}")
            return {"turns": [], "error": str(e)}

    def _classify_speaker(self, text: str, duration: float, confidence: float) -> bool:
        """
        Classifie si un segment est du bot ou du client
        
        Returns:
            True si bot, False si client
        """
        # Mots-clés typiques du bot (depuis audio_texts.json)
        bot_keywords = [
            "bonjour", "thierry", "france patrimoine", "association",
            "merci", "parfait", "excellent", "intéressé", "rendez-vous",
            "disponible", "bonne journée", "au revoir"
        ]
        
        text_lower = text.lower()
        
        # Score bot
        bot_score = 0
        
        # Critère 1: Mots-clés
        for keyword in bot_keywords:
            if keyword in text_lower:
                bot_score += 2
        
        # Critère 2: Durée (bot généralement plus court)
        if duration < 3.0:
            bot_score += 1
        elif duration > 8.0:
            bot_score -= 2
            
        # Critère 3: Confiance (bot généralement plus claire)
        if confidence > 0.9:
            bot_score += 1
        elif confidence < 0.6:
            bot_score -= 1
            
        # Critère 4: Structure (bot plus formel)
        if any(marker in text_lower for marker in ["?", ".", "!"]):
            bot_score += 1
            
        # Critère 5: Hésitations (typique client)
        if any(hesitation in text_lower for hesitation in ["euh", "hm", "ben", "alors"]):
            bot_score -= 2
        
        return bot_score > 0

    def _get_classification_score(self, text: str, duration: float, confidence: float) -> float:
        """Score de confiance de la classification (0-1)"""
        # Facteurs de confiance
        factors = []
        
        # Longueur du texte
        if len(text) > 10:
            factors.append(0.8)
        else:
            factors.append(0.4)
            
        # Durée
        if 1.0 < duration < 10.0:
            factors.append(0.9)
        else:
            factors.append(0.6)
            
        # Confiance Vosk
        factors.append(min(confidence, 1.0))
        
        return sum(factors) / len(factors)

    def _generate_secure_download_link(self, file_path: str, call_id: str) -> str:
        """Génère lien de téléchargement sécurisé avec token"""
        try:
            import secrets
            import hashlib
            
            # Token sécurisé temporaire (valide 24h)
            timestamp = int(datetime.now().timestamp())
            secret_key = f"{call_id}_{timestamp}_minibotpanel"
            token = hashlib.sha256(secret_key.encode()).hexdigest()[:16]
            
            # URL sécurisée
            download_url = f"https://{self.vps_ip}/api/downloads/call-audio/{call_id}?token={token}&expires={timestamp + 86400}"
            
            # Sauvegarder token pour validation (cache simple)
            tokens_file = self.transcripts_path / "download_tokens.json"
            tokens_data = {}
            
            if tokens_file.exists():
                with open(tokens_file, 'r') as f:
                    tokens_data = json.load(f)
            
            tokens_data[call_id] = {
                "token": token,
                "expires": timestamp + 86400,
                "file_path": file_path,
                "created": timestamp
            }
            
            with open(tokens_file, 'w') as f:
                json.dump(tokens_data, f, indent=2)
            
            return download_url
            
        except Exception as e:
            self.logger.error(f"❌ Token generation failed: {e}")
            return f"http://{self.vps_ip}/static/call-audio/{call_id}.wav"

    def _generate_readable_transcript(self, transcript_data: Dict) -> str:
        """Génère transcription lisible format texte"""
        
        call_id = transcript_data.get("call_id", "unknown")
        phone = transcript_data.get("phone_number", "unknown") 
        duration = transcript_data.get("recording_info", {}).get("duration_seconds", 0)
        
        readable = f"""
TRANSCRIPTION COMPLÈTE D'APPEL - MiniBotPanel v2
===============================================

📞 Appel ID: {call_id}
📱 Numéro: {phone}
⏱️  Durée: {duration:.1f} secondes
📅 Traité le: {transcript_data.get('processed_at', 'unknown')}
🎙️  Méthode: {transcript_data.get('transcription', {}).get('method', 'unknown')}

CONVERSATION:
=============

"""
        
        # Ajouter conversation turn by turn
        conversation = transcript_data.get("conversation_analysis", {})
        turns = conversation.get("turns", [])
        
        for turn in turns:
            speaker = turn.get("speaker", "UNKNOWN")
            time_start = turn.get("start_time", 0)
            text = turn.get("text", "")
            confidence = turn.get("confidence", 0) * 100
            
            readable += f"[{time_start:06.1f}s] {speaker:6} ({confidence:04.1f}%): {text}\n"
        
        # Statistiques
        bot_duration = conversation.get("bot_duration", 0)
        client_duration = conversation.get("client_duration", 0)
        bot_ratio = conversation.get("bot_ratio", 0) * 100
        client_ratio = conversation.get("client_ratio", 0) * 100
        
        readable += f"""

STATISTIQUES:
=============
• Total tours de parole: {len(turns)}
• Temps bot: {bot_duration:.1f}s ({bot_ratio:.1f}%)
• Temps client: {client_duration:.1f}s ({client_ratio:.1f}%)
• Lien téléchargement: {transcript_data.get('download_link', 'N/A')}

---
Généré par MiniBotPanel v2 - Transcription post-appel
"""
        
        return readable

    def _get_audio_duration(self, file_path: str) -> float:
        """Obtient la durée d'un fichier audio avec soxi"""
        try:
            result = subprocess.run(
                ["soxi", "-D", file_path],
                capture_output=True,
                text=True,
                timeout=10
            )
            if result.returncode == 0:
                return float(result.stdout.strip())
            return 0.0
        except Exception as e:
            self.logger.warning(f"Could not get duration for {file_path}: {e}")
            return 0.0

    def get_service_status(self) -> Dict:
        """Retourne le statut du service"""
        return {
            "available": True,
            "vosk_available": self.vosk_available,
            "recordings_path": self.recordings_path,
            "transcripts_path": str(self.transcripts_path),
            "vps_ip": self.vps_ip,
            "audio_texts_loaded": len(self.audio_texts) > 0
        }


# Instance globale
post_call_recording_service = PostCallRecordingService()

def process_call_recording(call_id: str, uniqueid: str, phone_number: str) -> Dict:
    """
    Fonction utilitaire pour traiter un enregistrement post-appel
    
    Args:
        call_id: ID de l'appel
        uniqueid: Unique ID Asterisk
        phone_number: Numéro appelé
        
    Returns:
        Dict avec résultats du traitement
    """
    return post_call_recording_service.process_complete_call(call_id, uniqueid, phone_number)


if __name__ == "__main__":
    # Test du service
    service = PostCallRecordingService()
    
    print("🎙️ Testing Post-Call Recording Service...")
    print(f"📊 Status: {service.get_service_status()}")
    
    # Test avec fichier exemple (si disponible)
    test_file = "/var/spool/asterisk/recording/complete_call_test.wav"
    if os.path.exists(test_file):
        result = service.process_complete_call("test_call", "test_unique", "33123456789")
        print(f"✅ Test result: {result}")
    else:
        print("ℹ️  No test recording available")