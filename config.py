import os
from dotenv import load_dotenv

load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://robot:password@localhost/robot_calls")

ARI_URL = os.getenv("ARI_URL", "http://localhost:8088")
ARI_USERNAME = os.getenv("ARI_USERNAME", "robot")
ARI_PASSWORD = os.getenv("ARI_PASSWORD", "password")

WHISPER_MODEL = os.getenv("WHISPER_MODEL", "small")  # Utiliser small comme dans les logs
WHISPER_DEVICE = os.getenv("WHISPER_DEVICE", "cpu")  # Temporairement CPU pour éviter l'erreur cuDNN
WHISPER_COMPUTE_TYPE = os.getenv("WHISPER_COMPUTE_TYPE", "int8")  # int8 pour CPU

RECORDINGS_PATH = os.getenv("RECORDINGS_PATH", "/var/spool/asterisk/recording")
SOUNDS_PATH = os.getenv("SOUNDS_PATH", "/var/lib/asterisk/sounds/custom")

LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")
LOG_FILE = os.getenv("LOG_FILE", "logs/robot.log")

# Public API URL for exports (used in client exports)
PUBLIC_API_URL = os.getenv("PUBLIC_API_URL", "http://localhost:8000")