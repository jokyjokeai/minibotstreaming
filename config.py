import os
from dotenv import load_dotenv

load_dotenv()

# =============================================================================
# DATABASE & API (Configuration existante gardée)
# =============================================================================
DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://robot:password@localhost/robot_calls")

ARI_URL = os.getenv("ARI_URL", "http://localhost:8088")
ARI_USERNAME = os.getenv("ARI_USERNAME", "robot")
ARI_PASSWORD = os.getenv("ARI_PASSWORD", "password")

# Public API URL for exports (used in client exports)
PUBLIC_API_URL = os.getenv("PUBLIC_API_URL", "http://localhost:8000")

# =============================================================================
# MODE DE FONCTIONNEMENT - STREAMING ONLY
# =============================================================================
# Streaming toujours activé - mode classic supprimé
STREAMING_MODE = True

# Whisper gardé uniquement pour fallback d'urgence (si Vosk échoue)
WHISPER_MODEL = os.getenv("WHISPER_MODEL", "small")  
WHISPER_DEVICE = os.getenv("WHISPER_DEVICE", "cpu")  
WHISPER_COMPUTE_TYPE = os.getenv("WHISPER_COMPUTE_TYPE", "int8")  

# =============================================================================
# TRANSCRIPTION - MODE STREAMING (Vosk)
# =============================================================================
VOSK_MODEL_PATH = os.getenv("VOSK_MODEL_PATH", "models/vosk-fr")
VOSK_SAMPLE_RATE = int(os.getenv("VOSK_SAMPLE_RATE", "16000"))

# =============================================================================
# NLP & INTENT (Ollama Local)
# =============================================================================
OLLAMA_URL = os.getenv("OLLAMA_URL", "http://localhost:11434")
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "phi3")
OLLAMA_TIMEOUT = int(os.getenv("OLLAMA_TIMEOUT", "10"))  # secondes

# Fallback sur sentiment analysis keywords si Ollama indisponible (fallback d'urgence uniquement)
OLLAMA_FALLBACK_TO_KEYWORDS = os.getenv("OLLAMA_FALLBACK_TO_KEYWORDS", "true").lower() == "true"

# =============================================================================
# AUDIO STREAMING (AudioFork WebSocket)
# =============================================================================
AUDIOFORK_HOST = os.getenv("AUDIOFORK_HOST", "127.0.0.1")
AUDIOFORK_PORT = int(os.getenv("AUDIOFORK_PORT", "8765"))
AUDIOFORK_URL = f"ws://{AUDIOFORK_HOST}:{AUDIOFORK_PORT}"

# Configuration VAD (Voice Activity Detection)
VAD_MODE = int(os.getenv("VAD_MODE", "2"))  # 0=loose, 1=normal, 2=tight, 3=very tight
VAD_FRAME_DURATION = int(os.getenv("VAD_FRAME_DURATION", "30"))  # ms (10, 20, 30)

# =============================================================================
# BARGE-IN & LATENCE
# =============================================================================
BARGE_IN_ENABLED = os.getenv("BARGE_IN_ENABLED", "true").lower() == "true"

# Latences cibles (millisecondes)
TARGET_BARGE_IN_LATENCY = int(os.getenv("TARGET_BARGE_IN_LATENCY", "150"))  # < 150ms
TARGET_ASR_LATENCY = int(os.getenv("TARGET_ASR_LATENCY", "400"))  # < 400ms  
TARGET_INTENT_LATENCY = int(os.getenv("TARGET_INTENT_LATENCY", "600"))  # < 600ms
TARGET_TOTAL_LATENCY = int(os.getenv("TARGET_TOTAL_LATENCY", "1000"))  # < 1s

# =============================================================================
# AMD (Answering Machine Detection) - HYBRIDE
# =============================================================================
# AMD Asterisk (premier niveau - rapide)
AMD_ENABLED = os.getenv("AMD_ENABLED", "true").lower() == "true"
AMD_INITIAL_SILENCE = int(os.getenv("AMD_INITIAL_SILENCE", "2000"))  # ms
AMD_GREETING = int(os.getenv("AMD_GREETING", "5000"))  # ms
AMD_AFTER_GREETING_SILENCE = int(os.getenv("AMD_AFTER_GREETING_SILENCE", "800"))  # ms
AMD_TOTAL_ANALYSIS_TIME = int(os.getenv("AMD_TOTAL_ANALYSIS_TIME", "7000"))  # ms
AMD_MIN_WORD_LENGTH = int(os.getenv("AMD_MIN_WORD_LENGTH", "100"))  # ms
AMD_BETWEEN_WORDS_SILENCE = int(os.getenv("AMD_BETWEEN_WORDS_SILENCE", "50"))  # ms

# AMD Python (deuxième niveau - intelligent)
AMD_PYTHON_ENABLED = os.getenv("AMD_PYTHON_ENABLED", "true").lower() == "true"
AMD_MACHINE_SPEECH_THRESHOLD = float(os.getenv("AMD_MACHINE_SPEECH_THRESHOLD", "2.8"))  # secondes
AMD_HUMAN_SPEECH_THRESHOLD = float(os.getenv("AMD_HUMAN_SPEECH_THRESHOLD", "1.2"))  # secondes
AMD_SILENCE_THRESHOLD = float(os.getenv("AMD_SILENCE_THRESHOLD", "0.9"))  # secondes
AMD_BEEP_DETECTION_ENABLED = os.getenv("AMD_BEEP_DETECTION_ENABLED", "true").lower() == "true"

# =============================================================================
# AUDIO & CHEMINS (Configuration existante gardée)
# =============================================================================
RECORDINGS_PATH = os.getenv("RECORDINGS_PATH", "/var/spool/asterisk/recording")
SOUNDS_PATH = os.getenv("SOUNDS_PATH", "/var/lib/asterisk/sounds/minibot")

# =============================================================================
# LOGS (Configuration existante gardée)
# =============================================================================
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")
LOG_FILE = os.getenv("LOG_FILE", "logs/robot.log")

# Logs spécifiques streaming
STREAMING_LOG_FILE = os.getenv("STREAMING_LOG_FILE", "logs/streaming.log")
AMD_LOG_FILE = os.getenv("AMD_LOG_FILE", "logs/amd.log")