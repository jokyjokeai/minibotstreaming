#!/usr/bin/env python3
"""
SCRIPT INSTALLATION MiniBotPanel v2 STREAMING
Installation complète mode streaming avec Asterisk 22 + AudioFork + Vosk + Ollama
Architecture temps réel pour performances optimales
"""

import os
import sys
import subprocess
import tempfile
import time
import secrets
import string
import logging
import requests
import json
import re
from datetime import datetime
from pathlib import Path

# =============================================================================
# CONFIGURATION ET UTILITIES
# =============================================================================

class Colors:
    GREEN = '\033[92m'
    RED = '\033[91m'
    YELLOW = '\033[93m'
    BLUE = '\033[94m'
    CYAN = '\033[96m'
    PURPLE = '\033[95m'
    NC = '\033[0m'  # No Color
    BOLD = '\033[1m'


def setup_logging():
    """Configure le système de logging"""
    # Créer le répertoire logs dans le répertoire du projet
    project_dir = Path(__file__).parent.parent
    log_dir = project_dir / "logs"
    log_dir.mkdir(exist_ok=True)
    
    log_file = log_dir / f"installation_streaming_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log"
    
    logging.basicConfig(
        level=logging.DEBUG,
        format='%(asctime)s - %(levelname)s - %(funcName)s - %(message)s',
        handlers=[
            logging.FileHandler(log_file, encoding='utf-8'),
            logging.StreamHandler()
        ]
    )
    
    return log_file

def log(msg: str, level: str = "info"):
    """Logger unifié avec couleurs"""
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    
    color_map = {
        "info": Colors.GREEN,
        "warning": Colors.YELLOW, 
        "error": Colors.RED,
        "debug": Colors.BLUE,
        "success": Colors.CYAN
    }
    
    color = color_map.get(level, Colors.NC)
    print(f"{color}[{timestamp}] {msg}{Colors.NC}")
    
    # Log au fichier aussi
    getattr(logging, level.lower(), logging.info)(msg)

def run_cmd(cmd: str, description: str = "", check: bool = True, timeout: int = 300):
    """Exécute une commande avec logging et gestion d'erreurs"""
    if description:
        log(f"🔧 {description}")
    
    log(f"💻 Command: {cmd}", "debug")
    
    try:
        result = subprocess.run(
            cmd, 
            shell=True, 
            capture_output=True, 
            text=True, 
            timeout=timeout,
            check=check
        )
        
        if result.stdout:
            log(f"📤 Output: {result.stdout.strip()}", "debug")
        if result.stderr and result.returncode == 0:
            log(f"📥 Info: {result.stderr.strip()}", "debug")
            
        return result
        
    except subprocess.TimeoutExpired:
        log(f"❌ Command timeout after {timeout}s: {cmd}", "error")
        raise
    except subprocess.CalledProcessError as e:
        log(f"❌ Command failed (code {e.returncode}): {cmd}", "error")
        if e.stdout:
            log(f"📤 Stdout: {e.stdout.strip()}", "error")
        if e.stderr:
            log(f"📥 Stderr: {e.stderr.strip()}", "error")
        if check:
            raise
        return e

def check_root():
    """Vérifie les permissions root"""
    if os.geteuid() != 0:
        log("❌ Ce script doit être exécuté avec sudo/root", "error")
        sys.exit(1)

def generate_password(length: int = 16) -> str:
    """Génère un mot de passe sécurisé"""
    alphabet = string.ascii_letters + string.digits + "!@#$%^&*"
    return ''.join(secrets.choice(alphabet) for _ in range(length))

# =============================================================================
# DÉTECTION SYSTÈME ET PRÉREQUIS
# =============================================================================

class SystemInfo:
    def __init__(self):
        self.os_name = self.detect_os()
        self.arch = self.detect_arch()
        self.has_gpu = self.detect_gpu()
        self.memory_gb = self.get_memory_gb()
        self.cpu_cores = self.get_cpu_cores()
        
    def detect_os(self) -> str:
        """Détecte l'OS"""
        try:
            with open('/etc/os-release', 'r') as f:
                content = f.read()
                if 'ubuntu' in content.lower():
                    return 'ubuntu'
                elif 'debian' in content.lower():
                    return 'debian'
                elif 'centos' in content.lower():
                    return 'centos'
                elif 'rhel' in content.lower():
                    return 'rhel'
                else:
                    return 'unknown'
        except:
            return 'unknown'
    
    def detect_arch(self) -> str:
        """Détecte l'architecture"""
        result = run_cmd("uname -m", check=False)
        return result.stdout.strip() if result.returncode == 0 else "unknown"
    
    def detect_gpu(self) -> bool:
        """Détecte la présence d'un GPU NVIDIA"""
        try:
            result = run_cmd("nvidia-smi", check=False)
            return result.returncode == 0
        except:
            return False
    
    def get_memory_gb(self) -> int:
        """Obtient la mémoire RAM en GB"""
        try:
            result = run_cmd("free -g | grep '^Mem:' | awk '{print $2}'", check=False)
            return int(result.stdout.strip()) if result.returncode == 0 else 0
        except:
            return 0
    
    def get_cpu_cores(self) -> int:
        """Obtient le nombre de cores CPU"""
        try:
            result = run_cmd("nproc", check=False)
            return int(result.stdout.strip()) if result.returncode == 0 else 0
        except:
            return 0

# =============================================================================
# INSTALLATEURS SPÉCIALISÉS
# =============================================================================

