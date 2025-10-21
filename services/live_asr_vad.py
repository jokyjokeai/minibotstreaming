#!/usr/bin/env python3
"""
Live ASR & VAD Service - MiniBotPanel v2 Streaming
Module de transcription temps réel avec Voice Activity Detection
Compatible avec l'architecture existante MiniBotPanel v2
"""

import asyncio
import websockets
import webrtcvad
import numpy as np
import json
import time
import threading
from typing import Dict, Callable, Optional, Any
from datetime import datetime
from queue import Queue, Empty
import struct

# Import des configurations et logger existants
import config
from logger_config import get_logger

logger = get_logger(__name__)

try:
    from vosk import Model, KaldiRecognizer
    VOSK_AVAILABLE = True
    logger.info("✅ Vosk imported successfully for streaming ASR")
except ImportError as e:
    VOSK_AVAILABLE = False
    logger.warning(f"⚠️ Vosk not available: {e}. Streaming mode will be disabled.")

class LiveASRVAD:
    """
    Service de transcription temps réel avec détection d'activité vocale
    Intégré avec l'architecture MiniBotPanel v2 existante
    """

    def __init__(self):
        self.logger = get_logger(f"{__name__}.LiveASRVAD")
        self.is_available = VOSK_AVAILABLE
        
        if not self.is_available:
            self.logger.warning("🚫 LiveASRVAD service not available - missing dependencies")
            return
            
        # Configuration VAD
        self.vad = webrtcvad.Vad(config.VAD_MODE)
        self.sample_rate = config.VOSK_SAMPLE_RATE
        self.frame_duration_ms = config.VAD_FRAME_DURATION
        self.frame_size = int(self.sample_rate * self.frame_duration_ms / 1000)
        
        # Modèle Vosk
        self.model = None
        self.recognizers = {}  # {channel_id: KaldiRecognizer}
        
        # État streaming
        self.active_streams = {}  # {channel_id: stream_info}
        self.callbacks = {}  # {channel_id: callback_function}
        
        # WebSocket server
        self.websocket_server = None
        self.server_task = None
        
        # Statistiques & monitoring
        self.stats = {
            "active_streams": 0,
            "total_frames_processed": 0,
            "speech_frames": 0,
            "silence_frames": 0,
            "transcriptions": 0,
            "avg_latency_ms": 0.0
        }
        
        self._initialize_vosk_model()

    def _initialize_vosk_model(self):
        """Initialise le modèle Vosk au démarrage"""
        try:
            if not VOSK_AVAILABLE:
                return False
                
            self.logger.info(f"🧠 Loading Vosk model from {config.VOSK_MODEL_PATH}")
            start_time = time.time()
            
            self.model = Model(config.VOSK_MODEL_PATH)
            
            load_time = time.time() - start_time
            self.logger.info(f"✅ Vosk model loaded in {load_time:.2f}s")
            
            # Test recognizer
            test_rec = KaldiRecognizer(self.model, self.sample_rate)
            test_rec.SetWords(True)
            self.logger.info("✅ Vosk recognizer test successful")
            
            return True
            
        except Exception as e:
            self.logger.error(f"❌ Failed to load Vosk model: {e}")
            self.is_available = False
            return False

    def get_recognizer(self, channel_id: str) -> Optional[Any]:
        """Obtient ou crée un recognizer pour un channel"""
        if channel_id not in self.recognizers:
            if not self.model:
                return None
            try:
                rec = KaldiRecognizer(self.model, self.sample_rate)
                rec.SetWords(True)
                self.recognizers[channel_id] = rec
                self.logger.debug(f"🎤 Created new recognizer for channel {channel_id}")
            except Exception as e:
                self.logger.error(f"❌ Failed to create recognizer for {channel_id}: {e}")
                return None
        
        return self.recognizers.get(channel_id)

    async def start_websocket_server(self):
        """Lance le serveur WebSocket pour AudioFork"""
        if not self.is_available:
            self.logger.error("🚫 Cannot start WebSocket server - dependencies not available")
            return
            
        try:
            self.logger.info(f"🌐 Starting WebSocket server on {config.AUDIOFORK_HOST}:{config.AUDIOFORK_PORT}")
            
            self.websocket_server = await websockets.serve(
                self._handle_websocket_connection,
                config.AUDIOFORK_HOST,
                config.AUDIOFORK_PORT,
                max_size=None,  # Pas de limite de taille pour l'audio
                ping_interval=None  # Désactive ping pour performance
            )
            
            self.logger.info("✅ WebSocket server started successfully")
            
        except Exception as e:
            self.logger.error(f"❌ Failed to start WebSocket server: {e}")
            raise

    async def _handle_websocket_connection(self, websocket, path):
        """Gère une connexion WebSocket AudioFork"""
        # Extraire channel_id du path: /stream/{UNIQUEID}
        try:
            channel_id = path.split('/')[-1]
            self.logger.info(f"📞 New AudioFork connection for channel: {channel_id}")
            
            # Initialiser le stream
            self._initialize_stream(channel_id)
            
            # Buffer pour accumuler les données audio
            audio_buffer = b''
            
            async for message in websocket:
                if isinstance(message, bytes):
                    # Données audio SLIN16 16kHz
                    audio_buffer += message
                    
                    # Traiter par frames de VAD
                    while len(audio_buffer) >= self.frame_size * 2:  # 2 bytes par sample
                        frame_bytes = audio_buffer[:self.frame_size * 2]
                        audio_buffer = audio_buffer[self.frame_size * 2:]
                        
                        # Traitement temps réel
                        await self._process_audio_frame(channel_id, frame_bytes)
                        
        except websockets.exceptions.ConnectionClosed:
            self.logger.info(f"📞 AudioFork connection closed for channel: {channel_id}")
        except Exception as e:
            self.logger.error(f"❌ Error handling AudioFork connection: {e}")
        finally:
            self._cleanup_stream(channel_id)

    def _initialize_stream(self, channel_id: str):
        """Initialise un stream pour un channel"""
        self.active_streams[channel_id] = {
            "start_time": time.time(),
            "frame_count": 0,
            "speech_frames": 0,
            "silence_frames": 0,
            "current_speech_duration": 0.0,
            "current_silence_duration": 0.0,
            "in_speech": False,
            "partial_transcription": "",
            "final_transcription": "",
            "last_vad_result": False
        }
        
        # Créer recognizer pour ce channel
        self.get_recognizer(channel_id)
        
        self.stats["active_streams"] += 1
        self.logger.debug(f"🎤 Initialized stream for channel {channel_id}")

    async def _process_audio_frame(self, channel_id: str, frame_bytes: bytes):
        """Traite une frame audio en temps réel"""
        if channel_id not in self.active_streams:
            return
            
        start_time = time.time()
        stream_info = self.active_streams[channel_id]
        recognizer = self.get_recognizer(channel_id)
        
        if not recognizer:
            return
            
        try:
            # VAD - détection activité vocale
            is_speech = self.vad.is_speech(frame_bytes, self.sample_rate)
            
            # Mise à jour statistiques stream
            stream_info["frame_count"] += 1
            self.stats["total_frames_processed"] += 1
            
            frame_duration_s = self.frame_duration_ms / 1000.0
            
            if is_speech:
                stream_info["speech_frames"] += 1
                stream_info["current_speech_duration"] += frame_duration_s
                stream_info["current_silence_duration"] = 0.0
                self.stats["speech_frames"] += 1
                
                if not stream_info["in_speech"]:
                    # Début de parole détecté
                    stream_info["in_speech"] = True
                    self.logger.debug(f"🗣️ Speech start detected for {channel_id}")
                    await self._notify_speech_start(channel_id)
                    
            else:
                stream_info["silence_frames"] += 1
                stream_info["current_silence_duration"] += frame_duration_s
                self.stats["silence_frames"] += 1
                
                if stream_info["in_speech"]:
                    # Vérifier si fin de parole (silence prolongé)
                    if stream_info["current_silence_duration"] >= config.AMD_SILENCE_THRESHOLD:
                        stream_info["in_speech"] = False
                        self.logger.debug(f"🤐 Speech end detected for {channel_id}")
                        await self._notify_speech_end(channel_id)
            
            # ASR - Transcription streaming avec Vosk
            if recognizer.AcceptWaveform(frame_bytes):
                # Transcription finale
                result = json.loads(recognizer.Result())
                text = result.get("text", "").strip()
                
                if text:
                    stream_info["final_transcription"] = text
                    self.stats["transcriptions"] += 1
                    
                    # Calculer latence
                    latency_ms = (time.time() - start_time) * 1000
                    self._update_latency_stats(latency_ms)
                    
                    self.logger.debug(f"📝 Final transcription for {channel_id}: '{text}' ({latency_ms:.1f}ms)")
                    await self._notify_transcription(channel_id, text, "final", latency_ms)
                    
            else:
                # Transcription partielle
                partial_result = json.loads(recognizer.PartialResult())
                partial_text = partial_result.get("partial", "").strip()
                
                if partial_text and partial_text != stream_info["partial_transcription"]:
                    stream_info["partial_transcription"] = partial_text
                    
                    latency_ms = (time.time() - start_time) * 1000
                    self.logger.debug(f"📝 Partial transcription for {channel_id}: '{partial_text}' ({latency_ms:.1f}ms)")
                    await self._notify_transcription(channel_id, partial_text, "partial", latency_ms)
            
        except Exception as e:
            self.logger.error(f"❌ Error processing audio frame for {channel_id}: {e}")

    def _update_latency_stats(self, latency_ms: float):
        """Met à jour les statistiques de latence"""
        if self.stats["transcriptions"] == 1:
            self.stats["avg_latency_ms"] = latency_ms
        else:
            # Moyenne mobile
            self.stats["avg_latency_ms"] = (
                self.stats["avg_latency_ms"] * 0.9 + latency_ms * 0.1
            )

    async def _notify_speech_start(self, channel_id: str):
        """Notifie le début de parole (pour barge-in)"""
        if channel_id in self.callbacks:
            try:
                callback = self.callbacks[channel_id]
                if asyncio.iscoroutinefunction(callback):
                    await callback("speech_start", channel_id, {
                        "timestamp": time.time(),
                        "event": "speech_start"
                    })
                else:
                    callback("speech_start", channel_id, {
                        "timestamp": time.time(),
                        "event": "speech_start"
                    })
            except Exception as e:
                self.logger.error(f"❌ Error in speech_start callback for {channel_id}: {e}")

    async def _notify_speech_end(self, channel_id: str):
        """Notifie la fin de parole"""
        if channel_id in self.callbacks:
            try:
                callback = self.callbacks[channel_id]
                stream_info = self.active_streams.get(channel_id, {})
                
                data = {
                    "timestamp": time.time(),
                    "event": "speech_end",
                    "speech_duration": stream_info.get("current_speech_duration", 0.0),
                    "final_transcription": stream_info.get("final_transcription", "")
                }
                
                if asyncio.iscoroutinefunction(callback):
                    await callback("speech_end", channel_id, data)
                else:
                    callback("speech_end", channel_id, data)
                    
            except Exception as e:
                self.logger.error(f"❌ Error in speech_end callback for {channel_id}: {e}")

    async def _notify_transcription(self, channel_id: str, text: str, transcription_type: str, latency_ms: float):
        """Notifie une transcription (partielle ou finale)"""
        if channel_id in self.callbacks:
            try:
                callback = self.callbacks[channel_id]
                
                data = {
                    "timestamp": time.time(),
                    "event": "transcription",
                    "text": text,
                    "type": transcription_type,  # "partial" ou "final"
                    "latency_ms": latency_ms,
                    "meets_target": latency_ms < config.TARGET_ASR_LATENCY
                }
                
                if asyncio.iscoroutinefunction(callback):
                    await callback("transcription", channel_id, data)
                else:
                    callback("transcription", channel_id, data)
                    
            except Exception as e:
                self.logger.error(f"❌ Error in transcription callback for {channel_id}: {e}")

    def register_callback(self, channel_id: str, callback: Callable):
        """Enregistre un callback pour un channel"""
        self.callbacks[channel_id] = callback
        self.logger.debug(f"📋 Registered callback for channel {channel_id}")

    def unregister_callback(self, channel_id: str):
        """Désenregistre un callback"""
        if channel_id in self.callbacks:
            del self.callbacks[channel_id]
            self.logger.debug(f"📋 Unregistered callback for channel {channel_id}")

    def _cleanup_stream(self, channel_id: str):
        """Nettoie les ressources d'un stream"""
        if channel_id in self.active_streams:
            del self.active_streams[channel_id]
            self.stats["active_streams"] -= 1
            
        if channel_id in self.recognizers:
            del self.recognizers[channel_id]
            
        self.unregister_callback(channel_id)
        
        self.logger.debug(f"🧹 Cleaned up stream for channel {channel_id}")

    def get_stats(self) -> Dict[str, Any]:
        """Retourne les statistiques du service"""
        return {
            **self.stats,
            "is_available": self.is_available,
            "vosk_model_loaded": self.model is not None,
            "websocket_server_running": self.websocket_server is not None
        }

    def get_stream_info(self, channel_id: str) -> Optional[Dict[str, Any]]:
        """Retourne les informations d'un stream actif"""
        return self.active_streams.get(channel_id)

    async def stop(self):
        """Arrête le service"""
        self.logger.info("🛑 Stopping LiveASRVAD service")
        
        if self.websocket_server:
            self.websocket_server.close()
            await self.websocket_server.wait_closed()
            self.websocket_server = None
            
        # Nettoyer tous les streams
        for channel_id in list(self.active_streams.keys()):
            self._cleanup_stream(channel_id)
            
        self.logger.info("✅ LiveASRVAD service stopped")

