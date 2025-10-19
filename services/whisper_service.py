from typing import Dict, Optional
from faster_whisper import WhisperModel
import config
import os
import subprocess
import tempfile
from logger_config import get_logger

logger = get_logger(__name__)

class WhisperService:
    """Service for audio transcription using faster-whisper with GPU support"""

    def __init__(self):
        self.model = None
        self._model_loaded = False
        self._initialize_model()

    def _initialize_model(self):
        """Initialize Whisper model at startup (called once)"""
        try:
            # Déterminer le dossier de cache des modèles
            cache_dir = os.path.expanduser("~/.cache/huggingface/hub")

            # Vérifier si le modèle existe déjà dans le cache
            model_name = config.WHISPER_MODEL
            model_patterns = [
                f"{cache_dir}/models--Systran--faster-whisper-{model_name}",
                f"{cache_dir}/models--openai--whisper-{model_name}",
            ]

            model_cached = False
            for pattern in model_patterns:
                if os.path.exists(pattern):
                    model_cached = True
                    logger.info(f"✅ Model '{model_name}' found in cache: {pattern}")
                    break

            if not model_cached:
                logger.info(f"📥 Model '{model_name}' will be downloaded on first use")

            # Use CPU (optimal for VPS deployment)
            # CPU is sufficient: 3-4s transcription, no CUDA issues, works everywhere
            device = "cpu"
            compute_type = "int8"  # Optimal pour CPU

            logger.info(f"🤖 Initializing Whisper model: {config.WHISPER_MODEL} on {device}")
            logger.info(f"   Device: {device}")
            logger.info(f"   Compute type: {compute_type}")

            # Charger le modèle avec fallback CPU si GPU échoue
            try:
                self.model = WhisperModel(
                    config.WHISPER_MODEL,
                    device=device,
                    compute_type=compute_type,
                    download_root=cache_dir  # Utiliser le cache existant
                )
                self._model_loaded = True
                logger.info(f"✅ Whisper model loaded and ready on {device.upper()}!")
            except Exception as gpu_error:
                logger.warning(f"⚠️ GPU failed: {gpu_error}")
                logger.info("🔄 Falling back to CPU...")
                device = "cpu"
                compute_type = "int8"
                self.model = WhisperModel(
                    config.WHISPER_MODEL,
                    device=device,
                    compute_type=compute_type,
                    download_root=cache_dir
                )
                self._model_loaded = True
                logger.info("✅ Whisper model loaded on CPU (fallback)")

        except Exception as e:
            logger.error(f"❌ Failed to initialize Whisper model: {e}", exc_info=True)
            logger.warning("⚠️ Whisper will be unavailable, falling back to DEMO mode")
            self._model_loaded = False

    def normalize_audio(self, input_path: str) -> str:
        """
        Normalize audio volume to fix low-level recordings
        Returns path to normalized file (temporary)

        Uses aggressive amplification to fix VoIP recordings that are often very quiet
        """
        try:
            # Create temporary file for normalized audio
            temp_fd, temp_path = tempfile.mkstemp(suffix='.wav')
            os.close(temp_fd)

            # AGGRESSIVE normalization for VoIP recordings
            # Strategy: norm -0.1 = normalize to -0.1dB (near maximum, prevents clipping)
            # Then add gain +6dB to boost quiet voices even more
            # This is MUCH more aggressive than just gain -n
            cmd = f"sox {input_path} {temp_path} norm -0.1 gain 6"

            result = subprocess.run(cmd, shell=True, capture_output=True, text=True)

            if result.returncode == 0:
                logger.info(f"🔊 Audio AGGRESSIVELY normalized: {input_path} → {temp_path} (norm -0.1 + gain 6dB)")
                return temp_path
            else:
                # Fallback: try just norm without additional gain
                logger.warning(f"⚠️  Aggressive normalization failed, trying softer approach...")
                cmd_fallback = f"sox {input_path} {temp_path} norm -3"
                result_fallback = subprocess.run(cmd_fallback, shell=True, capture_output=True, text=True)

                if result_fallback.returncode == 0:
                    logger.info(f"🔊 Audio normalized (fallback): {input_path} → {temp_path}")
                    return temp_path
                else:
                    logger.warning(f"⚠️  Audio normalization failed completely: {result_fallback.stderr}")
                    return input_path  # Return original if both fail

        except Exception as e:
            logger.warning(f"⚠️  Audio normalization error: {e}")
            return input_path  # Return original on error

    def transcribe(self, audio_path: str, language: str = "fr") -> Dict:
        """
        Transcribe an audio file

        Args:
            audio_path: Path to the WAV audio file
            language: Language code (default: "fr")

        Returns:
            Dictionary with transcription results:
            {
                "text": "transcription complète",
                "language": "fr",
                "language_probability": 0.98,
                "duration": 12.5
            }
        """
        # Vérifier si le modèle est chargé
        if not self._model_loaded or self.model is None:
            logger.error("❌ Whisper model not loaded, cannot transcribe")
            return {
                "text": "",
                "language": language,
                "language_probability": 0.0,
                "duration": 0.0,
                "error": "Model not loaded"
            }

        try:
            logger.info(f"🎤 Transcribing audio: {audio_path}")

            # Vérifier que le fichier existe
            if not os.path.exists(audio_path):
                logger.error(f"❌ Audio file not found: {audio_path}")
                return {
                    "text": "",
                    "language": language,
                    "language_probability": 0.0,
                    "duration": 0.0,
                    "error": "File not found"
                }

            # Normalize audio to fix low-level recordings (common issue with VoIP)
            normalized_path = self.normalize_audio(audio_path)
            audio_to_transcribe = normalized_path

            try:
                segments, info = self.model.transcribe(
                    audio_to_transcribe,
                    language=language,
                    vad_filter=True,  # VAD aide à filtrer les silences
                    beam_size=1  # Réduit pour vitesse
                )
            finally:
                # Clean up temporary normalized file
                if normalized_path != audio_path and os.path.exists(normalized_path):
                    try:
                        os.unlink(normalized_path)
                    except:
                        pass  # Ignore cleanup errors

            # FIX: Convert generator to list immediately to avoid GPU hang
            # (known issue with faster-whisper on CUDA)
            segments_list = list(segments)

            # Combine all segments into full text
            full_text = ""
            for segment in segments_list:
                full_text += segment.text + " "

            full_text = full_text.strip()

            result = {
                "text": full_text,
                "language": info.language,
                "language_probability": info.language_probability,
                "duration": info.duration
            }

            logger.info(f"📝 Transcription completed: '{full_text[:50]}...' (language: {info.language}, prob: {info.language_probability:.2f})")

            return result

        except Exception as e:
            logger.error(f"❌ Transcription failed: {e}", exc_info=True)
            return {
                "text": "",
                "language": language,
                "language_probability": 0.0,
                "duration": 0.0,
                "error": str(e)
            }

# Global instance - loaded once at startup
whisper_service = WhisperService()