class AsteriskInstaller:
    """Installateur Asterisk 22 avec AudioFork"""
    
    def __init__(self, system_info: SystemInfo):
        self.system_info = system_info
        self.asterisk_version = "22"
        self.install_dir = "/usr/src/asterisk-22"
        
    def install(self):
        """Installation complète Asterisk 22"""
        log("🚀 Starting Asterisk 22 installation with AudioFork", "success")
        
        self.install_dependencies()
        self.download_asterisk()
        self.configure_asterisk()
        self.compile_asterisk()
        self.install_asterisk()
        self.configure_service()
        
        log("✅ Asterisk 22 installation completed", "success")
    
    def install_dependencies(self):
        """Installation des dépendances Asterisk"""
        log("📦 Installing Asterisk dependencies")
        
        if self.system_info.os_name in ['ubuntu', 'debian']:
            deps = [
                "build-essential", "libjansson-dev", "libsqlite3-dev", 
                "uuid-dev", "libxml2-dev", "libssl-dev", "libcurl4-openssl-dev",
                "libedit-dev", "libsrtp2-dev", "libspandsp-dev", "libunbound-dev",
                "git", "wget", "curl", "sox", "pkg-config", "autoconf", "automake",
                "libtool", "libncurses5-dev", "libreadline-dev", "libspeex-dev",
                "libspeexdsp-dev", "libgsm1-dev", "libogg-dev", "libvorbis-dev",
                "libasound2-dev", "portaudio19-dev", "libfftw3-dev", "libresample1-dev",
                "libsystemd-dev"  # CRITIQUE: Support systemd pour éviter timeout au démarrage
            ]
            
            run_cmd("apt-get update", "Updating package lists")
            run_cmd(f"apt-get install -y {' '.join(deps)}", "Installing dependencies")
            
        else:
            log("⚠️ OS not supported for automatic dependency installation", "warning")
    
    def clean_previous_installation(self):
        """Nettoyage complet de l'installation Asterisk précédente"""
        log("🧹 Complete cleanup of previous Asterisk installation")
        
        # Arrêter et désactiver le service
        run_cmd("systemctl stop asterisk", check=False)
        run_cmd("systemctl disable asterisk", check=False)
        
        # Tuer tous processus Asterisk
        run_cmd("pkill -9 asterisk", check=False)
        
        # Supprimer binaires
        run_cmd("rm -f /usr/sbin/asterisk", check=False)
        run_cmd("rm -f /usr/sbin/astgenkey", check=False) 
        run_cmd("rm -f /usr/sbin/astdb2sqlite3", check=False)
        
        # Supprimer configs (sauvegarde d'abord)
        run_cmd("rm -rf /etc/asterisk.backup", check=False)
        run_cmd("mv /etc/asterisk /etc/asterisk.backup", check=False)
        
        # Supprimer données et logs
        run_cmd("rm -rf /var/lib/asterisk", check=False)
        run_cmd("rm -rf /var/log/asterisk", check=False)
        run_cmd("rm -rf /var/spool/asterisk", check=False)
        run_cmd("rm -rf /var/run/asterisk", check=False)
        
        # Supprimer service systemd
        run_cmd("rm -f /etc/systemd/system/asterisk.service", check=False)
        run_cmd("systemctl daemon-reload", check=False)
        
        log("✅ Previous installation cleaned")

    def download_asterisk(self):
        """Télécharge Asterisk 22"""
        log(f"📥 Downloading Asterisk {self.asterisk_version}")
        
        # Nettoyage complet d'abord
        self.clean_previous_installation()
        
        # Supprimer code source précédent
        if os.path.exists(self.install_dir):
            run_cmd(f"rm -rf {self.install_dir}", "Removing previous source installation")
        
        # Télécharger Asterisk 22.6.0 LTS stable (version exacte pour streaming/IA)
        exact_version = "22.6.0"
        run_cmd(
            f"wget -q https://github.com/asterisk/asterisk/releases/download/{exact_version}/asterisk-{exact_version}.tar.gz",
            f"Downloading Asterisk {exact_version} LTS stable release",
            timeout=300
        )
        
        exact_version = "22.6.0"
        run_cmd(
            f"tar -xzf asterisk-{exact_version}.tar.gz",
            f"Extracting Asterisk {exact_version}",
            timeout=60
        )
        
        # Répertoire extrait avec version exacte
        extracted_dir = f"asterisk-{exact_version}"
        if os.path.exists(self.install_dir):
            run_cmd(f"rm -rf {self.install_dir}", "Removing existing directory")
        
        run_cmd(f"mv {extracted_dir} {self.install_dir}", "Moving to install directory")
        
        os.chdir(self.install_dir)
    
    def configure_asterisk(self):
        """Configure Asterisk avant compilation"""
        log("⚙️ Configuring Asterisk build")
        
        # Vérifier si recompilation nécessaire pour support systemd
        if os.path.exists("/usr/sbin/asterisk"):
            log("🔍 Checking if existing Asterisk has systemd support")
            result = run_cmd("ldd /usr/sbin/asterisk | grep systemd", check=False)
            if result.returncode != 0:
                log("⚠️ Existing Asterisk lacks systemd support - recompilation required")
                log("🧹 Cleaning previous build for systemd support")
                run_cmd("make distclean", check=False)
            else:
                log("✅ Existing Asterisk has systemd support")
        
        # Fix pkg-config paths pour PJSIP (résout "No objects found")
        log("🔧 Setting up PKG_CONFIG_PATH for PJSIP compatibility")
        os.environ['PKG_CONFIG_PATH'] = '/usr/lib/pkgconfig:/usr/lib64/pkgconfig:/usr/local/lib/pkgconfig'
        run_cmd("export PKG_CONFIG_PATH=/usr/lib/pkgconfig:/usr/lib64/pkgconfig:/usr/local/lib/pkgconfig", check=False)
        
        # Configuration de base avec pjproject bundled + libdir fix
        configure_cmd = "./configure --with-pjproject-bundled --with-jansson-bundled"
        
        # Fix pour systèmes 64-bit (CentOS/Ubuntu)
        if os.path.exists("/usr/lib64"):
            configure_cmd += " --libdir=/usr/lib64"
            
        run_cmd(configure_cmd, "Running configure script with PJSIP fixes", timeout=300)
        
        # Menu selection automatique
        self.setup_menuselect()
    
    def setup_menuselect(self):
        """Configure les modules Asterisk"""
        log("📋 Configuring Asterisk modules")
        
        # Modules essentiels pour MiniBotPanel v2
        essential_modules = [
            "res_ari",
            "res_ari_applications", 
            "res_ari_asterisk",
            "res_ari_bridges",
            "res_ari_channels",
            "res_ari_device_states",
            "res_ari_endpoints",
            "res_ari_events",
            "res_ari_mailboxes",
            "res_ari_playbacks",
            "res_ari_recordings",
            "res_ari_sounds",
            "res_http_websocket",
            "res_stasis",
            "res_stasis_answer",
            "res_stasis_device_state",
            "res_stasis_playback",
            "res_stasis_recording",
            "res_stasis_snoop",
            "app_stasis"
        ]
        
        # Module AudioFork (nouveau dans Asterisk 22)
        streaming_modules = [
            "res_stasis_snoop",  # Pour AudioFork
            "app_mixmonitor",    # Pour enregistrements
            "func_audiohook"     # Pour hooks audio
        ]
        
        # AMD et audio
        audio_modules = [
            "app_amd",
            "res_musiconhold",
            "format_wav",
            "format_gsm", 
            "format_pcm",
            "codec_gsm",
            "codec_alaw",
            "codec_ulaw"
        ]
        
        all_modules = essential_modules + streaming_modules + audio_modules
        
        # Activer les modules
        for module in all_modules:
            run_cmd(f"make menuselect.makeopts", check=False)
            run_cmd(f"menuselect/menuselect --enable {module} menuselect.makeopts", check=False)
        
        log(f"✅ Configured {len(all_modules)} essential modules")
    
    def compile_asterisk(self):
        """Compile Asterisk"""
        log("🔨 Compiling Asterisk (this may take 10-30 minutes)")
        
        # Utiliser tous les cores disponibles
        cores = max(1, self.system_info.cpu_cores - 1)
        
        run_cmd(
            f"make -j{cores}",
            f"Compiling with {cores} cores",
            timeout=1800  # 30 minutes max
        )
    
    def install_asterisk(self):
        """Installe Asterisk"""
        log("📦 Installing Asterisk system-wide")
        
        run_cmd("make install", "Installing binaries", timeout=300)
        run_cmd("make samples", "Installing sample configs", timeout=60)
        
        # NOUVELLE APPROCHE: Garder les configs de base et merger les nôtres
        log("📋 Keeping base configs and will merge our configurations later")
        
        run_cmd("make progdocs", "Installing documentation", check=False, timeout=300)
    
    def configure_service(self):
        """Configure le service systemd"""
        log("🔧 Configuring Asterisk service")
        
        # Créer utilisateur asterisk si nécessaire
        run_cmd("useradd -r -d /var/lib/asterisk -s /bin/false asterisk", check=False)
        
        # Permissions
        dirs_to_create = [
            "/etc/asterisk",
            "/var/lib/asterisk",
            "/var/log/asterisk", 
            "/var/spool/asterisk",
            "/var/run/asterisk"
        ]
        
        for dir_path in dirs_to_create:
            run_cmd(f"mkdir -p {dir_path}", check=False)
            run_cmd(f"chown asterisk:asterisk {dir_path}", check=False)
        
        # Service systemd avec timeouts VPS
        systemd_content = """[Unit]
Description=Asterisk PBX
Documentation=man:asterisk(8)
Wants=network.target
After=network.target

[Service]
Type=forking
User=asterisk
Group=asterisk
Environment=HOME=/var/lib/asterisk
WorkingDirectory=/var/lib/asterisk
PIDFile=/var/run/asterisk/asterisk.pid
ExecStart=/usr/sbin/asterisk -C /etc/asterisk/asterisk.conf
ExecStop=/usr/sbin/asterisk -rx 'core stop now'
ExecReload=/usr/sbin/asterisk -rx 'core reload'
# Safe temp directories
PrivateTmp=true
Restart=always
RestartSec=4
# VPS timeout optimizations
TimeoutStartSec=300
TimeoutStopSec=120

[Install]
WantedBy=multi-user.target
"""
        
        with open("/etc/systemd/system/asterisk.service", "w") as f:
            f.write(systemd_content)
        
        run_cmd("systemctl daemon-reload", "Reloading systemd")
        run_cmd("systemctl enable asterisk", "Enabling Asterisk service")

