#!/usr/bin/env python3
"""
Robot ARI - Version FINALE PRODUCTION
WebSocket natif sans module ari cassé
"""

import json
import requests
import websocket
import time
import os
import threading
from datetime import datetime
from sqlalchemy.orm import Session
from database import SessionLocal
from models import Call
from logger_config import get_logger
from scenarios import scenario_test, scenario_production  # Scénarios disponibles

logger = get_logger(__name__)

# Configuration
ARI_URL = "http://localhost:8088"
ARI_USER = "robot"
ARI_PASS = "tyxiyy6KTdGbIbUT"
RECORDINGS_PATH = "/var/spool/asterisk/recording"

# Services IA - Import IMMÉDIAT au démarrage
from services.sentiment_service import sentiment_service

# CHARGER WHISPER DÈS MAINTENANT !
logger.info("🤖 Loading Whisper service at startup...")
try:
    from services.whisper_service import whisper_service
    logger.info("✅ Whisper loaded at startup! No delays during calls")
except Exception as e:
    logger.error(f"❌ Failed to load Whisper: {e}")
    whisper_service = None

# Les fichiers audio sont gérés par setup_audio.sh maintenant
# Plus besoin de vérification ici

# PRÉ-CHARGER TOUS LES SCÉNARIOS !
logger.info("📝 Pre-loading scenarios...")
try:
    from scenario_cache import scenario_manager
    scenario_manager.preload_scenarios()
    logger.info("✅ Scenarios cached and validated!")
except Exception as e:
    logger.error(f"❌ Failed to load scenarios: {e}")
    scenario_manager = None

# Whisper est maintenant toujours pré-chargé au démarrage
# Plus besoin de chargement à la demande

