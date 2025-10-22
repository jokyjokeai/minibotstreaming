#!/usr/bin/env python3
"""
Robot ARI Streaming - MiniBotPanel v2 
Version streaming temps réel avec Vosk + Ollama
Compatible avec architecture existante + performances optimisées
"""

import json
import requests
import websocket
import time
import os
import threading
import asyncio
from datetime import datetime
from sqlalchemy.orm import Session
from database import SessionLocal
from models import Call
from logger_config import get_logger
from typing import Dict, Optional, Any, Callable

logger = get_logger(__name__)

# Configuration
import config
from config import ARI_URL, ARI_USERNAME as ARI_USER, ARI_PASSWORD as ARI_PASS
RECORDINGS_PATH = "/var/spool/asterisk/recording"


# Services streaming (requis)
logger.info("🤖 Loading streaming services...")
try:
    from services.live_asr_vad import live_asr_vad_service, start_live_asr_service
    from services.nlp_intent import intent_engine
    from services.amd_service import amd_service
    STREAMING_SERVICES_AVAILABLE = True
    logger.info("✅ Streaming services loaded successfully")
except Exception as e:
    logger.error(f"❌ Streaming services not available: {e}")
    STREAMING_SERVICES_AVAILABLE = False
    raise RuntimeError("Streaming services required but not available")

# Scénarios streaming
try:
    from scenarios_streaming import scenario_test_streaming, scenario_production_streaming
    SCENARIOS_AVAILABLE = True
    logger.info("✅ Streaming scenarios imported successfully")
except Exception as e:
    logger.error(f"❌ Failed to load streaming scenarios: {e}")
    SCENARIOS_AVAILABLE = False

# Cache scénarios si disponible
try:
    from scenario_cache import scenario_manager
    scenario_manager.preload_scenarios()
    logger.info("✅ Scenarios cached and validated")
except Exception as e:
    logger.warning(f"⚠️ Scenario cache not available: {e}")
    scenario_manager = None