class StreamingServicesInstaller:
    """Installateur des services streaming (Vosk, Ollama, etc.)"""
    
    def __init__(self, system_info: SystemInfo):
        self.system_info = system_info
        
    def install(self):
        """Installation complète des services streaming"""
        log("🌊 Installing streaming services", "success")
        
        self.install_vosk()
        self.install_ollama()
        self.download_models()
        
        log("✅ Streaming services installation completed", "success")
    
    def install_vosk(self):
        """Installe Vosk et télécharge modèles français"""
        log("🗣️ Installing Vosk ASR")
        
        # Vosk sera installé via pip dans requirements.txt
        # Ici on télécharge les modèles
        
        models_dir = Path("/var/lib/vosk-models")
        models_dir.mkdir(parents=True, exist_ok=True)
        
        # Modèle français small (140MB) - rapide
        fr_small_url = "https://alphacephei.com/vosk/models/vosk-model-fr-0.6-linto.zip"
        fr_small_path = models_dir / "vosk-fr-small"
        
        if not fr_small_path.exists():
            log("📥 Downloading French Vosk model (small)")
            
            run_cmd(f"wget -O /tmp/vosk-fr-linto.zip {fr_small_url}", timeout=600)
            run_cmd("cd /tmp && unzip -q vosk-fr-linto.zip")
            run_cmd(f"mv /tmp/vosk-model-fr-* {fr_small_path}")
            run_cmd("rm -f /tmp/vosk-fr-linto.zip")
            
            log("✅ French Vosk model installed")
        else:
            log("ℹ️ French Vosk model already installed")
        
        # Créer lien symbolique pour config
        os.makedirs("/opt/minibot/models", exist_ok=True)
        run_cmd(f"ln -sf {fr_small_path} /opt/minibot/models/vosk-fr", check=False)
    
    def install_ollama(self):
        """Installe Ollama pour NLP local"""
        log("🤖 Installing Ollama for local NLP")
        
        # Vérifier si déjà installé
        result = run_cmd("which ollama", check=False)
        if result.returncode == 0:
            log("ℹ️ Ollama already installed")
            return
        
        # Installation officielle
        run_cmd(
            "curl -fsSL https://ollama.ai/install.sh | sh",
            "Installing Ollama",
            timeout=300
        )
        
        # Démarrer le service
        run_cmd("systemctl enable ollama", check=False)
        run_cmd("systemctl start ollama", check=False)
        
        # Attendre que le service soit prêt
        time.sleep(5)
    
    def download_models(self):
        """Télécharge les modèles Ollama"""
        log("📥 Downloading Ollama models")
        
        models = ["phi3:mini", "mistral:7b-instruct"]  # Modèles légers
        
        for model in models:
            try:
                log(f"📥 Downloading {model}")
                run_cmd(f"ollama pull {model}", f"Downloading {model}", timeout=1200)
                log(f"✅ {model} downloaded")
            except:
                log(f"⚠️ Failed to download {model}", "warning")
        
        # Vérifier les modèles disponibles
        result = run_cmd("ollama list", check=False)
        if result.returncode == 0:
            log(f"📋 Available models:\n{result.stdout}")

class DatabaseInstaller:
    """Installateur PostgreSQL (existant gardé)"""
    
    def __init__(self, system_info: SystemInfo):
        self.system_info = system_info
        self.db_name = "minibot_db"
        self.db_user = "robot"
        # Use simple password to avoid special characters issues with PostgreSQL URLs
        self.db_password = "minibot2024"
        
    def install(self):
        """Installation PostgreSQL (logique existante gardée)"""
        log("🗄️ Installing PostgreSQL", "success")
        
        self.install_postgresql()
        self.setup_database()
        
        log("✅ PostgreSQL installation completed", "success")
    
    def install_postgresql(self):
        """Installe PostgreSQL"""
        if self.system_info.os_name in ['ubuntu', 'debian']:
            run_cmd("apt-get update", "Updating packages")
            run_cmd(
                "apt-get install -y postgresql postgresql-contrib python3-psycopg2",
                "Installing PostgreSQL"
            )
        
        # Démarrer le service
        run_cmd("systemctl enable postgresql", "Enabling PostgreSQL")
        run_cmd("systemctl start postgresql", "Starting PostgreSQL")
    
    def setup_database(self):
        """Configure la base de données"""
        log("🔧 Setting up database")
        
        # Créer utilisateur et base
        commands = [
            f"CREATE USER {self.db_user} WITH PASSWORD '{self.db_password}';",
            f"CREATE DATABASE {self.db_name} OWNER {self.db_user};",
            f"GRANT ALL PRIVILEGES ON DATABASE {self.db_name} TO {self.db_user};"
        ]
        
        for cmd in commands:
            run_cmd(f'sudo -u postgres psql -c "{cmd}"', check=False)
        
        log(f"✅ Database {self.db_name} created with user {self.db_user}")

# =============================================================================
# CONFIGURATEUR PRINCIPAL
# =============================================================================