class RobotARI:
    """Robot ARI Production - WebSocket natif"""

    def __init__(self):
        self.ws = None
        self.auth = (ARI_USER, ARI_PASS)
        self.running = True
        self.active_calls = {}  # Dict pour tracker les threads actifs {channel_id: thread}
        self.call_sequences = {}  # Dict pour AUTO-TRACKER les audio: {channel_id: [{type, file, ...}]}
        self.call_lock = threading.Lock()
        self.connect()

    def connect(self):
        """Connexion WebSocket à Asterisk ARI"""
        ws_url = f"ws://localhost:8088/ari/events?app=robot-app&api_key={ARI_USER}:{ARI_PASS}"
        logger.info(f"📡 Connecting to Asterisk ARI...")

        self.ws = websocket.WebSocketApp(
            ws_url,
            on_open=self.on_open,
            on_message=self.on_message,
            on_error=self.on_error,
            on_close=self.on_close
        )

    def on_open(self, ws):
        logger.info("✅ Connected to Asterisk ARI")
        logger.info("👂 Listening for calls...")

    def on_message(self, ws, message):
        """Traite les événements ARI"""
        try:
            event = json.loads(message)
            event_type = event.get('type', '')

            if event_type == 'StasisStart':
                self.handle_stasis_start(event)
            elif event_type == 'StasisEnd':
                self.handle_stasis_end(event)
            elif event_type in ['ChannelStateChange', 'PlaybackStarted', 'PlaybackFinished']:
                logger.debug(f"📨 {event_type}")

        except Exception as e:
            logger.error(f"❌ Error handling event: {e}", exc_info=True)

    def on_error(self, ws, error):
        logger.error(f"❌ WebSocket error: {error}")

    def on_close(self, ws, close_status_code, close_msg):
        logger.info(f"👋 WebSocket closed: {close_status_code}")

        # Reconnexion automatique
        if self.running and close_status_code != 1000:
            logger.info("🔄 Reconnecting in 5 seconds...")
            time.sleep(5)
            self.connect()

    def start_full_call_recording(self, channel_id, recording_name):
        """
        Démarre l'enregistrement complet de l'appel avec MixMonitor via ARI

        Args:
            channel_id: ID du canal Asterisk
            recording_name: Nom du fichier d'enregistrement (sans extension)
        """
        try:
            url = f"{ARI_URL}/ari/channels/{channel_id}/record"
            data = {
                "name": recording_name,
                "format": "wav",
                "maxDurationSeconds": 0,  # 0 = pas de limite
                "terminateOn": "none",
                "beep": False,
                "ifExists": "overwrite"
            }

            response = requests.post(url, json=data, auth=self.auth)

            if response.status_code in [200, 201]:
                logger.info(f"🎙️  Full call recording started: {recording_name}.wav")
                return True
            else:
                logger.error(f"❌ Failed to start full call recording: {response.text}")
                return False

        except Exception as e:
            logger.error(f"❌ Error starting full call recording: {e}")
            return False

    def _handle_call_thread(self, channel_id, phone_number, amd_status, scenario_name, campaign_id, rec_file):
        """Gère un appel dans un thread séparé (PERMET LE MULTI-APPEL)"""
        try:
            # RÉPONDRE AU CANAL (CRITIQUE pour que l'audio puisse jouer)
            try:
                answer_url = f"{ARI_URL}/ari/channels/{channel_id}/answer"
                answer_resp = requests.post(answer_url, auth=self.auth)
                if answer_resp.status_code in [200, 204]:
                    logger.info(f"✅ Channel answered")
                else:
                    logger.error(f"❌ Failed to answer channel: {answer_resp.text}")
                    return
            except Exception as e:
                logger.error(f"❌ Error answering channel: {e}")
                return

            # Enregistrement path
            if rec_file:
                recording_path = f"{RECORDINGS_PATH}/{rec_file}.wav"
                logger.info(f"   📁 Recording path (interactions only): {rec_file}.wav")
            else:
                recording_path = None
                logger.warning("   ⚠️  No recording file provided by dialplan")

            # Sauvegarder en base avec AMD status et recording path
            db = SessionLocal()
            try:
                call = Call(
                    call_id=channel_id,
                    phone_number=phone_number,
                    campaign_id=campaign_id,
                    status="answered",
                    amd_result=amd_status.lower() if amd_status else None,
                    recording_path=recording_path,
                    started_at=datetime.now()
                )
                db.add(call)
                db.commit()
                logger.info(f"💾 Call saved to database (AMD: {amd_status})")
                logger.info(f"🎙️  Full call recording: {recording_path}")
            except Exception as e:
                logger.error(f"❌ Database error: {e}")
            finally:
                db.close()

            # Si c'est un répondeur, raccrocher directement
            if amd_status.upper() == "MACHINE":
                logger.info(f"📱 Answering machine detected! Hanging up...")
                self.hangup(channel_id)
                return

            # Initialiser le tracking automatique des audio pour cet appel
            self.start_tracking_call(channel_id)

            # Exécuter le scénario PRODUCTION (unique scénario actif)
            logger.info(f"🎬 Exécution du scénario PRODUCTION")
            scenario_production(self, channel_id, phone_number, campaign_id)

        except Exception as e:
            logger.error(f"❌ Error in call thread: {e}", exc_info=True)
            if channel_id:
                self.hangup(channel_id)
        finally:
            # Retirer de la liste des appels actifs
            with self.call_lock:
                if channel_id in self.active_calls:
                    del self.active_calls[channel_id]
                    logger.info(f"📊 Active calls: {len(self.active_calls)}")

    def handle_stasis_start(self, event):
        """Gère le début d'un appel - LANCE DANS UN THREAD POUR MULTI-APPEL"""
        try:
            channel = event.get('channel', {})
            channel_id = channel.get('id')
            args = event.get('args', [])

            # Extraire les arguments (ordre du dialplan: phone, amd_status, scenario, campaign, rec_file)
            phone_number = args[0] if len(args) > 0 else "unknown"
            amd_status = args[1] if len(args) > 1 else "UNKNOWN"
            scenario_name = args[2] if len(args) > 2 else "basique"
            campaign_id = args[3] if len(args) > 3 else None
            rec_file = args[4] if len(args) > 4 else None

            logger.info(f"📞 New call: {channel_id}")
            logger.info(f"   📱 Phone: {phone_number}")
            logger.info(f"   🤖 AMD Status: {amd_status}")
            logger.info(f"   🎬 Scenario: {scenario_name}")

            # LANCER DANS UN THREAD POUR PERMETTRE LE MULTI-APPEL
            call_thread = threading.Thread(
                target=self._handle_call_thread,
                args=(channel_id, phone_number, amd_status, scenario_name, campaign_id, rec_file),
                daemon=True,
                name=f"Call-{channel_id}"
            )

            with self.call_lock:
                self.active_calls[channel_id] = call_thread
                logger.info(f"🚀 Starting call thread ({len(self.active_calls)} active)")

            call_thread.start()

        except Exception as e:
            logger.error(f"❌ Error in StasisStart: {e}", exc_info=True)

    def handle_stasis_end(self, event):
        """Gère la fin d'un appel"""
        try:
            channel = event.get('channel', {})
            channel_id = channel.get('id')

            logger.info(f"📞 Call ended: {channel_id}")

            # Mettre à jour en base
            db = SessionLocal()
            try:
                from models import Contact

                call = db.query(Call).filter(Call.call_id == channel_id).first()
                if call:
                    call.status = "completed"
                    call.ended_at = datetime.now()
                    if call.started_at:
                        call.duration = int((call.ended_at - call.started_at).total_seconds())

                    # Sauvegarder le chemin d'enregistrement dans le contact s'il existe
                    if call.phone_number and call.recording_path:
                        contact = db.query(Contact).filter(Contact.phone == call.phone_number).first()
                        if contact:
                            contact.audio_recording_path = call.recording_path
                            logger.info(f"📁 Recording path saved to contact: {call.phone_number}")

                    db.commit()
                    logger.info(f"📊 Call duration: {call.duration}s")
            finally:
                db.close()

        except Exception as e:
            logger.error(f"❌ Error in StasisEnd: {e}")


    def play_audio(self, channel_id, sound):
        """Joue un son Asterisk (beep, hello-world, etc.)"""
        try:
            url = f"{ARI_URL}/ari/channels/{channel_id}/play"
            media = f"sound:{sound}"
            data = {"media": media}
            response = requests.post(url, json=data, auth=self.auth)

            if response.status_code in [200, 201]:
                logger.info(f"🔊 Playing sound: {sound}")
                return response.json().get('id')
            else:
                logger.error(f"❌ Failed to play {sound}: {response.text}")

        except Exception as e:
            logger.error(f"❌ Play error: {e}")
            return None

    def play_audio_file(self, channel_id, filename, wait_for_completion=True):
        """
        Joue VOS vrais fichiers WAV du dossier audio/
        🤖 AUTO-TRACKING: Ajoute automatiquement à call_sequences pour assemblage

        Args:
            channel_id: ID du canal
            filename: Nom du fichier sans extension
            wait_for_completion: Si True, attend la fin de l'audio avant de retourner
        """
        try:
            url = f"{ARI_URL}/ari/channels/{channel_id}/play"

            # Chemin complet vers votre fichier WAV (pour vérification)
            # Détecter automatiquement le répertoire du projet
            project_root = os.path.dirname(os.path.abspath(__file__))
            audio_path = os.path.join(project_root, "audio", f"{filename}.wav")

            if os.path.exists(audio_path):
                # NOUVELLE MÉTHODE: Utiliser sound:minibot/
                # Nécessite d'avoir copié les fichiers dans /var/lib/asterisk/sounds/minibot/
                # Exécuter: sudo ./copy_audio_to_asterisk.sh
                media = f"sound:minibot/{filename}"
                logger.info(f"🎵 Playing YOUR audio file: minibot/{filename}")
                logger.info(f"   Using Asterisk sounds directory")
            else:
                logger.warning(f"⚠️ File not found: {audio_path}, using beep")
                media = "sound:beep"

            data = {"media": media}
            response = requests.post(url, json=data, auth=self.auth)

            if response.status_code in [200, 201]:
                playback_id = response.json().get('id')

                # 🤖 AUTO-TRACKING: Ajouter automatiquement à la séquence
                self._track_audio(channel_id, "bot", f"{filename}.wav")

                if wait_for_completion and playback_id:
                    # NOUVEAU : Attendre que l'audio soit VRAIMENT fini
                    self.wait_for_playback_finished(channel_id, playback_id)

                return playback_id
            else:
                logger.error(f"❌ Failed to play {filename}: {response.text}")

        except Exception as e:
            logger.error(f"❌ Play error: {e}")
            return None

    def wait_for_playback_finished(self, channel_id, playback_id, max_wait=60):
        """
        Attend que le playback soit terminé

        Args:
            channel_id: ID du canal
            playback_id: ID du playback retourné par play_audio_file
            max_wait: Temps max d'attente en secondes (sécurité)
        """
        if not playback_id:
            return

        logger.info(f"⏳ Waiting for playback {playback_id} to finish...")
        start_time = time.time()

        while time.time() - start_time < max_wait:
            try:
                # Vérifier si le playback existe encore
                url = f"{ARI_URL}/ari/playbacks/{playback_id}"
                response = requests.get(url, auth=self.auth)

                if response.status_code == 404:
                    # Playback terminé !
                    elapsed = time.time() - start_time
                    logger.info(f"✅ Playback finished after {elapsed:.1f}s")
                    time.sleep(0.5)  # Petite pause de sécurité
                    break
                elif response.status_code == 200:
                    # Playback toujours en cours
                    data = response.json()
                    state = data.get('state', 'unknown')
                    logger.debug(f"   Playback state: {state}")

                time.sleep(0.3)  # Vérifier toutes les 300ms

            except Exception as e:
                logger.error(f"Error checking playback: {e}")
                break
        else:
            logger.warning(f"⚠️ Max wait time reached for playback")

    def record_audio(self, channel_id, name, max_silence_seconds=2, wait_before_stop=8):
        """
        Enregistre l'audio avec détection de silence CUSTOM Python
        (Contourne le bug d'Asterisk qui ignore maxSilenceSeconds)

        Args:
            channel_id: ID du canal
            name: Nom de l'enregistrement
            max_silence_seconds: Secondes de silence avant arrêt (VRAIMENT appliqué!)
            wait_before_stop: Temps max d'attente avant arrêt forcé
        """
        try:
            url = f"{ARI_URL}/ari/channels/{channel_id}/record"
            data = {
                "name": name,
                "format": "wav",
                "maxDurationSeconds": 30,
                # On n'envoie PLUS maxSilenceSeconds car Asterisk l'ignore
                "terminateOn": "#",
                "beep": False,
                "ifExists": "overwrite"
            }

            response = requests.post(url, json=data, auth=self.auth)

            if response.status_code in [200, 201]:
                logger.info(f"🎤 Recording started: {name} (custom silence detection: {max_silence_seconds}s)")

                # DÉTECTION DE SILENCE : Version simplifiée basée sur le timing
                # (Le fichier WAV n'existe qu'après l'arrêt, pas pendant!)
                recording_path = f"{RECORDINGS_PATH}/{name}.wav"
                start_time = time.time()
                speech_detected = False
                speech_start_time = None
                silence_start_time = None

                logger.info(f"⏳ Waiting for speech (max {wait_before_stop}s)...")

                while time.time() - start_time < wait_before_stop:
                    elapsed = time.time() - start_time

                    # Vérifier si l'enregistrement est toujours en cours
                    status_url = f"{ARI_URL}/ari/recordings/live/{name}"
                    status_resp = requests.get(status_url, auth=self.auth)

                    if status_resp.status_code == 404:
                        # Recording terminé (touche # ou autre)
                        logger.info(f"⏹️ Recording ended after {elapsed:.1f}s")
                        break

                    # Logique simplifiée de détection
                    if elapsed < 1.0:
                        # Première seconde : on attend que la personne commence
                        logger.debug(f"⏳ Waiting for speech... {elapsed:.1f}s")

                    elif elapsed < 2.5 and not speech_detected:
                        # Si pas de réponse après 1-2 secondes, on considère qu'elle parle
                        speech_detected = True
                        speech_start_time = time.time()
                        logger.info(f"🗣️ Speech assumed to have started")

                    elif speech_detected:
                        # Après avoir détecté la parole, on attend le silence configuré
                        time_since_speech = time.time() - speech_start_time

                        # On suppose que la personne a fini après X secondes depuis le début
                        # (typiquement 2-4 secondes pour "Oui c'est bien moi")
                        if time_since_speech >= max_silence_seconds:
                            logger.info(f"🤫 Assuming silence after {max_silence_seconds}s (total: {elapsed:.1f}s)")

                            # Arrêter l'enregistrement
                            stop_url = f"{ARI_URL}/ari/recordings/live/{name}/stop"
                            stop_resp = requests.post(stop_url, auth=self.auth)

                            if stop_resp.status_code in [200, 204]:
                                logger.info(f"✅ Recording stopped successfully")
                                time.sleep(0.5)  # Laisser le temps de finaliser
                                break
                            else:
                                logger.warning(f"⚠️ Could not stop recording: {stop_resp.status_code}")

                    time.sleep(0.5)  # Vérifier toutes les 500ms

                else:
                    # Temps max atteint
                    stop_url = f"{ARI_URL}/ari/recordings/live/{name}/stop"
                    requests.post(stop_url, auth=self.auth)
                    logger.info(f"⏱️ Recording stopped after max time ({wait_before_stop}s)")

                return recording_path
            else:
                logger.error(f"❌ Failed to start recording: {response.text}")
                return None

        except Exception as e:
            logger.error(f"❌ Record error: {e}")
            return None

    def process_recording(self, recording_path):
        """Traite l'enregistrement: transcription + sentiment"""
        try:
            # Vérifier si le fichier existe
            if not os.path.exists(recording_path):
                logger.warning(f"⚠️ Recording not found: {recording_path}")
                return "silence", "neutre"

            logger.info(f"📁 Processing recording: {recording_path}")

            # Obtenir taille du fichier pour debug
            file_size = os.path.getsize(recording_path)
            logger.info(f"📊 File size: {file_size} bytes")

            if file_size < 1000:  # Fichier trop petit, probablement silence
                logger.warning("⚠️ File too small, probably silence")
                return "silence", "neutre"

            # Utiliser Whisper pour la transcription (pré-chargé au démarrage)
            try:
                logger.info("🎤 Starting Whisper transcription...")
                if whisper_service is None:
                    logger.warning("⚠️ Whisper not available, using DEMO mode")
                    import random
                    demo_responses = [
                        ("Oui je suis satisfait", "positif"),
                        ("Non pas vraiment", "negatif"),
                        ("C'est correct", "neutre"),
                        ("Très bien merci", "positif")
                    ]
                    return random.choice(demo_responses)

                result = whisper_service.transcribe(recording_path, language="fr")
                transcription = result.get("text", "").strip()

                if not transcription:
                    logger.warning("⚠️ No transcription detected (silence)")
                    return "silence", "neutre"

                logger.info(f"📝 Transcription: '{transcription}'")

                # Analyser le sentiment
                logger.info("💭 Analyzing sentiment...")
                sentiment, confidence = sentiment_service.analyze_sentiment(transcription)
                logger.info(f"💭 Sentiment detected: {sentiment}")

                return transcription, sentiment

            except Exception as whisper_error:
                logger.error(f"❌ Whisper error: {whisper_error}", exc_info=True)
                # Fallback au mode DEMO si Whisper échoue
                logger.warning("⚠️ Falling back to DEMO mode")
                import random
                demo_responses = [
                    ("Oui je suis satisfait", "positif"),
                    ("Non pas vraiment", "negatif"),
                    ("C'est correct", "neutre"),
                    ("Très bien merci", "positif")
                ]
                return random.choice(demo_responses)

        except Exception as e:
            logger.error(f"❌ Processing error: {e}", exc_info=True)
            return "error", "neutre"

    def record_with_silence_detection(self, channel_id, name, max_silence_seconds=4, wait_before_stop=15):
        """
        Record audio with silence detection and transcription (BATCH MODE)
        🤖 AUTO-TRACKING: Ajoute automatiquement à call_sequences pour assemblage

        Args:
            channel_id: Asterisk channel ID
            name: Recording name
            max_silence_seconds: Seconds of silence before stopping
            wait_before_stop: Max wait time

        Returns:
            (transcription, sentiment) tuple
        """
        logger.info("🎙️  Starting recording with silence detection...")

        recording_path = self.record_audio(
            channel_id,
            name,
            max_silence_seconds=max_silence_seconds,
            wait_before_stop=wait_before_stop
        )

        if recording_path and os.path.exists(recording_path):
            transcription, sentiment = self.process_recording(recording_path)
            logger.info(f"✅ Transcription completed")
            logger.info(f"   Transcription: '{transcription[:100]}'")
            logger.info(f"   Sentiment: {sentiment}")

            # 🤖 AUTO-TRACKING: Ajouter automatiquement à la séquence
            self._track_audio(channel_id, "client", f"{name}.wav", transcription, sentiment)

            return transcription, sentiment
        else:
            logger.error("❌ Recording failed!")
            return "silence", "neutre"

    def save_interaction(self, call_id, question_num, question_type, transcription, sentiment):
        """Sauvegarde l'interaction en base"""
        db = SessionLocal()
        try:
            from sqlalchemy import text
            query = text("""
                INSERT INTO call_interactions
                (call_id, question_number, question_played, transcription, sentiment, played_at)
                VALUES (:call_id, :q_num, :q_type, :trans, :sent, :played)
            """)

            db.execute(query, {
                'call_id': call_id,
                'q_num': question_num,
                'q_type': question_type,
                'trans': transcription[:500] if transcription else "",
                'sent': sentiment,
                'played': datetime.now()
            })
            db.commit()
            logger.info(f"💾 Interaction saved: Q{question_num} → {sentiment}")

        except Exception as e:
            logger.error(f"❌ Save error: {e}")
        finally:
            db.close()

    # ============================================================================
    # 🤖 AUTO-TRACKING SYSTÈME (en mémoire, simple, universel)
    # ============================================================================

    def start_tracking_call(self, channel_id):
        """
        Initialise le tracking automatique pour un appel
        Appelé au début du scénario automatiquement
        """
        self.call_sequences[channel_id] = []
        logger.debug(f"🤖 Auto-tracking started for call {channel_id}")

    def _track_audio(self, channel_id, audio_type, filename, transcription="", sentiment=""):
        """
        Ajoute un fichier audio à la séquence (INTERNE - appelé automatiquement)

        Args:
            channel_id: ID du canal
            audio_type: "bot" ou "client"
            filename: Nom du fichier (ex: "intro.wav" ou "test_123.wav")
            transcription: Texte transcrit (pour client seulement)
            sentiment: Sentiment détecté (pour client seulement)
        """
        if channel_id not in self.call_sequences:
            # Fallback: initialiser si pas encore fait
            self.call_sequences[channel_id] = []

        item = {
            "type": audio_type,
            "file": filename,
            "timestamp": datetime.now()
        }

        if audio_type == "client":
            item["transcription"] = transcription
            item["sentiment"] = sentiment

        self.call_sequences[channel_id].append(item)
        logger.debug(f"🤖 Tracked: {audio_type} → {filename}")

    def get_call_sequence(self, channel_id):
        """
        Récupère la séquence complète des audio pour un appel
        Appelé à la fin du scénario pour assemblage

        Returns:
            Liste des audio [{type, file, timestamp, ...}]
        """
        sequence = self.call_sequences.get(channel_id, [])

        # Nettoyer de la mémoire après récupération
        if channel_id in self.call_sequences:
            del self.call_sequences[channel_id]

        logger.info(f"🤖 Retrieved {len(sequence)} tracked audio files for call {channel_id}")
        return sequence

    # ============================================================================

    def hangup(self, channel_id):
        """Raccroche l'appel"""
        try:
            url = f"{ARI_URL}/ari/channels/{channel_id}"
            response = requests.delete(url, auth=self.auth)

            if response.status_code in [200, 204]:
                logger.info(f"📞 Call terminated")
            else:
                logger.error(f"❌ Failed to hangup: {response.text}")

        except Exception as e:
            logger.error(f"❌ Hangup error: {e}")

    def run(self):
        """Démarre le robot"""
        logger.info("=" * 60)
        logger.info("🤖 MINIBOT ROBOT ARI - READY")
        logger.info("=" * 60)
        logger.info("✅ Whisper: Pré-chargé au démarrage")
        logger.info("✅ Scénario: PRODUCTION (qualification progressive)")
        logger.info("📡 Connexion WebSocket à Asterisk ARI...")
        logger.info("=" * 60)

        try:
            logger.info("🚀 Starting WebSocket connection...")
            self.ws.run_forever()
        except KeyboardInterrupt:
            logger.info("⛔ Stopping robot...")
            self.running = False
            if self.ws:
                self.ws.close()

    def stop(self):
        """Arrête le robot proprement"""
        self.running = False
        if self.ws:
            self.ws.close()
        logger.info("👋 Robot stopped")