class RobotARIStreaming:
    """
    Robot ARI Streaming - MiniBotPanel v2
    Architecture streaming temps réel pour performances optimales
    """

    def __init__(self):
        self.ws = None
        self.auth = (ARI_USER, ARI_PASS)
        self.running = True
        
        # État des appels (gardé de l'architecture existante)
        self.active_calls = {}  # {channel_id: thread}
        self.call_sequences = {}  # {channel_id: [audio_items]} - AUTO-TRACKING
        self.call_lock = threading.Lock()
        
        # Nouveau: État streaming
        self.streaming_sessions = {}  # {channel_id: streaming_session_info}
        self.barge_in_active = {}  # {channel_id: bool}
        
        # Vérifier les services streaming
        if not STREAMING_SERVICES_AVAILABLE:
            raise RuntimeError("Streaming services required but not available")
        
        logger.info("🎛️ Robot mode: streaming only")
        
        # Initialiser services streaming
        self._init_streaming_services()
        
        # Connexion ARI
        self.connect()


    def _init_streaming_services(self):
        """Initialise les services streaming"""
        try:
            # Démarrer le serveur ASR/VAD en arrière-plan
            def start_streaming_services():
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
                loop.run_until_complete(start_live_asr_service())
            
            streaming_thread = threading.Thread(
                target=start_streaming_services,
                daemon=True,
                name="StreamingServices"
            )
            streaming_thread.start()
            
            logger.info("✅ Streaming services initialization started")
            
        except Exception as e:
            logger.error(f"❌ Failed to initialize streaming services: {e}")
            raise

    def connect(self):
        """Connexion WebSocket à Asterisk ARI"""
        ws_url = f"ws://localhost:8088/ari/events?app=robot&api_key={ARI_USER}:{ARI_PASS}"
        logger.info(f"📡 Connecting to Asterisk ARI...")

        self.ws = websocket.WebSocketApp(
            ws_url,
            on_open=self.on_open,
            on_message=self.on_message,
            on_error=self.on_error,
            on_close=self.on_close
        )

    def on_open(self, ws):
        logger.info("✅ Connected to Asterisk ARI - Mode: streaming")
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
            elif event_type == 'RecordingStarted':
                logger.debug(f"🎙️ Recording started")
            elif event_type == 'RecordingFinished':
                logger.debug(f"🎙️ Recording finished")

        except Exception as e:
            logger.error(f"❌ Error handling event: {e}", exc_info=True)

    def on_error(self, ws, error):
        logger.error(f"❌ WebSocket error: {error}")

    def on_close(self, ws, close_status_code, close_msg):
        logger.warning(f"⚠️ Connection closed: {close_status_code} - {close_msg}")
        if self.running:
            logger.info("🔄 Attempting to reconnect...")
            time.sleep(5)
            self.connect()

    def handle_stasis_start(self, event):
        """Démarre le traitement d'un appel"""
        try:
            channel = event['channel']
            channel_id = channel['id']
            args = event.get('args', [])
            
            # Parser les arguments (compatibilité avec dialplan existant)
            phone_number = args[0] if len(args) > 0 else "unknown"
            amd_status = args[1] if len(args) > 1 else "NOTSURE"
            scenario = args[2] if len(args) > 2 else "production"
            campaign_id = args[3] if len(args) > 3 else "default"
            rec_file = args[4] if len(args) > 4 else ""
            # Mode streaming uniquement
            mode = "streaming"
            
            logger.info(f"📞 New call: {phone_number} | Channel: {channel_id} | Mode: {mode}")
            
            # Lancer le thread de traitement en mode streaming uniquement
            call_thread = threading.Thread(
                target=self._handle_call_streaming,
                args=(channel_id, phone_number, amd_status, scenario, campaign_id, rec_file),
                daemon=True,
                name=f"Call-Streaming-{channel_id}"
            )
            
            with self.call_lock:
                self.active_calls[channel_id] = call_thread
                self.call_sequences[channel_id] = []  # Initialiser AUTO-TRACKING
            
            call_thread.start()
            
        except Exception as e:
            logger.error(f"❌ Error in StasisStart: {e}", exc_info=True)

    def handle_stasis_end(self, event):
        """Nettoie après fin d'appel"""
        try:
            channel = event['channel']
            channel_id = channel['id']
            
            logger.info(f"📞 Call ended: {channel_id}")
            
            with self.call_lock:
                # Nettoyer les ressources
                if channel_id in self.active_calls:
                    del self.active_calls[channel_id]
                
                # Traitement post-appel (audio assembly, etc.)
                if channel_id in self.call_sequences:
                    self._post_process_call(channel_id)
                    del self.call_sequences[channel_id]
                
                # Nettoyer ressources streaming
                if channel_id in self.streaming_sessions:
                    del self.streaming_sessions[channel_id]
                if channel_id in self.barge_in_active:
                    del self.barge_in_active[channel_id]
            
        except Exception as e:
            logger.error(f"❌ Error in StasisEnd: {e}", exc_info=True)

    def _handle_call_streaming(self, channel_id: str, phone_number: str, amd_status: str, 
                             scenario: str, campaign_id: str, rec_file: str):
        """
        Traitement d'appel en mode streaming
        Nouvelle logique avec ASR temps réel + intent + barge-in
        """
        logger.info(f"🌊 Starting streaming call handler for {phone_number}")
        
        try:
            # Répondre au canal
            self.answer_channel(channel_id)
            
            # Créer enregistrement Call en DB (compatibilité existante)
            call_record = self._create_call_record(channel_id, phone_number, campaign_id, "streaming")
            
            # AMD hybride si activé
            final_amd_result = amd_status
            if config.AMD_PYTHON_ENABLED:
                try:
                    # TODO: Récupérer les frames audio pour AMD Python
                    # Pour l'instant utiliser AMD Asterisk
                    amd_result, amd_confidence, amd_metadata = amd_service.analyze_asterisk_amd(amd_status)
                    final_amd_result = amd_result.value
                    logger.info(f"🤖 AMD Result: {final_amd_result} ({amd_confidence:.2f})")
                except Exception as e:
                    logger.warning(f"⚠️ AMD analysis failed: {e}")
            
            # Si machine détectée, arrêter ici (géré par dialplan)
            if final_amd_result == "MACHINE":
                logger.info(f"📠 Machine detected for {phone_number} - call handled by dialplan")
                return
            
            # Initialiser session streaming
            self._init_streaming_session(channel_id, phone_number)
            
            # Exécuter scénario streaming
            if scenario == "production":
                self._scenario_production_streaming(channel_id, phone_number, campaign_id)
            else:
                self._scenario_test_streaming(channel_id, phone_number, campaign_id)
            
        except Exception as e:
            logger.error(f"❌ Error in streaming call handler: {e}", exc_info=True)
        finally:
            logger.info(f"🌊 Streaming call handler completed for {phone_number}")

    def _handle_call_classic(self, channel_id: str, phone_number: str, amd_status: str,
                           scenario: str, campaign_id: str, rec_file: str):
        """
        Traitement d'appel en mode classic
        Logique existante préservée avec Whisper batch
        """
        logger.info(f"📻 Starting classic call handler for {phone_number}")
        
        try:
            # Répondre au canal
            self.answer_channel(channel_id)
            
            # Créer enregistrement Call en DB
            call_record = self._create_call_record(channel_id, phone_number, campaign_id, "classic")
            
            # Exécuter scénario classic (logique supprimée)
            # ANCIEN CODE SUPPRIMÉ: scenarios.py n'existe plus depuis refactoring
            # Tous les appels utilisent maintenant le mode streaming ou les scénarios générés
            logger.warning("⚠️ Mode classic obsolète - utiliser streaming ou scénarios générés")
            return
            
        except Exception as e:
            logger.error(f"❌ Error in classic call handler: {e}", exc_info=True)
        finally:
            logger.info(f"📻 Classic call handler completed for {phone_number}")

    def _init_streaming_session(self, channel_id: str, phone_number: str):
        """Initialise une session streaming pour un appel"""
        self.streaming_sessions[channel_id] = {
            "phone_number": phone_number,
            "start_time": time.time(),
            "current_step": "hello",
            "partial_transcriptions": [],
            "final_transcriptions": [],
            "intents": [],
            "barge_in_count": 0,
            "latency_stats": []
        }
        
        # Enregistrer callback pour ASR/VAD
        if live_asr_vad_service.is_available:
            live_asr_vad_service.register_callback(channel_id, self._streaming_callback)
        
        self.barge_in_active[channel_id] = False
        logger.debug(f"🎛️ Streaming session initialized for {channel_id}")

    def _streaming_callback(self, event_type: str, channel_id: str, data: Dict[str, Any]):
        """Callback pour événements streaming (ASR, VAD, etc.)"""
        try:
            if channel_id not in self.streaming_sessions:
                return
            
            session = self.streaming_sessions[channel_id]
            
            if event_type == "speech_start":
                # Détection début de parole - potentiel barge-in
                if config.BARGE_IN_ENABLED and self.barge_in_active.get(channel_id, False):
                    logger.debug(f"🔇 Barge-in detected for {channel_id}")
                    self._handle_barge_in(channel_id)
                    session["barge_in_count"] += 1
            
            elif event_type == "speech_end":
                # Fin de parole
                logger.debug(f"🤐 Speech end for {channel_id}")
                
            elif event_type == "transcription":
                # Transcription reçue
                transcription_data = {
                    "text": data["text"],
                    "type": data["type"],
                    "timestamp": data["timestamp"],
                    "latency_ms": data["latency_ms"]
                }
                
                if data["type"] == "partial":
                    session["partial_transcriptions"].append(transcription_data)
                else:
                    session["final_transcriptions"].append(transcription_data)
                    logger.debug(f"📝 Final transcription: '{data['text']}' ({data['latency_ms']:.1f}ms)")
                    
                    # Analyser intent si transcription finale
                    self._process_final_transcription(channel_id, data["text"])
            
        except Exception as e:
            logger.error(f"❌ Error in streaming callback: {e}")

    def _process_final_transcription(self, channel_id: str, text: str):
        """Traite une transcription finale pour extraction d'intent"""
        try:
            if channel_id not in self.streaming_sessions:
                return
            
            session = self.streaming_sessions[channel_id]
            current_step = session["current_step"]
            
            # Analyser intent avec contexte
            intent, confidence, metadata = intent_engine.get_intent(text, current_step)
            
            intent_data = {
                "text": text,
                "intent": intent,
                "confidence": confidence,
                "context": current_step,
                "metadata": metadata,
                "timestamp": time.time()
            }
            
            session["intents"].append(intent_data)
            session["latency_stats"].append(metadata.get("latency_ms", 0))
            
            logger.debug(f"🧠 Intent: {text} → {intent} ({confidence:.2f})")
            
            # Déclencher transition scénario
            self._trigger_scenario_transition(channel_id, intent, confidence)
            
        except Exception as e:
            logger.error(f"❌ Error processing transcription: {e}")

    def _trigger_scenario_transition(self, channel_id: str, intent: str, confidence: float):
        """Déclenche une transition de scénario basée sur l'intent"""
        # Cette méthode sera appelée de façon asynchrone
        # Pour l'instant, stocker pour traitement par le thread principal
        if channel_id in self.streaming_sessions:
            session = self.streaming_sessions[channel_id]
            session["pending_transition"] = {
                "intent": intent,
                "confidence": confidence,
                "timestamp": time.time()
            }

    def _handle_barge_in(self, channel_id: str):
        """Gère l'interruption barge-in"""
        try:
            # Arrêter playback en cours
            self.stop_playback(channel_id)
            logger.debug(f"🔇 Playback stopped for barge-in on {channel_id}")
            
        except Exception as e:
            logger.error(f"❌ Error handling barge-in: {e}")

    # =============================================================================
    # MÉTHODES HÉRITÉES DE L'ARCHITECTURE EXISTANTE
    # =============================================================================
    
    def answer_channel(self, channel_id):
        """Répond à un canal (méthode existante gardée)"""
        try:
            url = f"{ARI_URL}/ari/channels/{channel_id}/answer"
            response = requests.post(url, auth=self.auth)
            response.raise_for_status()
            logger.debug(f"✅ Channel {channel_id} answered")
        except Exception as e:
            logger.error(f"❌ Failed to answer channel {channel_id}: {e}")

    def hangup_channel(self, channel_id):
        """Raccroche un canal (méthode existante gardée)"""
        try:
            url = f"{ARI_URL}/ari/channels/{channel_id}"
            response = requests.delete(url, auth=self.auth)
            logger.debug(f"✅ Channel {channel_id} hung up")
        except Exception as e:
            logger.error(f"❌ Failed to hangup channel {channel_id}: {e}")

    def play_audio_file(self, channel_id, filename, enable_barge_in=False):
        """
        Joue un fichier audio (méthode hybride)
        Compatible mode classic + ajout barge-in pour streaming
        """
        try:
            # Activer barge-in si mode streaming
            if enable_barge_in:
                self.barge_in_active[channel_id] = True
            
            media_uri = f"sound:minibot/{filename}"
            url = f"{ARI_URL}/ari/channels/{channel_id}/play"
            
            payload = {
                "media": media_uri,
                "playbackId": f"playback-{channel_id}-{int(time.time())}"
            }
            
            response = requests.post(url, auth=self.auth, json=payload)
            response.raise_for_status()
            
            playback_id = payload["playbackId"]
            
            # AUTO-TRACKING (garder logique existante)
            self._track_audio(channel_id, "bot", filename)
            
            logger.debug(f"🔊 Playing {filename} on {channel_id}")
            
            # Attendre fin de playback
            self.wait_for_playback_finished(playback_id)
            
            # Désactiver barge-in après playback
            if enable_barge_in and channel_id in self.barge_in_active:
                self.barge_in_active[channel_id] = False
            
            return playback_id
            
        except Exception as e:
            logger.error(f"❌ Failed to play {filename}: {e}")
            return None

    def stop_playback(self, channel_id):
        """Arrête le playback en cours"""
        try:
            # Trouver les playbacks actifs pour ce channel
            url = f"{ARI_URL}/ari/playbacks"
            response = requests.get(url, auth=self.auth)
            response.raise_for_status()
            
            playbacks = response.json()
            for playback in playbacks:
                if playback.get("target_uri", "").endswith(channel_id):
                    playback_id = playback["id"]
                    stop_url = f"{ARI_URL}/ari/playbacks/{playback_id}"
                    requests.delete(stop_url, auth=self.auth)
                    logger.debug(f"🛑 Stopped playback {playback_id}")
                    
        except Exception as e:
            logger.error(f"❌ Failed to stop playback: {e}")

    def wait_for_playback_finished(self, playback_id):
        """Attend la fin d'un playback (méthode existante gardée)"""
        # Logique existante simplifiée
        # Dans la vraie implémentation, écouter PlaybackFinished events
        time.sleep(0.5)  # Placeholder

    def _track_audio(self, channel_id, audio_type, filename, transcription="", sentiment=""):
        """AUTO-TRACKING des audio (méthode existante gardée)"""
        if channel_id not in self.call_sequences:
            self.call_sequences[channel_id] = []
        
        audio_item = {
            "type": audio_type,  # "bot" ou "client"
            "file": filename,
            "transcription": transcription,
            "sentiment": sentiment,
            "timestamp": time.time()
        }
        
        self.call_sequences[channel_id].append(audio_item)
        logger.debug(f"📝 Tracked audio: {audio_type}/{filename}")

    def _create_call_record(self, channel_id: str, phone_number: str, campaign_id: str, mode: str) -> Call:
        """Crée un enregistrement Call en DB (compatible existant)"""
        try:
            db = SessionLocal()
            call = Call(
                call_id=channel_id,
                phone_number=phone_number,
                campaign_id=campaign_id,
                status="answered",
                started_at=datetime.now()
            )
            db.add(call)
            db.commit()
            db.refresh(call)
            db.close()
            
            logger.debug(f"💾 Call record created: {channel_id}")
            return call
            
        except Exception as e:
            logger.error(f"❌ Failed to create call record: {e}")
            return None

    def _post_process_call(self, channel_id: str):
        """Post-traitement après appel (assembly audio, etc.)"""
        try:
            if channel_id in self.call_sequences:
                sequence = self.call_sequences[channel_id]
                logger.debug(f"🔧 Post-processing call {channel_id} with {len(sequence)} audio items")
                
                # Déclencher assembly audio (logique existante)
                # TODO: Appeler audio_assembly_service
                
        except Exception as e:
            logger.error(f"❌ Error in post-processing: {e}")

    # =============================================================================
    # SCÉNARIOS STREAMING (nouveaux)
    # =============================================================================
    
    def _scenario_production_streaming(self, channel_id: str, phone_number: str, campaign_id: str):
        """Scénario production en mode streaming"""
        logger.info(f"🎬 Starting production scenario (streaming) for {phone_number}")
        
        try:
            # Étape 1: Hello avec barge-in
            self.play_audio_file(channel_id, "hello.wav", enable_barge_in=True)
            
            # Attendre transcription et intent
            response = self._wait_for_streaming_response(channel_id, "hello", timeout=15.0)
            
            if response["intent"] in ["affirm", "interested"]:
                # Continuer avec questions
                self._ask_streaming_questions(channel_id, phone_number, campaign_id)
            elif response["intent"] == "deny":
                # Tentative retry
                self._try_retry_streaming(channel_id, phone_number, campaign_id)
            else:
                # Cas par défaut
                self._try_retry_streaming(channel_id, phone_number, campaign_id)
                
        except Exception as e:
            logger.error(f"❌ Error in streaming production scenario: {e}")

    def _scenario_test_streaming(self, channel_id: str, phone_number: str, campaign_id: str):
        """Scénario test en mode streaming"""
        logger.info(f"🧪 Starting test scenario (streaming) for {phone_number}")
        
        # Version simplifiée pour tests
        self.play_audio_file(channel_id, "test_audio.wav", enable_barge_in=True)
        time.sleep(3)  # Attendre un peu
        self.hangup_channel(channel_id)

    def _wait_for_streaming_response(self, channel_id: str, context: str, timeout: float = 10.0) -> Dict[str, Any]:
        """Attend une réponse en mode streaming"""
        start_time = time.time()
        
        while time.time() - start_time < timeout:
            if channel_id in self.streaming_sessions:
                session = self.streaming_sessions[channel_id]
                
                # Vérifier s'il y a une transition en attente
                if "pending_transition" in session:
                    transition = session.pop("pending_transition")
                    return {
                        "intent": transition["intent"],
                        "confidence": transition["confidence"],
                        "text": "",
                        "timeout": False
                    }
            
            time.sleep(0.1)  # Petit délai
        
        # Timeout
        logger.warning(f"⏰ Timeout waiting for streaming response on {channel_id}")
        return {
            "intent": "unsure",
            "confidence": 0.0,
            "text": "",
            "timeout": True
        }

    def _ask_streaming_questions(self, channel_id: str, phone_number: str, campaign_id: str):
        """Pose les questions en mode streaming"""
        questions = ["q1.wav", "q2.wav", "q3.wav"]
        
        for i, question in enumerate(questions, 1):
            logger.debug(f"❓ Question {i} for {phone_number}")
            
            self.play_audio_file(channel_id, question, enable_barge_in=True)
            response = self._wait_for_streaming_response(channel_id, f"q{i}", timeout=12.0)
            
            # Enregistrer la réponse mais continuer (qualification)
            logger.debug(f"💬 Q{i} response: {response['intent']} ({response['confidence']:.2f})")
        
        # Question finale
        self._ask_final_offer_streaming(channel_id, phone_number, campaign_id)

    def _ask_final_offer_streaming(self, channel_id: str, phone_number: str, campaign_id: str):
        """Question finale en mode streaming"""
        logger.debug(f"🎯 Final offer for {phone_number}")
        
        self.play_audio_file(channel_id, "is_leads.wav", enable_barge_in=True)
        response = self._wait_for_streaming_response(channel_id, "final_offer", timeout=15.0)
        
        if response["intent"] in ["affirm", "interested"]:
            # Lead!
            self._confirm_callback_streaming(channel_id, phone_number, campaign_id)
            self._update_contact_status(phone_number, "Leads")
        else:
            # Pas intéressé
            self.play_audio_file(channel_id, "bye_failed.wav")
            self._update_contact_status(phone_number, "Not_interested")
        
        self.hangup_channel(channel_id)

    def _try_retry_streaming(self, channel_id: str, phone_number: str, campaign_id: str):
        """Tentative de relance en mode streaming"""
        logger.debug(f"🔄 Retry attempt for {phone_number}")
        
        self.play_audio_file(channel_id, "retry.wav", enable_barge_in=True)
        response = self._wait_for_streaming_response(channel_id, "retry", timeout=15.0)
        
        if response["intent"] in ["affirm", "interested"]:
            self._ask_streaming_questions(channel_id, phone_number, campaign_id)
        else:
            self.play_audio_file(channel_id, "bye_failed.wav")
            self._update_contact_status(phone_number, "Not_interested")
            self.hangup_channel(channel_id)

    def _confirm_callback_streaming(self, channel_id: str, phone_number: str, campaign_id: str):
        """Confirmation rappel en mode streaming"""
        self.play_audio_file(channel_id, "confirm.wav", enable_barge_in=True)
        response = self._wait_for_streaming_response(channel_id, "confirm", timeout=10.0)
        
        self.play_audio_file(channel_id, "bye_success.wav")

    def _update_contact_status(self, phone_number: str, status: str):
        """Met à jour le statut d'un contact (compatible existant)"""
        try:
            from models import Contact
            db = SessionLocal()
            
            contact = db.query(Contact).filter(Contact.phone == phone_number).first()
            if contact:
                contact.status = status
                db.commit()
                logger.debug(f"📊 Contact {phone_number} → {status}")
            
            db.close()
            
        except Exception as e:
            logger.error(f"❌ Failed to update contact status: {e}")

    # =============================================================================
    # MÉTHODES UTILITAIRES ET MONITORING
    # =============================================================================
    
    def get_stats(self) -> Dict[str, Any]:
        """Retourne les statistiques du robot"""
        return {
            "mode": "streaming",
            "active_calls": len(self.active_calls),
            "streaming_sessions": len(self.streaming_sessions) if hasattr(self, 'streaming_sessions') else 0,
            "services_available": {
                "streaming": STREAMING_SERVICES_AVAILABLE,
                "scenarios": SCENARIOS_AVAILABLE
            }
        }

    def run(self):
        """Lance le robot"""
        if not STREAMING_SERVICES_AVAILABLE:
            logger.error("❌ Cannot start robot - streaming services not available")
            return
            
        logger.info("🚀 Starting Robot ARI Streaming")
        self.ws.run_forever()

    def stop(self):
        """Arrête le robot"""
        logger.info("🛑 Stopping Robot ARI Streaming")
        self.running = False
        if self.ws:
            self.ws.close()

# Instance globale
robot = RobotARIStreaming()

if __name__ == "__main__":
    try:
        robot.run()
    except KeyboardInterrupt:
        logger.info("🛑 Shutdown requested by user")
        robot.stop()
    except Exception as e:
        logger.error(f"❌ Fatal error: {e}", exc_info=True)
        robot.stop()