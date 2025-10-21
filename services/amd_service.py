#!/usr/bin/env python3
"""
AMD (Answering Machine Detection) Service - MiniBotPanel v2
Module hybride combinant AMD Asterisk + analyse Python intelligente
Compatible avec architecture streaming et classic
"""

import numpy as np
import json
import time
import re
from typing import Dict, Optional, Tuple, List, Any
from datetime import datetime
from enum import Enum

# Import des configurations et services existants
import config
from logger_config import get_logger

logger = get_logger(__name__)

# Import WebRTC VAD pour analyse temps réel
try:
    import webrtcvad
    VAD_AVAILABLE = True
    logger.info("✅ WebRTC VAD imported successfully for AMD")
except ImportError as e:
    VAD_AVAILABLE = False
    logger.warning(f"⚠️ WebRTC VAD not available: {e}. Python AMD will be limited.")

# Import Vosk pour détection keywords si disponible
try:
    from vosk import Model, KaldiRecognizer
    VOSK_AVAILABLE = True
except ImportError:
    VOSK_AVAILABLE = False

class AMDResult(Enum):
    """Résultats possibles de l'AMD"""
    HUMAN = "HUMAN"
    MACHINE = "MACHINE" 
    NOTSURE = "NOTSURE"
    ERROR = "ERROR"