# Instance globale du service (singleton pattern comme les autres services)
live_asr_vad_service = LiveASRVAD()

# Fonction pour démarrage automatique (appelée depuis robot_ari.py)
async def start_live_asr_service():
    """Démarre le service ASR/VAD en mode streaming"""
    if live_asr_vad_service.is_available:
        await live_asr_vad_service.start_websocket_server()
        return True
    else:
        logger.warning("⚠️ LiveASRVAD service not available - check dependencies")
        return False

if __name__ == "__main__":
    # Test en mode standalone
    async def test_callback(event_type, channel_id, data):
        print(f"📢 Event: {event_type} for {channel_id}: {data}")
    
    async def main():
        logger.info("🧪 Testing LiveASRVAD service in standalone mode")
        
        if not live_asr_vad_service.is_available:
            logger.error("❌ Service not available")
            return
            
        # Démarrer le service
        await live_asr_vad_service.start_websocket_server()
        
        # Enregistrer un callback de test
        live_asr_vad_service.register_callback("test-channel", test_callback)
        
        logger.info("✅ Service running. Connect AudioFork to ws://localhost:8765/stream/test-channel")
        logger.info("📊 Stats available at live_asr_vad_service.get_stats()")
        
        # Garder le service en vie
        try:
            await asyncio.Future()  # Run forever
        except KeyboardInterrupt:
            logger.info("🛑 Shutting down test")
            await live_asr_vad_service.stop()
    
    asyncio.run(main())