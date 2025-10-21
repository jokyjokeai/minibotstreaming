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
                "libasound2-dev", "portaudio19-dev", "libfftw3-dev", "libresample1-dev"
            ]
            
            run_cmd("apt-get update", "Updating package lists")
            run_cmd(f"apt-get install -y {' '.join(deps)}", "Installing dependencies")
            
        else:
            log("⚠️ OS not supported for automatic dependency installation", "warning")
    
    def download_asterisk(self):
        """Télécharge Asterisk 22"""
        log(f"📥 Downloading Asterisk {self.asterisk_version}")
        
        # Supprimer installation précédente
        if os.path.exists(self.install_dir):
            run_cmd(f"rm -rf {self.install_dir}", "Removing previous installation")
        
        # Cloner depuis git (plus fiable que tarball)
        run_cmd(
            f"git clone -b {self.asterisk_version} https://github.com/asterisk/asterisk {self.install_dir}",
            f"Cloning Asterisk {self.asterisk_version}",
            timeout=600
        )
        
        os.chdir(self.install_dir)
    
    def configure_asterisk(self):
        """Configure Asterisk avant compilation"""
        log("⚙️ Configuring Asterisk build")
        
        # Configuration de base avec pjproject bundled
        run_cmd(
            "./configure --with-pjproject-bundled --with-jansson-bundled",
            "Running configure script",
            timeout=300
        )
        
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
        
        # CRITIQUE: Supprimer immédiatement les configs corrompues installées par "make samples"
        log("🗑️ Removing corrupted default configs installed by 'make samples'")
        run_cmd("rm -f /etc/asterisk/extensions.conf", check=False)
        run_cmd("rm -f /etc/asterisk/extensions.ael", check=False) 
        run_cmd("rm -f /etc/asterisk/users.conf", check=False)
        run_cmd("rm -f /etc/asterisk/pjsip.conf", check=False)
        
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
ExecStart=/usr/sbin/asterisk -f -C /etc/asterisk/asterisk.conf
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
        self.db_password = generate_password(16)
        
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
        
    def setup_configs(self, db_password: str):
        """Configure tous les fichiers pour le mode streaming"""
        log("⚙️ Setting up configurations for streaming mode", "success")
        
        self.setup_environment_file(db_password)
        self.setup_asterisk_configs()
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
ARI_PASSWORD={generate_password(16)}

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
    
    def setup_asterisk_configs(self):
        """Configure Asterisk pour le mode streaming"""
        log("🔧 Setting up Asterisk configurations for streaming")
        
        # Configurations streaming
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
    
    def _copy_config(self, source_name: str, dest_path: str):
        """Copie un fichier de configuration"""
        source_path = self.config_dir / source_name
        
        if source_path.exists():
            run_cmd(f"cp {source_path} {dest_path}")
            log(f"📋 Copied {source_name} → {dest_path}")
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
            
            # Tests finaux
            self._run_installation_tests()
            
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
                "portaudio19-dev", "libasound2-dev", "ffmpeg", "sox", "ufw"
            ]
            
            run_cmd("apt-get update")
            run_cmd(f"apt-get install -y {' '.join(base_packages)}")
            
            # Configuration firewall UFW (comme ancien script)
            log("🛡️ Configuring UFW firewall for VPS security")
            run_cmd("ufw allow 22/tcp", "Allow SSH", check=False)
            run_cmd("ufw allow 5060/udp", "Allow SIP", check=False) 
            run_cmd("ufw allow 10000:20000/udp", "Allow RTP", check=False)
            run_cmd("ufw allow 8088/tcp", "Allow ARI", check=False)
            run_cmd("ufw allow 8000/tcp", "Allow FastAPI", check=False)
            run_cmd("ufw --force enable", "Enable firewall", check=False)
            log("✅ UFW firewall configured - VPS protected from SIP attacks")
        
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
        
        # Vérifier si PJSIP existe déjà
        if os.path.exists("/etc/asterisk/pjsip.conf"):
            log("📞 Configuration SIP existante détectée")
            response = input("Voulez-vous garder la config SIP existante ? [y/N]: ").strip().lower()
            if response in ['y', 'yes', 'oui']:
                log("✅ Configuration SIP existante conservée")
                return
                
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
        sip_config['context'] = "from-internal"
        
        log(f"📞 Configuration automatique: Port {sip_config['port']}, Trunk '{sip_config['trunk_name']}'")
        
        return sip_config
    
    def _generate_asterisk_sip_config(self, sip_config):
        """Génère la configuration SIP Asterisk"""
        log("📝 Generating Asterisk SIP configuration")
        
        # Les configs corrompues ont déjà été supprimées après "make samples"
        
        # Configuration PJSIP (Asterisk 22)
        pjsip_conf = f"""
; =============================================================================
; PJSIP Configuration for MiniBotPanel v2 - Generated {datetime.now().isoformat()}
; =============================================================================

[transport-udp]
type=transport
protocol=udp
bind=0.0.0.0:{sip_config['port']}

; Trunk SIP Provider
[{sip_config['trunk_name']}]
type=endpoint
context={sip_config['context']}
outbound_auth={sip_config['trunk_name']}_auth
aors={sip_config['trunk_name']}_aor
allow=!all,alaw,ulaw,g722

[{sip_config['trunk_name']}_auth]
type=auth
auth_type=userpass
username={sip_config['username']}
password={sip_config['password']}

[{sip_config['trunk_name']}_aor]
type=aor
contact=sip:{sip_config['host']}:{sip_config['port']}

[{sip_config['trunk_name']}_identify]
type=identify
endpoint={sip_config['trunk_name']}
match={sip_config['host']}

; Registration
[{sip_config['trunk_name']}_reg]
type=registration
outbound_auth={sip_config['trunk_name']}_auth
server_uri=sip:{sip_config['host']}:{sip_config['port']}
client_uri=sip:{sip_config['username']}@{sip_config['host']}
retry_interval=60
"""
        
        # Écrire la configuration
        with open("/etc/asterisk/pjsip.conf", "w") as f:
            f.write(pjsip_conf)
        
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
        
        with open("/etc/asterisk/extensions.conf", "w") as f:
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
        
        with open("/etc/asterisk/asterisk.conf", "w") as f:
            f.write(asterisk_conf)
        
        log("✅ Asterisk SIP configuration + transmit_silence generated")
    
    def _start_asterisk_service(self):
        """Démarre le service Asterisk"""
        log("🚀 Starting Asterisk service")
        
        try:
            # CRITIQUE: Nettoyer les processus zombies/bloqués avant restart
            log("🧹 Cleaning any existing Asterisk processes")
            run_cmd("pkill -9 asterisk", check=False)
            time.sleep(2)
            run_cmd("systemctl stop asterisk", check=False)
            time.sleep(3)
            
            # Recharger la configuration
            run_cmd("systemctl start asterisk", "Starting Asterisk", timeout=120)
            time.sleep(5)  # Attendre le démarrage
            
            # Vérifier que c'est démarré
            run_cmd("systemctl is-active asterisk", check=True)
            log("✅ Asterisk service started successfully")
            
        except Exception as e:
            log(f"❌ Failed to start Asterisk: {e}", "error")
            log("📋 Check Asterisk logs: sudo journalctl -u asterisk", "error")
            raise
    
    def _verify_sip_registration(self, sip_config):
        """Vérifie l'enregistrement SIP"""
        log("🔍 Verifying SIP registration")
        
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
                
                if result.returncode == 0 and sip_config['trunk_name'] in result.stdout:
                    # Chercher le statut
                    if "Registered" in result.stdout:
                        log("✅ SIP registration successful!", "success")
                        log(f"📞 Trunk '{sip_config['trunk_name']}' is registered")
                        return True
                    elif "Unregistered" in result.stdout:
                        log(f"⚠️ Registration failed - attempt {attempt}", "warning")
                    else:
                        log(f"🔄 Registration in progress - attempt {attempt}")
                else:
                    log(f"⚠️ No registration info found - attempt {attempt}")
                
                if attempt < max_attempts:
                    log("⏱️ Waiting 10 seconds before retry...")
                    time.sleep(10)
                    
            except Exception as e:
                log(f"❌ Error checking registration: {e}")
                if attempt < max_attempts:
                    time.sleep(10)
        
        # Si on arrive ici, l'enregistrement a échoué
        log("❌ SIP registration failed after all attempts", "error")
        log("🔧 Please check:")
        log("  - SIP credentials are correct")
        log("  - Firewall allows SIP traffic (UDP 5060)")
        log("  - Network connectivity to SIP provider")
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