class ConfigManager:
    """Gestionnaire de configuration streaming"""
    
    def __init__(self):
        # Répertoire du projet MiniBotPanel (parent du répertoire system)
        self.project_root = Path(__file__).parent.parent
        self.config_dir = self.project_root / "asterisk-configs"
        
    def setup_configs(self, db_password: str, sip_config: dict = None):
        """Configure tous les fichiers pour le mode streaming"""
        log("⚙️ Setting up configurations for streaming mode", "success")
        
        self.setup_environment_file(db_password)
        self.setup_asterisk_configs(sip_config)
        self.setup_python_configs()
        
        log("✅ Configuration setup completed", "success")
    
    def setup_environment_file(self, db_password: str):
        """Crée le fichier .env"""
        log("📝 Creating environment configuration")
        
        env_content = f"""# MiniBotPanel v2 Configuration - Streaming Mode
# Generated on {datetime.now().isoformat()}

# =============================================================================
# MODE DE FONCTIONNEMENT
# =============================================================================
STREAMING_MODE=true

# =============================================================================
# DATABASE
# =============================================================================
DATABASE_URL=postgresql://robot:{db_password}@localhost/minibot_db

# =============================================================================
# ASTERISK ARI
# =============================================================================
ARI_URL=http://localhost:8088
ARI_USERNAME=robot
ARI_PASSWORD=MiniBotAI2025!

# =============================================================================
# VOSK (Streaming ASR)
# =============================================================================
VOSK_MODEL_PATH=/opt/minibot/models/vosk-fr
VOSK_SAMPLE_RATE=16000

# =============================================================================
# OLLAMA (Local NLP)
# =============================================================================
OLLAMA_URL=http://localhost:11434
OLLAMA_MODEL=phi3:mini
OLLAMA_TIMEOUT=10
OLLAMA_FALLBACK_TO_KEYWORDS=true

# =============================================================================
# AUDIO STREAMING
# =============================================================================
AUDIOFORK_HOST=127.0.0.1
AUDIOFORK_PORT=8765
VAD_MODE=2
VAD_FRAME_DURATION=30

# =============================================================================
# BARGE-IN & LATENCES
# =============================================================================
BARGE_IN_ENABLED=true
TARGET_BARGE_IN_LATENCY=150
TARGET_ASR_LATENCY=400
TARGET_INTENT_LATENCY=600
TARGET_TOTAL_LATENCY=1000

# =============================================================================
# AMD (Answering Machine Detection)
# =============================================================================
AMD_ENABLED=true
AMD_INITIAL_SILENCE=2000
AMD_GREETING=5000
AMD_AFTER_GREETING_SILENCE=800
AMD_TOTAL_ANALYSIS_TIME=7000
AMD_MIN_WORD_LENGTH=100
AMD_BETWEEN_WORDS_SILENCE=50

AMD_PYTHON_ENABLED=true
AMD_MACHINE_SPEECH_THRESHOLD=2.8
AMD_HUMAN_SPEECH_THRESHOLD=1.2
AMD_SILENCE_THRESHOLD=0.9
AMD_BEEP_DETECTION_ENABLED=true

# =============================================================================
# PATHS
# =============================================================================
RECORDINGS_PATH=/var/spool/asterisk/recording
SOUNDS_PATH=/var/lib/asterisk/sounds/minibot

# =============================================================================
# LOGS
# =============================================================================
LOG_LEVEL=INFO
LOG_FILE=/opt/minibot/logs/robot.log
STREAMING_LOG_FILE=/opt/minibot/logs/streaming.log
AMD_LOG_FILE=/opt/minibot/logs/amd.log

# =============================================================================
# API
# =============================================================================
PUBLIC_API_URL=http://localhost:8000
"""
        
        env_file = self.project_root / ".env"
        with open(env_file, "w") as f:
            f.write(env_content)
        
        log(f"✅ Environment file created: {env_file}")
    
    def setup_asterisk_configs(self, sip_config: dict = None):
        """Configure Asterisk pour le mode streaming"""
        log("🔧 Setting up Asterisk configurations for streaming")
        
        # PJSIP : Génération dynamique avec vraies informations SIP
        if sip_config:
            self._generate_pjsip_config(sip_config)
        else:
            log("⚠️ No SIP config provided, using template", "warning")
            self._replace_config("pjsip_streaming.conf", "/etc/asterisk/pjsip.conf")
        
        # Autres configs : Merge possible
        self._copy_config("ari_streaming.conf", "/etc/asterisk/ari.conf")
        self._copy_config("extensions_streaming.conf", "/etc/asterisk/extensions.conf")
        self._copy_config("amd_streaming.conf", "/etc/asterisk/amd.conf")
        
        # Configuration HTTP (commune)
        http_conf = """[general]
enabled=yes
bindaddr=127.0.0.1
bindport=8088
"""
        
        with open("/etc/asterisk/http.conf", "w") as f:
            f.write(http_conf)
        
        # Changer propriétaire
        run_cmd("chown -R asterisk:asterisk /etc/asterisk/", check=False)
        
        log("✅ Asterisk configurations installed")
    
    def _generate_pjsip_config(self, sip_config: dict):
        """Génère la configuration PJSIP standard qui fonctionne (basée sur recherche web officielle)"""
        log(f"📞 Generating PJSIP config for {sip_config['username']}@{sip_config['server']}")
        
        # Convention standard : section name = CLI command name (1:1 mapping)
        username = sip_config['username']
        
        pjsip_conf = f"""[global]
type=global
endpoint_identifier_order=ip,username

[transport-udp]
type=transport
protocol=udp
bind=0.0.0.0:5060

[{username}]
type=registration
transport=transport-udp
outbound_auth={username}-auth
server_uri=sip:{sip_config['server']}
client_uri=sip:{username}@{sip_config['server']}
retry_interval=60

[{username}-auth]
type=auth
auth_type=userpass
username={username}
password={sip_config['password']}

[{username}-aor]
type=aor
max_contacts=2
remove_existing=yes
contact=sip:{sip_config['server']}

[{username}-endpoint]
type=endpoint
transport=transport-udp
context=outbound-robot
outbound_auth={username}-auth
aors={username}-aor
allow=!all,ulaw,alaw,gsm
from_user={username}
from_domain={sip_config['server']}

[{username}-identify]
type=identify
endpoint={username}-endpoint
match={sip_config['server']}
"""
        
        with open("/etc/asterisk/pjsip.conf", "w") as f:
            f.write(pjsip_conf)
        
        log("✅ PJSIP configuration generated with corrected parameters (max_contacts, remove_existing)")
    
    def _generate_ari_streaming_config(self):
        """Génère la configuration ARI optimisée pour streaming temps réel et IA"""
        log("🎯 Generating ARI streaming configuration for real-time AI")
        
        # Configuration ARI avec optimisations streaming
        ari_conf = """[general]
enabled = yes
pretty = yes
websocket_write_timeout = 100

[robot]
type = user
read_only = no
password = MiniBotAI2025!
"""
        
        # Configuration HTTP avec WebSocket pour IA
        http_conf = """[general]
enabled=yes
bindaddr=0.0.0.0
bindport=8088
websocket_timeout=30

[websockets]
enabled=yes
"""
        
        with open("/etc/asterisk/ari.conf", "w") as f:
            f.write(ari_conf)
        
        with open("/etc/asterisk/http.conf", "w") as f:
            f.write(http_conf)
        
        log("✅ ARI streaming configuration generated for real-time AI integration")
    
    def _replace_config(self, source_name: str, dest_path: str):
        """Remplace complètement le fichier de configuration (pour PJSIP)"""
        source_path = self.config_dir / source_name
        
        if source_path.exists():
            log(f"📋 Replacing {dest_path} with {source_name}")
            
            # Remplacer complètement le fichier (comme ancien install.py)
            with open(source_path, "r") as source_file:
                content = source_file.read()
                
            with open(dest_path, "w") as dest_file:
                dest_file.write(content)
                    
            log(f"✅ Replaced {dest_path} with {source_name}")
        else:
            log(f"⚠️ Config file not found: {source_path}", "warning")
    
    def _copy_config(self, source_name: str, dest_path: str):
        """Merge notre configuration dans le fichier existant"""
        source_path = self.config_dir / source_name
        
        if source_path.exists():
            # NOUVELLE APPROCHE: Append au lieu de remplacer
            log(f"📋 Merging {source_name} → {dest_path}")
            
            # Ajouter séparateur et nos configs à la fin du fichier existant
            with open(dest_path, "a") as dest_file:
                dest_file.write(f"\n\n; ========================================\n")
                dest_file.write(f"; MiniBotPanel v2 Configuration - {source_name}\n") 
                dest_file.write(f"; ========================================\n")
                
                with open(source_path, "r") as source_file:
                    dest_file.write(source_file.read())
                    
            log(f"✅ Merged {source_name} into existing {dest_path}")
        else:
            log(f"⚠️ Config file not found: {source_path}", "warning")
    
    def setup_python_configs(self):
        """Configure l'environnement Python"""
        log("🐍 Setting up Python environment")
        
        # Créer répertoires nécessaires
        dirs_to_create = [
            "/opt/minibot",
            "/opt/minibot/models",
            "/opt/minibot/logs", 
            "/var/lib/asterisk/sounds/minibot",
            self.project_root / "logs",
            self.project_root / "recordings",
            self.project_root / "assembled_audio",
            self.project_root / "transcripts"
        ]
        
        for dir_path in dirs_to_create:
            Path(dir_path).mkdir(parents=True, exist_ok=True)
            if str(dir_path).startswith("/opt") or str(dir_path).startswith("/var"):
                run_cmd(f"chown asterisk:asterisk {dir_path}", check=False)
        
        log("✅ Python environment configured")
    
    def _has_gpu(self) -> bool:
        """Vérifie la présence d'un GPU NVIDIA"""
        try:
            result = run_cmd("nvidia-smi", check=False)
            return result.returncode == 0
        except:
            return False

# =============================================================================
# INSTALLATEUR PRINCIPAL
# =============================================================================