class AMDService:
    """
    Service AMD hybride pour MiniBotPanel v2
    Combine AMD Asterisk (rapide) + analyse Python (précise)
    """

    def __init__(self):
        self.logger = get_logger(f"{__name__}.AMDService")
        self.is_available = VAD_AVAILABLE
        
        # Configuration VAD
        if VAD_AVAILABLE:
            self.vad = webrtcvad.Vad(config.VAD_MODE)
            self.sample_rate = 16000
            self.frame_duration_ms = 20  # 20ms frames pour AMD
            self.frame_size = int(self.sample_rate * self.frame_duration_ms / 1000)
        
        # Modèle Vosk pour keyword detection (optionnel)
        self.vosk_model = None
        if VOSK_AVAILABLE and hasattr(config, 'VOSK_MODEL_PATH'):
            try:
                self.vosk_model = Model(config.VOSK_MODEL_PATH)
                logger.info("✅ Vosk model loaded for AMD keyword detection")
            except Exception as e:
                logger.warning(f"⚠️ Failed to load Vosk for AMD: {e}")
        
        # Mots-clés indicateurs de répondeur
        self.vm_keywords = [
            "laissez un message", "laissez votre message", "après le bip", 
            "après le signal", "bip sonore", "enregistrer votre message",
            "nous rappeler", "nous recontacter", "indisponible", 
            "absents", "absent", "messagerie", "répondeur",
            "pas disponible", "pas là", "joignable",
            "ne suis pas", "ne peut pas", "n'est pas là"
        ]
        
        # Statistiques
        self.stats = {
            "total_analyses": 0,
            "asterisk_decisions": 0,
            "python_decisions": 0,
            "human_detected": 0,
            "machine_detected": 0,
            "uncertain_cases": 0,
            "avg_analysis_time_ms": 0.0,
            "beep_detections": 0,
            "keyword_detections": 0
        }

    def analyze_asterisk_amd(self, amd_status: str, amd_cause: str = "") -> Tuple[AMDResult, float, Dict[str, Any]]:
        """
        Analyse le résultat AMD d'Asterisk
        
        Args:
            amd_status: HUMAN, MACHINE, NOTSURE (depuis Asterisk)
            amd_cause: Cause détaillée si disponible
            
        Returns:
            Tuple[result, confidence, metadata]
        """
        self.stats["total_analyses"] += 1
        self.stats["asterisk_decisions"] += 1
        
        metadata = {
            "method": "asterisk_amd",
            "amd_status": amd_status,
            "amd_cause": amd_cause,
            "timestamp": time.time()
        }
        
        if amd_status == "HUMAN":
            self.stats["human_detected"] += 1
            return AMDResult.HUMAN, 0.8, metadata
            
        elif amd_status == "MACHINE":
            self.stats["machine_detected"] += 1
            return AMDResult.MACHINE, 0.9, metadata
            
        elif amd_status == "NOTSURE":
            self.stats["uncertain_cases"] += 1
            return AMDResult.NOTSURE, 0.5, metadata
            
        else:
            return AMDResult.ERROR, 0.0, {**metadata, "error": f"Unknown AMD status: {amd_status}"}

    def analyze_audio_stream(self, audio_frames: List[bytes], max_analysis_time: float = 7.0) -> Tuple[AMDResult, float, Dict[str, Any]]:
        """
        Analyse Python temps réel sur flux audio
        
        Args:
            audio_frames: Liste de frames audio SLIN16 
            max_analysis_time: Temps max d'analyse en secondes
            
        Returns:
            Tuple[result, confidence, metadata]
        """
        if not self.is_available:
            return AMDResult.ERROR, 0.0, {"error": "VAD not available"}
        
        start_time = time.time()
        self.stats["total_analyses"] += 1
        self.stats["python_decisions"] += 1
        
        # Accumulateurs pour analyse
        total_speech_duration = 0.0
        total_silence_duration = 0.0
        current_speech_segment = 0.0
        current_silence_segment = 0.0
        longest_speech_segment = 0.0
        speech_segments = []
        in_speech = False
        frame_duration_s = self.frame_duration_ms / 1000.0
        
        # Détection de beep
        beep_detected = False
        beep_count = 0
        
        # Transcription pour keywords (si Vosk disponible)
        transcription = ""
        recognizer = None
        if self.vosk_model:
            recognizer = KaldiRecognizer(self.vosk_model, self.sample_rate)
            recognizer.SetWords(True)
        
        # Analyser chaque frame
        for i, frame in enumerate(audio_frames):
            # Limite temporelle
            elapsed = time.time() - start_time
            if elapsed > max_analysis_time:
                break
                
            if len(frame) != self.frame_size * 2:  # SLIN16 = 2 bytes par sample
                continue
                
            try:
                # VAD - Voice Activity Detection
                is_speech = self.vad.is_speech(frame, self.sample_rate)
                
                if is_speech:
                    if not in_speech:
                        # Début d'un segment de parole
                        if current_silence_segment > 0:
                            total_silence_duration += current_silence_segment
                            current_silence_segment = 0.0
                        in_speech = True
                    
                    current_speech_segment += frame_duration_s
                    total_speech_duration += frame_duration_s
                    
                else:
                    if in_speech:
                        # Fin d'un segment de parole
                        speech_segments.append(current_speech_segment)
                        longest_speech_segment = max(longest_speech_segment, current_speech_segment)
                        total_speech_duration += current_speech_segment
                        current_speech_segment = 0.0
                        in_speech = False
                    
                    current_silence_segment += frame_duration_s
                
                # Détection de beep par analyse spectrale
                if self._detect_beep_in_frame(frame):
                    beep_count += 1
                    if beep_count >= 3:  # Confirmer le beep
                        beep_detected = True
                        self.stats["beep_detections"] += 1
                
                # Transcription pour keywords
                if recognizer and recognizer.AcceptWaveform(frame):
                    result = json.loads(recognizer.Result())
                    text = result.get("text", "")
                    if text:
                        transcription += " " + text
                
            except Exception as e:
                self.logger.warning(f"⚠️ Error processing AMD frame {i}: {e}")
                continue
        
        # Finaliser les segments en cours
        if in_speech and current_speech_segment > 0:
            speech_segments.append(current_speech_segment)
            longest_speech_segment = max(longest_speech_segment, current_speech_segment)
        
        # Analyse finale
        analysis_time_ms = (time.time() - start_time) * 1000
        self._update_analysis_time_stats(analysis_time_ms)
        
        # Détection de mots-clés de répondeur
        vm_keywords_found = self._detect_vm_keywords(transcription)
        if vm_keywords_found:
            self.stats["keyword_detections"] += 1
        
        # Logique de décision
        result, confidence = self._make_decision(
            total_speech_duration=total_speech_duration,
            total_silence_duration=total_silence_duration,
            longest_speech_segment=longest_speech_segment,
            speech_segments=speech_segments,
            beep_detected=beep_detected,
            vm_keywords_found=vm_keywords_found,
            transcription=transcription
        )
        
        # Métadonnées détaillées
        metadata = {
            "method": "python_analysis",
            "analysis_time_ms": analysis_time_ms,
            "total_speech_duration": total_speech_duration,
            "total_silence_duration": total_silence_duration,
            "longest_speech_segment": longest_speech_segment,
            "speech_segments_count": len(speech_segments),
            "beep_detected": beep_detected,
            "beep_count": beep_count,
            "vm_keywords_found": vm_keywords_found,
            "transcription": transcription.strip(),
            "frames_processed": len(audio_frames),
            "timestamp": time.time()
        }
        
        # Mise à jour stats
        if result == AMDResult.HUMAN:
            self.stats["human_detected"] += 1
        elif result == AMDResult.MACHINE:
            self.stats["machine_detected"] += 1
        else:
            self.stats["uncertain_cases"] += 1
        
        self.logger.debug(f"🤖 Python AMD: {result.value} ({confidence:.2f}) in {analysis_time_ms:.1f}ms")
        return result, confidence, metadata

    def _detect_beep_in_frame(self, frame: bytes) -> bool:
        """Détecte un beep de répondeur dans une frame audio"""
        try:
            # Convertir en numpy array
            audio_data = np.frombuffer(frame, dtype=np.int16).astype(np.float32) / 32768.0
            
            # FFT pour analyse spectrale
            spectrum = np.abs(np.fft.rfft(audio_data))
            freqs = np.fft.rfftfreq(len(audio_data), 1/self.sample_rate)
            
            # Chercher pic entre 800-2000 Hz (fréquence beep typique)
            beep_band = (freqs >= 800) & (freqs <= 2000)
            other_band = freqs < 800
            
            if len(spectrum[beep_band]) == 0 or len(spectrum[other_band]) == 0:
                return False
            
            beep_energy = spectrum[beep_band].mean()
            other_energy = spectrum[other_band].mean()
            
            # Ratio énergie beep vs reste
            if other_energy > 0:
                ratio = beep_energy / other_energy
                return ratio > 3.0  # Seuil ajustable
            
            return False
            
        except Exception as e:
            self.logger.debug(f"Error in beep detection: {e}")
            return False

    def _detect_vm_keywords(self, transcription: str) -> List[str]:
        """Détecte les mots-clés de répondeur dans la transcription"""
        if not transcription:
            return []
        
        text_lower = transcription.lower()
        found_keywords = []
        
        for keyword in self.vm_keywords:
            if keyword in text_lower:
                found_keywords.append(keyword)
        
        return found_keywords

    def _make_decision(self, total_speech_duration: float, total_silence_duration: float,
                      longest_speech_segment: float, speech_segments: List[float],
                      beep_detected: bool, vm_keywords_found: List[str],
                      transcription: str) -> Tuple[AMDResult, float]:
        """
        Logique de décision AMD basée sur l'analyse
        """
        confidence = 0.5
        
        # Règle 1: Beep détecté = Machine (haute confiance)
        if beep_detected:
            return AMDResult.MACHINE, 0.95
        
        # Règle 2: Mots-clés VM détectés = Machine
        if vm_keywords_found:
            confidence = 0.9 - (len(vm_keywords_found) * 0.1)  # Plus de mots-clés = plus sûr
            return AMDResult.MACHINE, min(confidence, 0.95)
        
        # Règle 3: Longue tirade initiale = Machine
        if longest_speech_segment > config.AMD_MACHINE_SPEECH_THRESHOLD:
            confidence = 0.8 + min((longest_speech_segment - config.AMD_MACHINE_SPEECH_THRESHOLD) * 0.1, 0.15)
            return AMDResult.MACHINE, confidence
        
        # Règle 4: Courte salutation = Humain
        if longest_speech_segment < config.AMD_HUMAN_SPEECH_THRESHOLD:
            # Vérifier qu'il y a bien eu de la parole
            if total_speech_duration > 0.5:  # Au moins 500ms de parole
                confidence = 0.75 + min((config.AMD_HUMAN_SPEECH_THRESHOLD - longest_speech_segment) * 0.1, 0.2)
                return AMDResult.HUMAN, confidence
        
        # Règle 5: Pattern de pauses courtes = Humain (respiration)
        if len(speech_segments) >= 2:
            short_segments = [s for s in speech_segments if s < 1.0]  # Segments < 1s
            if len(short_segments) >= 2:
                return AMDResult.HUMAN, 0.7
        
        # Règle 6: Très peu de parole = Silence/Erreur
        if total_speech_duration < 0.3:
            return AMDResult.NOTSURE, 0.3
        
        # Cas par défaut
        return AMDResult.NOTSURE, 0.5

    def analyze_hybrid(self, amd_status: str, audio_frames: List[bytes] = None, 
                      amd_cause: str = "") -> Tuple[AMDResult, float, Dict[str, Any]]:
        """
        Analyse hybride combinant Asterisk + Python
        
        Args:
            amd_status: Résultat AMD Asterisk
            audio_frames: Frames audio pour analyse Python (optionnel)
            amd_cause: Cause AMD Asterisk
            
        Returns:
            Tuple[result, confidence, metadata]
        """
        start_time = time.time()
        
        # Étape 1: Analyser résultat Asterisk
        asterisk_result, asterisk_confidence, asterisk_metadata = self.analyze_asterisk_amd(amd_status, amd_cause)
        
        # Si Asterisk est sûr de sa décision et qu'on n'a pas d'audio, utiliser Asterisk
        if asterisk_result in [AMDResult.MACHINE] and asterisk_confidence > 0.8:
            if not audio_frames or not self.is_available:
                return asterisk_result, asterisk_confidence, {
                    **asterisk_metadata,
                    "decision_method": "asterisk_only",
                    "reason": "high_confidence_asterisk"
                }
        
        # Étape 2: Analyse Python si disponible et nécessaire
        python_result = None
        python_confidence = 0.0
        python_metadata = {}
        
        if audio_frames and self.is_available and config.AMD_PYTHON_ENABLED:
            try:
                python_result, python_confidence, python_metadata = self.analyze_audio_stream(audio_frames)
            except Exception as e:
                self.logger.error(f"❌ Python AMD analysis failed: {e}")
                python_result = AMDResult.ERROR
                python_confidence = 0.0
                python_metadata = {"error": str(e)}
        
        # Étape 3: Combinaison des résultats
        if python_result and python_result != AMDResult.ERROR:
            final_result, final_confidence = self._combine_results(
                asterisk_result, asterisk_confidence,
                python_result, python_confidence
            )
            decision_method = "hybrid"
        else:
            final_result = asterisk_result
            final_confidence = asterisk_confidence
            decision_method = "asterisk_fallback"
        
        # Métadonnées combinées
        combined_metadata = {
            "decision_method": decision_method,
            "asterisk": asterisk_metadata,
            "python": python_metadata,
            "final_result": final_result.value,
            "final_confidence": final_confidence,
            "total_analysis_time_ms": (time.time() - start_time) * 1000,
            "timestamp": time.time()
        }
        
        self.logger.info(f"🔍 Hybrid AMD: {final_result.value} ({final_confidence:.2f}) - {decision_method}")
        return final_result, final_confidence, combined_metadata

    def _combine_results(self, asterisk_result: AMDResult, asterisk_confidence: float,
                        python_result: AMDResult, python_confidence: float) -> Tuple[AMDResult, float]:
        """Combine les résultats Asterisk et Python"""
        
        # Si les deux sont d'accord
        if asterisk_result == python_result:
            # Prendre la confiance la plus élevée
            combined_confidence = max(asterisk_confidence, python_confidence)
            return asterisk_result, combined_confidence
        
        # Si l'un des deux est très confiant
        if python_confidence > 0.9:
            return python_result, python_confidence
        if asterisk_confidence > 0.9:
            return asterisk_result, asterisk_confidence
        
        # Logique de priorité
        # Python MACHINE a priorité sur Asterisk HUMAN (plus précis)
        if python_result == AMDResult.MACHINE and asterisk_result == AMDResult.HUMAN:
            if python_confidence > 0.7:
                return python_result, python_confidence
        
        # Asterisk MACHINE a priorité sur Python HUMAN (AMD hardware fiable)
        if asterisk_result == AMDResult.MACHINE and python_result == AMDResult.HUMAN:
            if asterisk_confidence > 0.7:
                return asterisk_result, asterisk_confidence
        
        # En cas de doute, privilégier le résultat avec la plus haute confiance
        if python_confidence > asterisk_confidence:
            return python_result, python_confidence
        else:
            return asterisk_result, asterisk_confidence

    def _update_analysis_time_stats(self, analysis_time_ms: float):
        """Met à jour les statistiques de temps d'analyse"""
        if self.stats["python_decisions"] == 1:
            self.stats["avg_analysis_time_ms"] = analysis_time_ms
        else:
            # Moyenne mobile
            self.stats["avg_analysis_time_ms"] = (
                self.stats["avg_analysis_time_ms"] * 0.9 + analysis_time_ms * 0.1
            )

    def get_stats(self) -> Dict[str, Any]:
        """Retourne les statistiques du service AMD"""
        total = self.stats["total_analyses"]
        return {
            **self.stats,
            "is_available": self.is_available,
            "vad_available": VAD_AVAILABLE,
            "vosk_available": VOSK_AVAILABLE and self.vosk_model is not None,
            "human_rate_percent": (self.stats["human_detected"] / max(total, 1)) * 100,
            "machine_rate_percent": (self.stats["machine_detected"] / max(total, 1)) * 100,
            "uncertainty_rate_percent": (self.stats["uncertain_cases"] / max(total, 1)) * 100
        }

    def get_asterisk_amd_config(self) -> str:
        """Génère la configuration AMD pour Asterisk"""
        return f"""AMD({config.AMD_INITIAL_SILENCE},{config.AMD_GREETING},{config.AMD_AFTER_GREETING_SILENCE},{config.AMD_TOTAL_ANALYSIS_TIME},{config.AMD_MIN_WORD_LENGTH},{config.AMD_BETWEEN_WORDS_SILENCE})"""