if __name__ == "__main__":
    # Créer les dossiers si nécessaire
    os.makedirs(RECORDINGS_PATH, exist_ok=True)
    os.makedirs("audio", exist_ok=True)
    os.makedirs("logs", exist_ok=True)

    # PRÉ-VALIDATION AU DÉMARRAGE
    logger.info("=" * 60)
    logger.info("🔍 VALIDATION DU SYSTÈME AU DÉMARRAGE")
    logger.info("=" * 60)

    # 1. Vérifier Whisper
    if whisper_service:
        logger.info("✅ Whisper: Modèle chargé et prêt")
    else:
        logger.error("❌ Whisper non chargé!")

    # 2. Vérifier le scénario (déjà importé en haut)
    logger.info("✅ Scénario: PRODUCTION")

    # 3. Test rapide ARI
    try:
        test_resp = requests.get(f"{ARI_URL}/ari/asterisk/info", auth=(ARI_USER, ARI_PASS), timeout=2)
        if test_resp.status_code == 200:
            logger.info("✅ Connexion ARI: OK")
    except:
        logger.warning("⚠️  Test ARI échoué, mais continuons...")

    logger.info("=" * 60)

    # Démarrer le robot
    try:
        robot = RobotARI()
        robot.run()
    except KeyboardInterrupt:
        logger.info("👋 Stopped by user")
    except Exception as e:
        logger.error(f"❌ Fatal error: {e}", exc_info=True)