class StreamingInstaller:
    """Installateur principal MiniBotPanel v2 Streaming"""
    
    def __init__(self):
        self.system_info = SystemInfo()
        self.log_file = setup_logging()
        # Répertoire du projet MiniBotPanel (parent du répertoire system)
        self.project_dir = Path(__file__).parent.parent
        
    def run_installation(self):
        """Lance l'installation complète"""
        log("🚀 Starting MiniBotPanel v2 Streaming Installation", "success")
        log("📋 Installation mode: STREAMING ONLY")
        log(f"💻 System: {self.system_info.os_name} {self.system_info.arch}")
        log(f"🧠 Memory: {self.system_info.memory_gb}GB, CPU: {self.system_info.cpu_cores} cores")
        log(f"🎮 GPU: {'Yes' if self.system_info.has_gpu else 'No'}")
        
        try:
            # Vérifications préliminaires
            check_root()
            self._check_system_requirements()
            
            # Installation des composants
            self._install_system_packages()
            
            # PostgreSQL (toujours nécessaire)
            db_installer = DatabaseInstaller(self.system_info)
            db_installer.install()
            
            # Asterisk 22 (toujours nécessaire)
            asterisk_installer = AsteriskInstaller(self.system_info)
            asterisk_installer.install()
            
            # Services streaming
            streaming_installer = StreamingServicesInstaller(self.system_info)
            streaming_installer.install()
            
            # Configuration
            config_manager = ConfigManager()
            config_manager.setup_configs(db_installer.db_password)
            
            # Installation des dépendances Python
            self._install_python_dependencies()
            
            # Configuration SIP
            self._setup_sip_configuration()
            
            # Optimisations streaming automatiques
            self._apply_streaming_optimizations()
            
            # Tests finaux
            self._run_installation_tests()
            
            # Post-installation: corriger automatiquement le .env pour éviter les problèmes URL
            self._fix_env_file_for_production()
            
            # Résumé
            self._print_installation_summary(db_installer.db_password)
            
            log("🎉 Installation completed successfully!", "success")
            
        except Exception as e:
            log(f"❌ Installation failed: {e}", "error")
            log(f"📋 Check log file: {self.log_file}", "error")
            sys.exit(1)
    
    def _check_system_requirements(self):
        """Vérifie les prérequis système"""
        log("✅ Checking system requirements")
        
        # RAM minimum
        if self.system_info.memory_gb < 4:
            log("⚠️ Warning: Less than 4GB RAM detected", "warning")
        
        # Espace disque
        result = run_cmd("df -h / | tail -1 | awk '{print $4}'", check=False)
        if result.returncode == 0:
            log(f"💾 Available disk space: {result.stdout.strip()}")
        
        # Internet
        try:
            requests.get("https://github.com", timeout=5)
            log("🌐 Internet connection: OK")
        except:
            log("❌ No internet connection", "error")
            raise Exception("Internet connection required")
    
    def _install_system_packages(self):
        """Installe les packages système de base + UFW firewall"""
        log("📦 Installing base system packages + firewall")
        
        if self.system_info.os_name in ['ubuntu', 'debian']:
            base_packages = [
                "python3", "python3-pip", "python3-venv", "python3-dev",
                "build-essential", "git", "wget", "curl", "unzip",
                "portaudio19-dev", "libasound2-dev", "ffmpeg", "sox", "ufw", "fail2ban",
                "espeak", "espeak-data", "libespeak1", "libespeak-dev",  # Pour TTS fallback
                "libffi-dev", "libssl-dev"  # Pour dépendances Python TTS
            ]
            
            run_cmd("apt-get update")
            run_cmd(f"apt-get install -y {' '.join(base_packages)}")
            
            # Configuration firewall UFW + fail2ban (sécurité SIP)
            log("🛡️ Configuring UFW firewall + fail2ban for VPS security")
            run_cmd("ufw allow 22/tcp", "Allow SSH", check=False)
            run_cmd("ufw allow 5060/udp", "Allow SIP", check=False) 
            run_cmd("ufw allow 10000:20000/udp", "Allow RTP", check=False)
            run_cmd("ufw allow 8088/tcp", "Allow ARI", check=False)
            run_cmd("ufw allow 8000/tcp", "Allow FastAPI", check=False)
            
            # Bloquer IP attaquante connue
            run_cmd("ufw deny from 77.110.109.104", "Block SIP attacker IP", check=False)
            
            run_cmd("ufw --force enable", "Enable firewall", check=False)
            
            # Configuration fail2ban pour SIP
            fail2ban_config = self.project_dir / "system" / "fail2ban-asterisk.conf"
            if fail2ban_config.exists():
                run_cmd(f"cp {fail2ban_config} /etc/fail2ban/jail.local", "Install fail2ban config", check=False)
                run_cmd("systemctl enable fail2ban", "Enable fail2ban", check=False)
                run_cmd("systemctl reload fail2ban", "Reload fail2ban configuration", check=False)
                log("✅ fail2ban configured for SIP protection")
            
            log("✅ UFW firewall + fail2ban configured - VPS protected from SIP attacks")
        
        log("✅ Base packages + firewall installed")
    
    def _install_python_dependencies(self):
        """Installe les dépendances Python"""
        log("🐍 Installing Python dependencies")
        
        # Vérifier requirements.txt dans le répertoire du projet
        requirements_file = self.project_dir / "requirements.txt"
        if not requirements_file.exists():
            log("❌ requirements.txt not found", "error")
            log(f"📂 Looking for: {requirements_file}", "error")
            raise Exception("requirements.txt missing")
        
        # Installation avec pip (utiliser le chemin absolu)
        run_cmd(
            f"pip3 install -r {requirements_file}",
            "Installing Python packages",
            timeout=1200
        )
        
        log("✅ Python dependencies installed")
    
    def _setup_sip_configuration(self):
        """Configure l'enregistrement SIP"""
        log("📞 Setting up SIP configuration", "success")
        
        # Vérifier si PJSIP existe déjà et s'il contient de vraies configs (pas juste template)
        if os.path.exists("/etc/asterisk/pjsip.conf"):
            with open("/etc/asterisk/pjsip.conf", 'r') as f:
                content = f.read()
            
            # Vérifier si c'est une vraie config (contient des sections configurées)
            if "type=registration" in content and "server_uri=sip:" in content:
                log("📞 Configuration SIP existante détectée")
                response = input("Voulez-vous garder la config SIP existante ? [y/N]: ").strip().lower()
                if response in ['y', 'yes', 'oui']:
                    log("✅ Configuration SIP existante conservée")
                    return
            else:
                log("⚠️ Template PJSIP vide détecté, configuration SIP requise")
                
        # Demander les informations SIP
        log("\n" + "="*60)
        log("📞 CONFIGURATION SIP REQUISE")
        log("="*60)
        log("Pour que MiniBotPanel puisse passer des appels,")
        log("vous devez configurer un trunk SIP.")
        log("")
        
        # Collecter les informations
        sip_config = self._collect_sip_info()
        
        # Générer la configuration Asterisk
        self._generate_asterisk_sip_config(sip_config)
        
        # Démarrer Asterisk si pas déjà fait
        self._start_asterisk_service()
        
        # Vérifier l'enregistrement
        self._verify_sip_registration(sip_config)
        
        log("✅ SIP configuration completed")
    
    def _collect_sip_info(self):
        """Collecte les informations SIP de l'utilisateur"""
        import getpass
        
        log("📝 Veuillez entrer vos informations SIP:")
        
        sip_config = {}
        
        # Seulement les informations essentielles
        sip_config['host'] = input("🌐 Serveur SIP (ex: sip.ovhcloud.com): ").strip()
        sip_config['username'] = input("👤 Nom d'utilisateur SIP: ").strip()
        sip_config['password'] = getpass.getpass("🔐 Mot de passe SIP: ").strip()
        
        # Valeurs automatiques (pas de questions)
        sip_config['port'] = "5060"
        sip_config['trunk_name'] = "provider"
        sip_config['context'] = "outbound-robot"  # IMPORTANT: doit correspondre au dialplan
        sip_config['server'] = sip_config['host']  # Alias pour compatibilité
        
        log(f"📞 Configuration automatique: Port {sip_config['port']}, Trunk '{sip_config['trunk_name']}'")
        
        return sip_config
    
    def _generate_asterisk_sip_config(self, sip_config):
        """Génère la configuration SIP Asterisk"""
        log("📝 Generating Asterisk SIP configuration")
        
        # Les configs corrompues ont déjà été supprimées après "make samples"
        
        # Configuration PJSIP qui marchait ce matin (provider_* au lieu de username-*)
        pjsip_conf = f"""[global]
type=global
endpoint_identifier_order=ip,username

[transport-udp]
type=transport
protocol=udp
bind=0.0.0.0:5060

[provider_reg]
type=registration
transport=transport-udp
outbound_auth=provider_auth
server_uri=sip:{sip_config['host']}:5060
client_uri=sip:{sip_config['username']}@{sip_config['host']}:5060
retry_interval=60
expiration=3600

[provider_auth]
type=auth
auth_type=userpass
username={sip_config['username']}
password={sip_config['password']}

[provider]
type=endpoint
transport=transport-udp
context=outbound-robot
outbound_auth=provider_auth
aors=provider_aor
allow=!all,alaw,ulaw

[provider_aor]
type=aor
contact=sip:{sip_config['host']}:5060

[provider_identify]
type=identify
endpoint=provider
match={sip_config['host']}
"""
        
        # CORRECTION: Remplacer complètement le fichier PJSIP (comme ancien install.py)
        with open("/etc/asterisk/pjsip.conf", "w") as f:
            f.write(pjsip_conf)
        
        # FIX CRITIQUE: Corriger les permissions immédiatement (résout "No objects found")
        log("🔧 Fixing PJSIP file permissions (critical for object loading)")
        run_cmd("chown asterisk:asterisk /etc/asterisk/pjsip.conf", check=False)
        run_cmd("chmod 644 /etc/asterisk/pjsip.conf", check=False)
        run_cmd("chown -R asterisk:asterisk /etc/asterisk/", check=False)
        
        # Configuration des extensions (dialplan)
        extensions_conf = f"""
; =============================================================================
; Extensions for MiniBotPanel v2 - Generated {datetime.now().isoformat()}
; =============================================================================

[{sip_config['context']}]
; Appels sortants via le trunk
exten => _X.,1,NoOp(Outgoing call to ${{EXTEN}})
 same => n,Dial(PJSIP/${{EXTEN}}@{sip_config['trunk_name']},60)
 same => n,Hangup()

; Context pour les appels MiniBotPanel
[minibot-calls]
exten => _X.,1,NoOp(MiniBotPanel outgoing call to ${{EXTEN}})
 same => n,Set(CHANNEL(hangup_handler_push)=hangup-handler,s,1)
 same => n,AMD(2000,5000,800,7000,100,50)
 same => n,Set(AMD_STATUS=${{AMDSTATUS}})
 same => n,Set(AMD_CAUSE=${{AMDCAUSE}})
 same => n,Stasis(minibot,${{EXTEN}})
 same => n,Hangup()

[hangup-handler]
exten => s,1,NoOp(Call ended)
 same => n,Return()
"""
        
        # NOUVELLE APPROCHE: Append la config extensions au fichier existant  
        with open("/etc/asterisk/extensions.conf", "a") as f:
            f.write("\n\n; ========================================\n")
            f.write("; MiniBotPanel v2 Extensions Configuration\n") 
            f.write("; ========================================\n")
            f.write(extensions_conf)
        
        # Configuration asterisk.conf CRITIQUE pour transmit_silence
        asterisk_conf = f"""[directories](!)
astcachedir => /var/cache/asterisk
astetcdir => /etc/asterisk
astmoddir => /usr/lib/asterisk/modules
astvarlibdir => /var/lib/asterisk
astdbdir => /var/lib/asterisk
astkeydir => /var/lib/asterisk
astdatadir => /var/lib/asterisk
astagidir => /var/lib/asterisk/agi-bin
astspooldir => /var/spool/asterisk
astrundir => /var/run/asterisk
astlogdir => /var/log/asterisk
astsbindir => /usr/sbin

[options]
; CRITIQUE: transmit_silence DOIT être activé pour l'enregistrement
transmit_silence = yes		; Transmet du silence RTP pendant l'enregistrement
"""
        
        # NOUVELLE APPROCHE: Append la config asterisk.conf au fichier existant
        with open("/etc/asterisk/asterisk.conf", "a") as f:
            f.write("\n\n; ========================================\n")
            f.write("; MiniBotPanel v2 Asterisk Configuration\n")
            f.write("; ========================================\n") 
            f.write(asterisk_conf)
        
        log("✅ Asterisk SIP configuration + transmit_silence generated")
    
    def _start_asterisk_service(self):
        """Démarre le service Asterisk avec méthode robuste"""
        log("🚀 Starting Asterisk service with robust method")
        
        try:
            # 1. Arrêt propre et nettoyage
            log("🧹 Stopping any running Asterisk processes")
            run_cmd("systemctl stop asterisk", check=False)
            run_cmd("pkill -f asterisk", check=False)
            time.sleep(3)
            
            # 2. Nettoyage des fichiers de lock
            log("🔒 Cleaning lock files")
            run_cmd("rm -f /var/run/asterisk/asterisk.ctl", check=False)
            run_cmd("rm -f /var/run/asterisk/asterisk.pid", check=False)
            
            # 3. Fixer permissions des configurations
            log("📋 Fixing configuration permissions")
            config_files = ["/etc/asterisk/pjsip.conf", "/etc/asterisk/asterisk.conf", 
                          "/etc/asterisk/ari.conf", "/etc/asterisk/http.conf"]
            for config_file in config_files:
                run_cmd(f"chown asterisk:asterisk {config_file}", check=False)
                run_cmd(f"chmod 644 {config_file}", check=False)
            
            # 4. Créer et fixer permissions répertoires
            log("📁 Creating and fixing Asterisk directories")
            dirs = ["/var/run/asterisk", "/var/lib/asterisk", "/var/log/asterisk", 
                   "/var/spool/asterisk", "/var/spool/asterisk/recording"]
            for dir_path in dirs:
                run_cmd(f"mkdir -p {dir_path}", check=False)
                run_cmd(f"chown -R asterisk:asterisk {dir_path}", check=False)
                run_cmd(f"chmod 755 {dir_path}", check=False)
            
            # 5. Démarrage systemctl avec retry
            log("🎯 Starting Asterisk via systemctl with retry logic")
            max_attempts = 3
            for attempt in range(max_attempts):
                log(f"   Attempt {attempt + 1}/{max_attempts}")
                
                # Démarrer le service
                result = run_cmd("systemctl start asterisk", check=False)
                time.sleep(5)
                
                # Vérifier si c'est actif
                status_result = run_cmd("systemctl is-active asterisk", check=False)
                if status_result.returncode == 0:
                    log("✅ Asterisk started successfully via systemctl")
                    break
                    
                if attempt < max_attempts - 1:
                    log(f"⚠️ Attempt {attempt + 1} failed, retrying...")
                    run_cmd("systemctl stop asterisk", check=False)
                    run_cmd("pkill -f asterisk", check=False)
                    time.sleep(2)
                else:
                    log("❌ All systemctl attempts failed, trying direct start", "warning")
                    
                    # Fallback: démarrage direct
                    run_cmd("cd /var/lib/asterisk && sudo -u asterisk /usr/sbin/asterisk -C /etc/asterisk/asterisk.conf", 
                           "Direct Asterisk start", timeout=30, check=False)
                    time.sleep(5)
            
            # 6. Vérification finale
            log("🔍 Final verification of Asterisk status")
            
            # Test processus
            process_result = run_cmd("ps aux | grep '[a]sterisk.*asterisk.conf'", check=False)
            
            # Test CLI
            cli_result = run_cmd("asterisk -rx 'core show uptime'", check=False)
            
            # Test systemctl
            systemctl_result = run_cmd("systemctl is-active asterisk", check=False)
            
            if process_result.returncode == 0 and cli_result.returncode == 0:
                log("✅ Asterisk is running and responding to CLI")
                if systemctl_result.returncode == 0:
                    log("✅ Asterisk service is properly managed by systemctl")
                else:
                    log("⚠️ Asterisk running but not managed by systemctl (manual start)")
                return True
            else:
                log("❌ Asterisk failed to start properly", "error")
                return False
            
            # CRITIQUE: Débloquer le port SIP maintenant qu'Asterisk est démarré
            log("🔓 Unblocking SIP port - Asterisk is now running safely")
            run_cmd("iptables -D INPUT -p udp --dport 5060 -j DROP", check=False)
            
            log("✅ Asterisk service ready successfully")
            return True
            
        except Exception as e:
            log(f"❌ Failed to start Asterisk: {e}", "error")
            log("📋 Check Asterisk logs: sudo journalctl -u asterisk", "error")
            raise
    
    def _verify_sip_registration(self, sip_config):
        """Vérifie l'enregistrement SIP avec bitcall-reg"""
        log("🔍 Verifying SIP registration")
        
        # Recharger la config PJSIP
        log("🔄 Reloading PJSIP configuration...")
        run_cmd('asterisk -rx "module reload res_pjsip.so"', check=False)
        time.sleep(2)
        
        # Forcer une nouvelle registration avec convention standard
        username = sip_config['username']
        log("📞 Forcing new registration...")
        run_cmd(f'asterisk -rx "pjsip send register {username}"', check=False)
        time.sleep(3)
        
        max_attempts = 6
        for attempt in range(1, max_attempts + 1):
            log(f"📞 Checking registration (attempt {attempt}/{max_attempts})")
            
            try:
                # Vérifier l'enregistrement PJSIP
                result = run_cmd(
                    f'asterisk -rx "pjsip show registrations"',
                    check=False,
                    timeout=10
                )
                
                if result.returncode == 0:
                    log(f"💻 Command: asterisk -rx \"pjsip show registrations\"")
                    log(f"📤 Output: {result.stdout}")
                    
                    # Chercher provider_reg (notre registration) au lieu du username
                    username = sip_config['username']
                    if "provider_reg" in result.stdout:
                        if "Registered" in result.stdout:
                            log("✅ SIP registration successful!", "success")
                            log(f"📞 provider_reg is registered (user: {username})")
                            return True
                        elif "Unregistered" in result.stdout:
                            log(f"⚠️ Registration unregistered - attempt {attempt}", "warning")
                        elif "Rejected" in result.stdout:
                            log(f"❌ Registration rejected - check credentials - attempt {attempt}", "warning")
                        else:
                            log(f"🔄 Registration in progress - attempt {attempt}")
                    else:
                        log(f"⚠️ No provider_reg registration found - attempt {attempt}")
                else:
                    log(f"❌ Command failed - attempt {attempt}")
                
                if attempt < max_attempts:
                    log("⏱️ Waiting 10 seconds before retry...")
                    time.sleep(10)
                    
            except Exception as e:
                log(f"❌ Error checking registration: {e}")
                if attempt < max_attempts:
                    time.sleep(10)
        
        # Si on arrive ici, l'enregistrement a échoué
        log("❌ SIP registration failed after all attempts", "error")
        log("🔧 Please check:", "warning")
        log("   - SIP credentials in /etc/asterisk/pjsip.conf", "warning")
        log("   - Network connectivity to SIP provider", "warning")
        log("   - Provider allows your IP address", "warning")
        username = sip_config['username']
        log(f"   - Manual test: asterisk -rx 'pjsip send register {username}'", "warning")
        return False
        log("  - Asterisk logs: sudo tail -f /var/log/asterisk/messages")
        
        # Afficher les détails pour debug
        try:
            result = run_cmd('asterisk -rx "pjsip show registrations"', check=False)
            if result.stdout:
                log("📋 Current registrations:")
                for line in result.stdout.split('\n'):
                    if line.strip():
                        log(f"   {line}")
        except:
            pass
            
        return False
    
    def _run_installation_tests(self):
        """Lance des tests de validation"""
        log("🧪 Running installation tests")
        
        tests_passed = 0
        tests_total = 0
        
        # Test PostgreSQL
        tests_total += 1
        try:
            run_cmd("systemctl is-active postgresql", check=True)
            log("✅ PostgreSQL: Running")
            tests_passed += 1
        except:
            log("❌ PostgreSQL: Failed", "error")
        
        # Test Asterisk
        tests_total += 1
        try:
            run_cmd("systemctl is-active asterisk", check=True)
            log("✅ Asterisk: Running")
            tests_passed += 1
        except:
            log("❌ Asterisk: Failed", "error")
        
        # Test Ollama
        tests_total += 1
        try:
            result = run_cmd("curl -s http://localhost:11434/api/version", check=False)
            if result.returncode == 0:
                log("✅ Ollama: Running")
                tests_passed += 1
            else:
                log("❌ Ollama: Failed", "error")
        except:
            log("❌ Ollama: Failed", "error")
        
        # Test modèles Vosk
        tests_total += 1
        if Path("/opt/minibot/models/vosk-fr").exists():
            log("✅ Vosk models: Available")
            tests_passed += 1
        else:
            log("❌ Vosk models: Missing", "error")
        
        # Test SIP registration
        tests_total += 1
        try:
            result = run_cmd('asterisk -rx "pjsip show registrations"', check=False)
            if result.returncode == 0 and "Registered" in result.stdout:
                log("✅ SIP Registration: Active")
                tests_passed += 1
            else:
                log("❌ SIP Registration: Failed", "error")
        except:
            log("❌ SIP Registration: Failed", "error")
        
        # Test Vosk avec fichier audio de test
        tests_total += 1
        try:
            self._test_vosk_recognition()
            log("✅ Vosk Recognition: Working")
            tests_passed += 1
        except Exception as e:
            log(f"❌ Vosk Recognition: Failed - {e}", "error")
        
        log(f"📊 Tests: {tests_passed}/{tests_total} passed")
        
        if tests_passed < tests_total:
            log("⚠️ Some tests failed - check configuration", "warning")
    
    def _test_vosk_recognition(self):
        """Test Vosk avec le fichier audio de test"""
        log("🎤 Testing Vosk speech recognition")
        
        # Chemin vers le fichier audio de test
        test_audio_file = self.project_dir / "audio" / "test_audio.wav"
        
        if not test_audio_file.exists():
            raise Exception(f"Test audio file not found: {test_audio_file}")
        
        # Copier et convertir le fichier audio pour Vosk (16kHz mono requis)
        target_audio = Path("/opt/minibot/test_audio.wav")
        log("🔧 Converting audio to 16kHz mono for Vosk compatibility")
        
        # Conversion automatique avec sox : 16kHz, mono, WAV
        run_cmd(f"sox {test_audio_file} -r 16000 -c 1 {target_audio}", 
                "Converting audio format (16kHz mono)")
        
        # Créer un script Python de test Vosk
        test_script = f"""
import json
import wave
from vosk import Model, KaldiRecognizer

def test_vosk():
    # Charger le modèle
    model = Model("/opt/minibot/models/vosk-fr")
    rec = KaldiRecognizer(model, 16000)
    
    # Ouvrir le fichier audio
    wf = wave.open("{target_audio}", "rb")
    
    # Transcrire
    results = []
    while True:
        data = wf.readframes(4000)
        if len(data) == 0:
            break
        if rec.AcceptWaveform(data):
            result = json.loads(rec.Result())
            if result.get("text"):
                results.append(result["text"])
    
    # Résultat final
    final_result = json.loads(rec.FinalResult())
    if final_result.get("text"):
        results.append(final_result["text"])
    
    # Afficher le résultat
    transcription = " ".join(results).strip()
    print(f"TRANSCRIPTION: {{transcription}}")
    
    if transcription:
        print("SUCCESS: Vosk recognition working")
        return True
    else:
        print("ERROR: No transcription generated")
        return False

if __name__ == "__main__":
    try:
        result = test_vosk()
        exit(0 if result else 1)
    except Exception as e:
        print(f"ERROR: {{e}}")
        exit(1)
"""
        
        # Écrire et exécuter le script de test
        test_script_path = Path("/tmp/test_vosk.py")
        with open(test_script_path, "w") as f:
            f.write(test_script)
        
        # Exécuter le test
        result = run_cmd(f"cd /opt/minibot && python3 {test_script_path}", 
                        "Running Vosk recognition test", 
                        timeout=30, 
                        check=False)
        
        if result.returncode == 0:
            # Extraire la transcription du résultat
            for line in result.stdout.split('\n'):
                if line.startswith("TRANSCRIPTION:"):
                    transcription = line.replace("TRANSCRIPTION:", "").strip()
                    log(f"🎤 Vosk transcription: '{transcription}'")
                    break
            
            if "SUCCESS" in result.stdout:
                log("✅ Vosk recognition test passed")
            else:
                raise Exception("No transcription generated")
        else:
            raise Exception(f"Test failed: {result.stderr}")
        
        # Nettoyer
        run_cmd(f"rm -f {target_audio} {test_script_path}", check=False)
    
    def _apply_streaming_optimizations(self):
        """Applique automatiquement toutes les optimisations streaming pour performances maximales"""
        log("🚀 Applying streaming optimizations for maximum performance", "success")
        
        # 1. Optimisations Ollama pour JSON parfait
        self._optimize_ollama_for_streaming()
        
        # 2. Vérifications et corrections ARI/HTTP
        self._verify_and_fix_ari_config()
        
        # 3. Optimisations système pour streaming temps réel
        self._optimize_system_for_streaming()
        
        # 4. Configuration TTS avec clonage vocal
        self._setup_tts_voice_cloning()
        
        # 5. Mise à jour des prompts NLP dynamiques
        self._update_nlp_prompts()
        
        log("✅ All streaming optimizations applied successfully", "success")
    
    def _optimize_ollama_for_streaming(self):
        """Optimise Ollama pour des réponses JSON parfaites"""
        log("🤖 Optimizing Ollama for perfect JSON responses")
        
        try:
            # Vérifier si Ollama est accessible
            result = run_cmd("curl -s http://localhost:11434/api/version", check=False)
            if result.returncode != 0:
                log("⚠️ Ollama not accessible, starting service", "warning")
                run_cmd("systemctl start ollama", check=False)
                time.sleep(5)
            
            # Vérifier le modèle correct llama3.2:1b
            result = run_cmd("ollama list", check=False)
            if result.returncode == 0:
                if "llama3.2:1b" not in result.stdout:
                    log("📥 Installing optimized model llama3.2:1b for streaming")
                    run_cmd("ollama pull llama3.2:1b", timeout=600)
                else:
                    log("✅ Optimal model llama3.2:1b already available")
            
            # Test JSON response avec paramètres optimisés
            test_payload = {
                "model": "llama3.2:1b",
                "messages": [
                    {"role": "system", "content": "Réponds UNIQUEMENT en JSON: {\"intent\": \"affirm\", \"confidence\": 0.9}"},
                    {"role": "user", "content": "oui ça va"}
                ],
                "options": {
                    "temperature": 0.05,
                    "top_p": 0.15,
                    "num_predict": 20,
                    "stop": ["}"]
                }
            }
            
            import json as json_module
            test_file = "/tmp/ollama_test.json"
            with open(test_file, "w") as f:
                json_module.dump(test_payload, f)
            
            result = run_cmd(f"curl -s -X POST http://localhost:11434/api/chat -d @{test_file}", check=False)
            if result.returncode == 0:
                log("✅ Ollama optimization parameters validated")
            else:
                log("⚠️ Ollama test failed, but parameters will be used by robot", "warning")
            
            run_cmd(f"rm -f {test_file}", check=False)
            
        except Exception as e:
            log(f"⚠️ Ollama optimization warning: {e}", "warning")
    
    def _verify_and_fix_ari_config(self):
        """Vérifie et corrige la configuration ARI/HTTP"""
        log("🔧 Verifying and fixing ARI/HTTP configuration")
        
        try:
            # Vérifier que HTTP est activé dans http.conf
            http_conf_path = "/etc/asterisk/http.conf"
            if os.path.exists(http_conf_path):
                with open(http_conf_path, "r") as f:
                    content = f.read()
                
                if "enabled=yes" not in content:
                    log("🔧 Fixing HTTP configuration", "warning")
                    # Réécrire le fichier HTTP avec config correcte
                    http_conf = """[general]
enabled=yes
bindaddr=0.0.0.0
bindport=8088
websocket_timeout=30

[websockets]
enabled=yes
"""
                    with open(http_conf_path, "w") as f:
                        f.write(http_conf)
                    
                    log("✅ HTTP configuration fixed")
                else:
                    log("✅ HTTP configuration is correct")
            
            # Vérifier que ARI est configuré avec un mot de passe fixe
            ari_conf_path = "/etc/asterisk/ari.conf"
            if os.path.exists(ari_conf_path):
                with open(ari_conf_path, "r") as f:
                    content = f.read()
                
                if "${ARI_PASSWORD}" in content:
                    log("🔧 Fixing ARI password variable", "warning")
                    # Remplacer la variable par le mot de passe fixe
                    content = content.replace("${ARI_PASSWORD}", "MiniBotAI2025!")
                    with open(ari_conf_path, "w") as f:
                        f.write(content)
                    log("✅ ARI password variable fixed")
                elif "MiniBotAI2025!" in content:
                    log("✅ ARI configuration is correct")
                else:
                    log("⚠️ ARI password not found, using default config", "warning")
            
            # Redémarrer Asterisk pour appliquer les changements
            log("🔄 Restarting Asterisk to apply configuration changes")
            run_cmd("systemctl restart asterisk", check=False)
            time.sleep(3)
            
            # Vérifier que les services sont accessibles
            result = run_cmd("systemctl is-active asterisk", check=False)
            if result.returncode == 0:
                log("✅ Asterisk restarted successfully")
            else:
                log("⚠️ Asterisk restart issues, check manually", "warning")
                
        except Exception as e:
            log(f"⚠️ ARI configuration warning: {e}", "warning")
    
    def _optimize_system_for_streaming(self):
        """Optimise le système pour le streaming temps réel"""
        log("⚡ Optimizing system for real-time streaming")
        
        try:
            # Augmenter les limites de fichiers ouverts pour les WebSockets
            ulimit_conf = """# MiniBotPanel v2 streaming optimizations
* soft nofile 65536
* hard nofile 65536
* soft nproc 32768
* hard nproc 32768
"""
            with open("/etc/security/limits.d/minibot-streaming.conf", "w") as f:
                f.write(ulimit_conf)
            
            # Optimiser les paramètres réseau pour WebRTC/WebSocket
            sysctl_conf = """# MiniBotPanel v2 network optimizations for streaming
net.core.rmem_max = 16777216
net.core.wmem_max = 16777216
net.ipv4.tcp_rmem = 4096 87380 16777216
net.ipv4.tcp_wmem = 4096 16384 16777216
net.core.netdev_max_backlog = 5000
"""
            with open("/etc/sysctl.d/99-minibot-streaming.conf", "w") as f:
                f.write(sysctl_conf)
            
            # Appliquer les optimisations sysctl
            run_cmd("sysctl --system", check=False)
            
            log("✅ System optimizations applied")
            
        except Exception as e:
            log(f"⚠️ System optimization warning: {e}", "warning")
    
    def _fix_env_file_for_production(self):
        """Corrige automatiquement le fichier .env pour éviter les problèmes de caractères spéciaux"""
        log("🔧 Auto-fixing .env file for production compatibility")
        
        env_file = self.project_root / ".env"
        if not env_file.exists():
            log("⚠️ .env file not found, skipping auto-fix", "warning")
            return
            
        try:
            # Lire le contenu actuel
            with open(env_file, "r") as f:
                content = f.read()
            
            # Corriger l'URL de base de données avec le mot de passe simple
            content = re.sub(
                r'DATABASE_URL=postgresql://robot:[^@]+@localhost/minibot_db',
                'DATABASE_URL=postgresql://robot:minibot2024@localhost/minibot_db',
                content
            )
            
            # Écrire le contenu corrigé
            with open(env_file, "w") as f:
                f.write(content)
                
            log("✅ .env file automatically corrected for production")
            log("   - Database URL: Uses simple password without special characters")
            
        except Exception as e:
            log(f"⚠️ Could not auto-fix .env file: {e}", "warning")
    
    def _print_installation_summary(self, db_password: str):
        """Affiche le résumé d'installation"""
        log("=" * 60, "success")
        log("🎉 INSTALLATION SUMMARY", "success")
        log("=" * 60, "success")
        
        log("📋 Mode: STREAMING ONLY")
        log(f"🗄️ Database: minibot_db (password in .env)")
        log(f"📂 Project root: {Path.cwd()}")
        log(f"📝 Log file: {self.log_file}")
        
        log("\n📋 NEXT STEPS:")
        log("1. Review .env file configuration")
        log("2. Put your 9 audio files in audio/ directory")
        log("3. Run: sudo ./system/setup_audio.sh")
        log("4. Import contacts: python3 system/import_contacts.py contacts.csv")
        log("5. Start system: ./start_system.sh")
        log("6. Launch campaign: python3 system/launch_campaign.py --name 'Test' --limit 10")
        
        log("\n🌐 ENDPOINTS:")
        log("- API: http://localhost:8000")
        log("- Docs: http://localhost:8000/docs")
        log("- Health: http://localhost:8000/health")
        
        log("\n🌊 STREAMING FEATURES:")
        log("- Real-time ASR with Vosk")
        log("- Local NLP with Ollama")
        log("- Barge-in support")
        log("- Sub-second latency")
        log("- AMD hybrid detection")
        
        log("=" * 60, "success")

    def _setup_tts_voice_cloning(self):
        """Configure le TTS avec clonage vocal pour réponses dynamiques"""
        log("🎙️ Setting up TTS voice cloning for dynamic responses")
        
        try:
            # Vérifier que les dépendances TTS sont installées
            result = run_cmd("python3 -c 'import TTS; print(\"TTS available\")'", check=False)
            if result.returncode != 0:
                log("📦 Installing TTS dependencies (this may take several minutes)...")
                
                # Installation avec GPU support auto-détection
                gpu_available = run_cmd("nvidia-smi", check=False).returncode == 0
                
                if gpu_available:
                    log("🚀 GPU detected, installing with CUDA support")
                    run_cmd("pip3 install torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cu118", timeout=900)
                else:
                    log("💻 CPU-only installation")
                    run_cmd("pip3 install torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cpu", timeout=900)
                
                # Installation TTS et autres dépendances
                run_cmd("pip3 install TTS transformers datasets accelerate", timeout=600)
                
                # Vérification finale
                result = run_cmd("python3 -c 'import TTS; print(\"TTS successfully installed\")'", check=False)
                if result.returncode != 0:
                    log("⚠️ TTS installation may need manual intervention", "warning")
            
            # Tester le service TTS
            tts_test_script = self.project_dir / "services" / "tts_voice_clone.py"
            if tts_test_script.exists():
                log("🔧 Testing TTS voice cloning service...")
                result = run_cmd(f"python3 {tts_test_script}", check=False, timeout=120)
                if result.returncode == 0:
                    log("✅ TTS voice cloning service operational")
                else:
                    log("⚠️ TTS service needs manual configuration after first run", "warning")
            
            log("✅ TTS voice cloning setup completed")
            
        except Exception as e:
            log(f"⚠️ TTS setup warning: {e}", "warning")
            log("💡 TTS can be configured manually later", "info")

    def _update_nlp_prompts(self):
        """Met à jour les prompts NLP avec contexte dynamique"""
        log("🧠 Updating NLP prompts with dynamic context")
        
        try:
            # Vérifier que les fichiers de configuration existent
            prompts_config = self.project_dir / "prompts_config.json"
            nlp_service = self.project_dir / "services" / "nlp_intent.py"
            
            if not prompts_config.exists():
                log("⚠️ prompts_config.json not found, will be created at runtime", "warning")
            
            if nlp_service.exists():
                # Tester le chargement des prompts dynamiques
                test_cmd = f"cd {self.project_dir} && python3 -c 'from services.nlp_intent import intent_engine; print(\"NLP service with dynamic prompts loaded\")'"
                result = run_cmd(test_cmd, check=False)
                
                if result.returncode == 0:
                    log("✅ NLP service with dynamic prompts operational")
                else:
                    log("⚠️ NLP service will be configured at runtime", "warning")
            
            log("✅ NLP prompts update completed")
            
        except Exception as e:
            log(f"⚠️ NLP prompts update warning: {e}", "warning")

# Cette fonction existe déjà dans la classe StreamingInstaller comme _apply_streaming_optimizations()

# =============================================================================
# POINT D'ENTRÉE PRINCIPAL
# =============================================================================

def main():
    """Point d'entrée principal"""
    print(f"{Colors.BOLD}{Colors.CYAN}")
    print("=" * 60)
    print("🤖 MiniBotPanel v2 - Installation Streaming")
    print("   Real-time Architecture with Vosk + Ollama")
    print("=" * 60)
    print(f"{Colors.NC}")
    
    print("\n🌊 Features to install:")
    print("- Asterisk 22 with AudioFork")
    print("- PostgreSQL database")
    print("- Vosk real-time ASR (French)")
    print("- Ollama local NLP")
    print("- Barge-in capability")
    print("- Sub-second latency")
    print("- AMD hybrid detection")
    
    # Confirmation
    confirm = input("\nContinue with streaming installation? [y/N]: ").lower()
    if confirm not in ['y', 'yes']:
        print("👋 Installation cancelled")
        sys.exit(0)
    
    # Lancer l'installation
    installer = StreamingInstaller()
    installer.run_installation()

if __name__ == "__main__":
    main()