# Instance globale du service (singleton pattern)
amd_service = AMDService()

if __name__ == "__main__":
    # Test standalone
    def test_amd_service():
        logger.info("🧪 Testing AMD Service in standalone mode")
        
        # Test 1: AMD Asterisk seul
        print("=== Test 1: Asterisk AMD Results ===")
        test_cases = [
            ("HUMAN", ""),
            ("MACHINE", ""),
            ("NOTSURE", "LONGGREETING"),
            ("INVALID", "")
        ]
        
        for status, cause in test_cases:
            result, confidence, metadata = amd_service.analyze_asterisk_amd(status, cause)
            print(f"Status: {status} → Result: {result.value} | Confidence: {confidence:.2f}")
        
        # Test 2: Générer config Asterisk
        print(f"\n=== Test 2: Asterisk Config ===")
        print(f"AMD Config: {amd_service.get_asterisk_amd_config()}")
        
        # Test 3: Stats
        print(f"\n=== Test 3: Stats ===")
        stats = amd_service.get_stats()
        print(json.dumps(stats, indent=2))
        
        # Test 4: Keywords detection
        print(f"\n=== Test 4: VM Keywords Detection ===")
        test_texts = [
            "Bonjour vous êtes bien chez Paul",
            "Laissez votre message après le bip",
            "Je ne suis pas disponible, merci de rappeler",
            "Nous sommes absents, laissez un message"
        ]
        
        for text in test_texts:
            keywords = amd_service._detect_vm_keywords(text)
            print(f"Text: '{text}' → Keywords: {keywords}")
    
    test_amd_service()