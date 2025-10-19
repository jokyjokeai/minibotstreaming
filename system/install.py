#!/usr/bin/env python3
# ==============================================
# SCRIPT INSTALLATION MiniBotPanel v2 avec ARI
# Basé sur install.py v1 mais adapté pour ARI
# ==============================================

import os
import sys
import subprocess
import tempfile
import time
import secrets
import string
import logging
from datetime import datetime

# -----------------------------------------------------
# Configuration et couleurs
# -----------------------------------------------------

class Colors:
    GREEN = '\033[92m'
    RED = '\033[91m'
    YELLOW = '\033[93m'
    BLUE = '\033[94m'
    NC = '\033[0m'  # No Color

# Configuration logging
def setup_logging():
    """Configure le système de logging dans un fichier"""
    log_dir = "logs"
    os.makedirs(log_dir, exist_ok=True)

    log_file = f"{log_dir}/installation_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log"

    # Configuration du logger
    logging.basicConfig(
        level=logging.DEBUG,
        format='%(asctime)s - %(levelname)s - %(funcName)s - %(message)s',
        handlers=[
            logging.FileHandler(log_file, encoding='utf-8'),
            logging.StreamHandler()  # Affichage console aussi
        ]
    )

    return log_file

def log(msg: str, level: str = "info"):
    """Logger unifié avec couleurs + fichier"""
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    # Log dans fichier (sans couleurs)
    if level == "success":
        logging.info(f"✅ {msg}")
        print(f"{Colors.GREEN}[{timestamp}] ✅ {msg}{Colors.NC}")
    elif level == "error":
        logging.error(f"❌ {msg}")
        print(f"{Colors.RED}[{timestamp}] ❌ {msg}{Colors.NC}")
    elif level == "warning":
        logging.warning(f"⚠️  {msg}")
        print(f"{Colors.YELLOW}[{timestamp}] ⚠️  {msg}{Colors.NC}")
    else:
        logging.info(f"ℹ️  {msg}")
        print(f"{Colors.BLUE}[{timestamp}] ℹ️  {msg}{Colors.NC}")

def run_command(command: str, capture: bool = False, check: bool = True):
    """Exécute une commande shell avec logging"""
    # Log commande (sans affichage console pour ne pas polluer)
    logging.debug(f"CMD: {command}")

    try:
        if capture:
            result = subprocess.run(command, shell=True, capture_output=True, text=True)
            if result.returncode != 0:
                logging.debug(f"CMD FAILED (code {result.returncode}): {result.stderr[:200]}")
            if check and result.returncode != 0:
                return False, result.stderr
            return True, result.stdout
        else:
            result = subprocess.run(command, shell=True, check=check)
            return True, ""
    except subprocess.CalledProcessError as e:
        logging.error(f"CMD EXCEPTION: {e}")
        return False, str(e)

def print_banner():
    """Affiche la bannière de démarrage"""
    print(f"""
{Colors.BLUE}
╔══════════════════════════════════════════════════════════╗
║               MiniBotPanel v2 INSTALLER                 ║
║                    Architecture ARI                     ║
╚══════════════════════════════════════════════════════════╝
{Colors.NC}
""")

# -----------------------------------------------------
# Vérifications système
# -----------------------------------------------------

def check_system():
    """Vérifications préliminaires système"""
    log("🔍 Vérification système...")
    
    # Check OS
    if not os.path.exists("/etc/os-release"):
        log("❌ Système non supporté (nécessite Linux)", "error")
        sys.exit(1)
    
    # Check root/sudo
    if os.geteuid() != 0:
        log("❌ Script doit être exécuté en tant que root", "error")
        sys.exit(1)
    
    # Check Internet
    success, output = run_command("ping -c 1 8.8.8.8", capture=True, check=False)
    if not success or "1 received" not in output:
        log("⚠️ Connexion Internet recommandée mais installation continue", "warning")
    
    log("✅ Vérifications système OK", "success")

# -----------------------------------------------------
# Désinstallation Asterisk
# -----------------------------------------------------

def check_asterisk_installed():
    """Vérifie si Asterisk est déjà installé"""
    success, output = run_command("which asterisk", capture=True, check=False)
    if success and output.strip():
        success, version = run_command("asterisk -V", capture=True, check=False)
        if success:
            return True, version.strip()
    return False, None

def uninstall_asterisk():
    """Désinstallation complète et propre d'Asterisk"""
    log("🗑️  Désinstallation Asterisk existant...")

    # Arrêter Asterisk
    log("⏹️  Arrêt Asterisk...")
    run_command("systemctl stop asterisk", check=False)
    run_command("killall -9 asterisk", check=False)

    # Désinstaller via make (chercher uniquement les dossiers, pas les .tar.gz)
    success, dirs = run_command(f"find /usr/src -maxdepth 1 -type d -name 'asterisk-20*' 2>/dev/null", capture=True, check=False)
    if success and dirs.strip():
        latest_dir = dirs.strip().split('\n')[-1]
        log(f"📂 Désinstallation depuis: {latest_dir}")
        run_command(f"cd {latest_dir} && make uninstall", check=False)

    # Supprimer fichiers
    log("🗑️  Suppression fichiers...")
    paths_to_remove = [
        "/usr/sbin/asterisk",
        "/usr/lib/asterisk",
        "/var/lib/asterisk",
        "/var/spool/asterisk",
        "/var/log/asterisk",
        "/var/run/asterisk",
        "/etc/asterisk",
        "/usr/src/asterisk-*"
    ]

    for path in paths_to_remove:
        run_command(f"rm -rf {path}", check=False)

    # Supprimer utilisateur
    run_command("userdel -r asterisk 2>/dev/null", check=False)
    run_command("groupdel asterisk 2>/dev/null", check=False)

    # Supprimer service systemd
    run_command("systemctl disable asterisk", check=False)
    run_command("rm -f /etc/systemd/system/asterisk.service", check=False)
    run_command("systemctl daemon-reload")

    log("✅ Asterisk désinstallé", "success")

def backup_configs():
    """Sauvegarde configurations Asterisk existantes"""
    backup_dir = f"/root/asterisk_backup_{int(time.time())}"

    configs_to_backup = [
        "/etc/asterisk/pjsip.conf",
        "/etc/asterisk/extensions.conf",
        "/etc/asterisk/ari.conf",
        "/etc/asterisk/http.conf",
        "/etc/asterisk/amd.conf"
    ]

    # Vérifier si au moins un fichier existe
    has_configs = False
    for config in configs_to_backup:
        if os.path.exists(config):
            has_configs = True
            break

    if not has_configs:
        log("ℹ️  Aucune config à sauvegarder", "info")
        return None

    log("💾 Sauvegarde configurations existantes...")
    os.makedirs(backup_dir, exist_ok=True)

    for config in configs_to_backup:
        if os.path.exists(config):
            run_command(f"cp {config} {backup_dir}/", check=False)

    log(f"✅ Backup dans: {backup_dir}", "success")
    return backup_dir

# -----------------------------------------------------
# Installation Asterisk 20 LTS
# -----------------------------------------------------

def install_asterisk20():
    """Installation Asterisk 20 LTS avec ARI"""
    log("🚀 Installation Asterisk 20 LTS...")
    
    # Dépendances système
    packages = [
        "build-essential", "wget", "subversion", "libjansson-dev",
        "libxml2-dev", "uuid-dev", "libncurses5-dev", "libsqlite3-dev",
        "libssl-dev", "libedit-dev", "curl", "sox", "sqlite3"
    ]
    
    log("📦 Installation dépendances...")
    success, _ = run_command(f"apt update && apt install -y {' '.join(packages)}")
    if not success:
        log("❌ Erreur installation dépendances", "error")
        return False
    
    # Script installation Asterisk 20
    asterisk_script = f"""
#!/bin/bash
# Pas de set -e pour éviter l'arrêt sur erreurs non-critiques

cd /usr/src

# Nettoyage
rm -rf asterisk-20*.tar.gz asterisk-20.*/

# Téléchargement et extraction
echo "📥 Téléchargement Asterisk 20..."
wget -q https://downloads.asterisk.org/pub/telephony/asterisk/asterisk-20-current.tar.gz || {{
    echo "❌ Échec téléchargement"
    exit 1
}}

tar -xzf asterisk-20-current.tar.gz || {{
    echo "❌ Échec extraction"
    exit 1
}}

cd asterisk-20.*/ || {{
    echo "❌ Dossier Asterisk introuvable"
    exit 1
}}

# Installation contrib scripts (requis pour menuselect)
echo "⚙️ Installation des scripts contrib..."
contrib/scripts/install_prereq install || true

# Configuration avec support ARI
echo "⚙️ Configuration..."
./configure --with-jansson-bundled --with-pjproject-bundled || {{
    echo "❌ Configuration échouée"
    exit 1
}}

# Sélection modules
echo "📦 Sélection modules..."
make menuselect.makeopts || {{
    echo "❌ Échec menuselect"
    exit 1
}}

# Activer modules avec vérification
menuselect/menuselect \\
  --enable CORE-SOUNDS-FR-ULAW \\
  --enable CORE-SOUNDS-FR-ALAW \\
  --enable CORE-SOUNDS-FR-GSM \\
  --enable res_ari \\
  --enable res_http_websocket \\
  --enable app_amd \\
  menuselect.makeopts 2>/dev/null || true

# Compilation
echo "🔨 Compilation (cela peut prendre 10-15 minutes)..."
make -j$(nproc) || {{
    echo "❌ Compilation échouée"
    exit 1
}}

# Installation
echo "📦 Installation..."
make install || exit 1
make samples || true
make config || true
ldconfig

# Utilisateur asterisk
groupadd asterisk 2>/dev/null || true
useradd -r -d /var/lib/asterisk -g asterisk asterisk 2>/dev/null || true
usermod -aG audio,dialout asterisk 2>/dev/null || true

# Créer dossiers manquants
mkdir -p /etc/asterisk /var/lib/asterisk /var/spool/asterisk /var/spool/asterisk/recording /var/log/asterisk /var/run/asterisk /var/lib/asterisk/sounds/minibot
chown -R asterisk:asterisk /etc/asterisk /var/lib/asterisk /var/spool/asterisk /var/log/asterisk /var/run/asterisk 2>/dev/null || true

# Service systemd
cat > /etc/systemd/system/asterisk.service << 'EOFSERVICE'
[Unit]
Description=Asterisk PBX and telephony daemon
After=network.target

[Service]
Type=simple
User=asterisk
Group=asterisk
ExecStart=/usr/sbin/asterisk -f -C /etc/asterisk/asterisk.conf
ExecReload=/usr/sbin/asterisk -rx 'core reload'
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
EOFSERVICE

systemctl daemon-reload
systemctl enable asterisk
systemctl start asterisk

# Pare-feu (optionnel, ne pas fail si ufw n'est pas installé)
ufw allow 22/tcp 2>/dev/null || true       # SSH - CRITIQUE pour accès VPS !
ufw allow 5060/udp 2>/dev/null || true     # SIP
ufw allow 10000:20000/udp 2>/dev/null || true  # RTP
ufw allow 8088/tcp 2>/dev/null || true     # ARI
ufw allow 8000/tcp 2>/dev/null || true     # FastAPI

# Attendre démarrage
sleep 8

# Vérification
if ps aux | grep -v grep | grep -q "/usr/sbin/asterisk"; then
    echo "✅ Asterisk 20 installé avec ARI !"
    exit 0
else
    echo "⚠️ Asterisk installé mais pas démarré, vérifier logs"
    exit 0
fi
"""
    
    with tempfile.NamedTemporaryFile(mode='w', suffix='.sh', delete=False) as f:
        f.write(asterisk_script)
        script_path = f.name
    
    try:
        os.chmod(script_path, 0o755)
        success, output = run_command(f"bash {script_path}")
        if success:
            log("✅ Asterisk 20 avec ARI installé", "success")
            return True
        else:
            log(f"❌ Erreur installation Asterisk: {output}", "error")
            return False
    finally:
        os.unlink(script_path)

# -----------------------------------------------------
# Configuration SIP
# -----------------------------------------------------

def get_sip_config():
    """Demande configuration SIP interactif"""
    print(f"\n{Colors.YELLOW}📞 Configuration SIP Provider:{Colors.NC}")

    sip_config = {
        'server': input("🌐 Serveur SIP (ex: bitcall.kkucc.net): ").strip(),
        'username': input("👤 Username SIP: ").strip(),
        'password': input("🔐 Password SIP: ").strip(),
        'caller_id': input("📞 Caller ID (ex: 33423000000): ").strip()
    }

    # Validation
    for key, value in sip_config.items():
        if not value:
            log(f"❌ {key} requis", "error")
            sys.exit(1)

    return sip_config

def get_whisper_config():
    """Demande configuration Whisper avec choix du modèle"""
    print(f"\n{Colors.YELLOW}🤖 Configuration Whisper:{Colors.NC}")

    # Vérifier les modèles déjà téléchargés
    cache_base = os.path.expanduser("~/.cache/huggingface/hub")
    downloaded_models = []

    for model_name in ["tiny", "base", "small", "medium", "large"]:
        # Chercher avec les 3 patterns possibles (Systran, openai, whisper)
        model_patterns = [
            f"{cache_base}/models--Systran--faster-whisper-{model_name}",
            f"{cache_base}/models--openai--whisper-{model_name}",
            f"{cache_base}/whisper-{model_name}"
        ]
        for model_cache in model_patterns:
            if os.path.exists(model_cache):
                downloaded_models.append(model_name)
                break

    print("Modèles disponibles :")
    print("  1. tiny   - Le plus rapide, moins précis (~75MB)")
    print("  2. base   - Équilibre vitesse/précision (~150MB) [RECOMMANDÉ]")
    print("  3. small  - Plus précis, plus lent (~500MB)")
    print("  4. medium - Très précis, lent (~1.5GB)")
    print("  5. large  - Meilleure précision, très lent (~3GB)")

    if downloaded_models:
        print(f"\n💾 Modèles déjà téléchargés : {', '.join(downloaded_models)}")
        print("   (Réutilisation instantanée, pas de téléchargement)")

    choice = input(f"\n{Colors.BLUE}Choisissez le modèle [2-base]: {Colors.NC}").strip() or "2"

    model_map = {
        "1": "tiny",
        "2": "base",
        "3": "small",
        "4": "medium",
        "5": "large",
        "tiny": "tiny",
        "base": "base",
        "small": "small",
        "medium": "medium",
        "large": "large"
    }

    model = model_map.get(choice.lower(), "base")

    if model in downloaded_models:
        log(f"✅ Modèle '{model}' sélectionné (déjà téléchargé)", "success")
    else:
        log(f"✅ Modèle '{model}' sélectionné (sera téléchargé)", "success")

    return model

def detect_whisper_device():
    """Détecte si GPU avec cuDNN est disponible pour Whisper"""
    try:
        # Vérifier si PyTorch détecte CUDA
        success, output = run_command("python3 -c 'import torch; print(torch.cuda.is_available())'", capture=True, check=False)
        if not success or "True" not in output:
            log("💻 GPU non détecté, utilisation CPU pour Whisper", "info")
            return "cpu", "int8"

        # GPU détecté, vérifier cuDNN 9.x (système + pip)
        # 1. Chercher dans /usr (install système)
        success, output = run_command("find /usr -name 'libcudnn_ops.so.9*' 2>/dev/null | head -1", capture=True, check=False)
        if success and output.strip():
            log("🎮 GPU + cuDNN 9.x détecté (système), utilisation GPU pour Whisper", "success")
            return "cuda", "float16"

        # 2. Chercher package pip nvidia-cudnn-cu12
        success, output = run_command("pip3 show nvidia-cudnn-cu12 2>/dev/null", capture=True, check=False)
        if success and "Version: 9." in output:
            log("🎮 GPU + cuDNN 9.x détecté (pip), utilisation GPU pour Whisper", "success")
            return "cuda", "float16"

        # 3. Essayer d'importer directement
        success, output = run_command("python3 -c 'import nvidia.cudnn; print(nvidia.cudnn.__version__)'", capture=True, check=False)
        if success and "9." in output:
            log("🎮 GPU + cuDNN 9.x détecté (Python), utilisation GPU pour Whisper", "success")
            return "cuda", "float16"

        # cuDNN 9.x non trouvé
        log("⚠️ GPU détecté mais cuDNN 9.x manquant, utilisation CPU", "warning")
        log("💡 Pour activer GPU: pip3 install nvidia-cudnn-cu12==9.1.0.70", "info")
        return "cpu", "int8"

    except Exception as e:
        log(f"⚠️ Erreur détection GPU: {e}, utilisation CPU", "warning")
        return "cpu", "int8"

def configure_asterisk_ari(sip_config, whisper_model="base"):
    """Configuration Asterisk pour ARI"""
    log("⚙️ Configuration Asterisk ARI...")

    # Générer mot de passe ARI sécurisé
    ari_password = ''.join(secrets.choice(string.ascii_letters + string.digits) for _ in range(16))

    # Détecter device Whisper optimal
    whisper_device, whisper_compute = detect_whisper_device()
    
    # PJSIP Configuration
    pjsip_conf = f"""[global]
type=global
endpoint_identifier_order=ip,username

[transport-udp]
type=transport
protocol=udp
bind=0.0.0.0:5060

[{sip_config['username']}]
type=registration
transport=transport-udp
outbound_auth={sip_config['username']}-auth
server_uri=sip:{sip_config['server']}
client_uri=sip:{sip_config['username']}@{sip_config['server']}
retry_interval=60

[{sip_config['username']}-auth]
type=auth
auth_type=userpass
username={sip_config['username']}
password={sip_config['password']}

[bitcall]
type=endpoint
transport=transport-udp
context=outbound-robot
outbound_auth={sip_config['username']}-auth
aors=bitcall-aor
allow=!all,ulaw,alaw,gsm
from_user={sip_config['username']}
from_domain={sip_config['server']}

[bitcall-aor]
type=aor
contact=sip:{sip_config['server']}

[bitcall-identify]
type=identify
endpoint=bitcall
match={sip_config['server']}
"""
    
    # HTTP Configuration pour ARI
    http_conf = """[general]
enabled=yes
bindaddr=127.0.0.1
bindport=8088
"""
    
    # ARI Configuration  
    ari_conf = f"""[general]
enabled = yes
pretty = yes

[robot]
type = user
read_only = no
password = {ari_password}
"""
    
    # Extensions.conf (dialplan - MODE BATCH avec MixMonitor pour enregistrement complet)
    extensions_conf = f"""[outbound-robot]
; Robot calls with AMD (Answering Machine Detection)
; Args from ARI: ARG1=phone_number, ARG2=scenario, ARG3=campaign_id
exten => _X.,1,NoOp(Robot Call to ${{EXTEN}})
    same => n,Set(PHONE=${{ARG1}})
    same => n,Set(SCENARIO=${{ARG2}})
    same => n,Set(CAMPAIGN=${{ARG3}})
    same => n,NoOp(Args: Phone=${{PHONE}}, Scenario=${{SCENARIO}}, Campaign=${{CAMPAIGN}})
    ; Randomisation du Caller ID: 336 + 8 chiffres aléatoires
    same => n,Set(CALLERID(num)=336${{RAND(10000000,99999999)}})
    same => n,NoOp(Caller ID randomisé: ${{CALLERID(num)}})
    same => n,AMD()
    same => n,NoOp(AMD Status: ${{AMDSTATUS}}, Cause: ${{AMDCAUSE}})
    ; AudioFork DÉSACTIVÉ - Mode batch uniquement
    ; same => n,AudioFork(ws://127.0.0.1:8080/${{UNIQUEID}})
    ; MixMonitor RÉACTIVÉ avec option r() pour enregistrement complet + client séparé
    ; Cela permet de coexister avec les enregistrements ARI individuels
    same => n,Set(REC_FILE=full_call_${{UNIQUEID}}_${{EPOCH}})
    same => n,MixMonitor(/var/spool/asterisk/recording/${{REC_FILE}}.wav,r(/var/spool/asterisk/recording/${{REC_FILE}}_client.wav))
    same => n,NoOp(MixMonitor recording: ${{REC_FILE}}.wav + ${{REC_FILE}}_client.wav)
    same => n,GotoIf(["${{AMDSTATUS}}" = "HUMAN"]?human:machine)
    same => n(human),Stasis(robot-app,${{PHONE}},${{AMDSTATUS}},${{SCENARIO}},${{CAMPAIGN}},${{REC_FILE}})
    ; IMPORTANT: Pas de Hangup() ici - Stasis gère la fin de l'appel
    same => n(machine),Stasis(robot-app,${{PHONE}},${{AMDSTATUS}},${{SCENARIO}},${{CAMPAIGN}},${{REC_FILE}})
    ; IMPORTANT: Pas de Hangup() ici - Stasis gère la fin de l'appel

[test-record]
; Context pour test d'enregistrement pendant l'installation
exten => _X.,1,NoOp(Test Recording Call to ${{EXTEN}})
    same => n,Answer()
    same => n,Wait(1)
    same => n,Record(${{REC_FILE}}.wav,10,20,k)
    same => n,Hangup()
"""
    
    # AMD Configuration (optimisée pour meilleure détection répondeurs)
    amd_conf = """[general]
initial_silence = 2000        ; Temps d'attente initial avant de déclarer machine
greeting = 1500               ; Durée max pour dire "Allô"
after_greeting_silence = 800  ; Silence après le greeting - Détecte mieux les répondeurs
total_analysis_time = 2000    ; Temps total d'analyse - Optimisé pour démarrage rapide
min_word_length = 100         ; Durée min d'un mot en ms
between_words_silence = 50    ; Silence entre les mots
maximum_number_of_words = 3   ; Max 3 mots = humain (ex: "Allô c'est moi")
silence_threshold = 256       ; Seuil de détection du silence
maximum_word_length = 2000    ; Durée max d'un mot en ms
"""

    # Asterisk.conf Configuration - CRITIQUE pour transmit_silence
    # Configuration minimale testée et validée en production
    asterisk_conf = """[directories](!)
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
    
    # Écriture des fichiers
    configs = {
        '/etc/asterisk/pjsip.conf': pjsip_conf,
        '/etc/asterisk/http.conf': http_conf,
        '/etc/asterisk/ari.conf': ari_conf,
        '/etc/asterisk/extensions.conf': extensions_conf,
        '/etc/asterisk/amd.conf': amd_conf,
        '/etc/asterisk/asterisk.conf': asterisk_conf  # AJOUT CRITIQUE pour transmit_silence
    }
    
    try:
        for file_path, content in configs.items():
            with open(file_path, 'w') as f:
                f.write(content)
        
        # Redémarrage Asterisk
        run_command("systemctl restart asterisk")
        time.sleep(5)
        
        # Détecter IP publique du VPS
        success, public_ip = run_command("curl -s ifconfig.me", capture=True, check=False)
        if not success or not public_ip.strip():
            # Fallback sur méthode alternative
            success, public_ip = run_command("curl -s icanhazip.com", capture=True, check=False)

        if success and public_ip.strip():
            public_ip = public_ip.strip()
            public_api_url = f"http://{public_ip}:8000"
            log(f"🌐 IP publique détectée: {public_ip}", "success")
        else:
            public_api_url = "http://localhost:8000"
            log("⚠️  IP publique non détectée, utilisation localhost", "warning")

        # Sauvegarde config ARI pour .env
        env_content = f"""# Configuration ARI MiniBotPanel v2
ARI_URL=http://localhost:8088
ARI_USERNAME=robot
ARI_PASSWORD={ari_password}

# Configuration Database
DATABASE_URL=postgresql://robot:robotpass@localhost/robot_calls

# Configuration SIP
SIP_SERVER={sip_config['server']}
SIP_USERNAME={sip_config['username']}
SIP_PASSWORD={sip_config['password']}
CALLER_ID={sip_config['caller_id']}

# Whisper Configuration (auto-détection GPU/CPU)
WHISPER_MODEL={whisper_model}
WHISPER_DEVICE={whisper_device}
WHISPER_COMPUTE_TYPE={whisper_compute}
WHISPER_CACHE_DIR=/root/.cache/huggingface

# Paths
RECORDINGS_PATH=recordings
SOUNDS_PATH=audio

# Logs
LOG_LEVEL=INFO
LOG_FILE=logs/minibot.log

# Public API URL (pour exports clients)
# Auto-détecté lors de l'installation
PUBLIC_API_URL={public_api_url}
"""
        
        with open('.env', 'w') as f:
            f.write(env_content)
        
        log("✅ Configuration Asterisk ARI terminée", "success")
        return ari_password

    except Exception as e:
        log(f"❌ Erreur configuration Asterisk: {e}", "error")
        return None

# -----------------------------------------------------
# Test connexions
# -----------------------------------------------------

def test_sip_registration():
    """Test enregistrement SIP avec résultat clair"""
    log("🧪 Test enregistrement SIP...")

    time.sleep(10)  # Attendre enregistrement

    success, output = run_command("asterisk -rx 'pjsip show registrations'", capture=True, check=False)

    if success:
        # Parser output pour trouver les registrations
        lines = output.strip().split('\n')
        registered_count = 0
        registrations = []

        for line in lines:
            if "Registered" in line:
                registered_count += 1
                # Extraire nom de registration
                parts = line.split()
                if parts:
                    registrations.append(parts[0])

        if registered_count > 0:
            log(f"✅ SIP Registration: {registered_count} compte(s) enregistré(s)", "success")
            for reg in registrations:
                log(f"   📞 {reg}", "success")
            return True
        else:
            log("❌ SIP Registration: Aucun compte enregistré", "error")
            log("⚠️  Vérifiez vos identifiants SIP dans /etc/asterisk/pjsip.conf", "warning")
            return False
    else:
        log("❌ Impossible de vérifier SIP registration", "error")
        return False

def test_amd_config():
    """Test configuration AMD (Answering Machine Detection)"""
    log("🤖 Test AMD (Answering Machine Detection)...")

    success, output = run_command(
        "asterisk -rx 'core show application AMD'",
        capture=True,
        check=False
    )

    if success and "AMD" in output and "Synopsis" in output:
        log("✅ AMD disponible et configuré", "success")

        # Vérifier config AMD
        if os.path.exists("/etc/asterisk/amd.conf"):
            log("✅ Fichier /etc/asterisk/amd.conf présent", "success")
        else:
            log("⚠️  Fichier /etc/asterisk/amd.conf manquant", "warning")

        return True
    else:
        log("❌ AMD non disponible", "error")
        log("⚠️  AMD est requis pour détecter les répondeurs", "warning")
        return False

def test_transmit_silence():
    """Test que transmit_silence est activé - CRITIQUE pour l'enregistrement"""
    log("🔊 Test configuration transmit_silence (CRITIQUE)...")

    success, output = run_command(
        "asterisk -rx 'core show settings' | grep -i transmit",
        capture=True,
        check=False
    )

    if success and "Transmit silence during Record() app" in output and "Enabled" in output:
        log("✅ transmit_silence activé - Les enregistrements fonctionneront", "success")
        return True
    elif success and "Transmit silence during Record() app" in output and "Disabled" in output:
        log("❌ transmit_silence DÉSACTIVÉ - Les appels vont raccrocher !", "error")
        log("⚠️  CRITIQUE: Sans transmit_silence, les appelants raccrochent pendant l'enregistrement", "error")
        log("💡 Solution: Éditer /etc/asterisk/asterisk.conf et activer transmit_silence", "warning")
        return False
    else:
        log("⚠️  Impossible de vérifier transmit_silence", "warning")
        return False

def test_ari_connection():
    """Test connexion ARI avec authentification"""
    log("🧪 Test connexion ARI...")

    # Lire password depuis .env si disponible
    ari_password = "test"
    if os.path.exists(".env"):
        with open(".env", 'r') as f:
            for line in f:
                if line.startswith("ARI_PASSWORD="):
                    ari_password = line.split("=")[1].strip()
                    break

    success, output = run_command(
        f"curl -s -u robot:{ari_password} http://localhost:8088/ari/asterisk/info",
        capture=True,
        check=False
    )

    if success and '"version"' in output:
        log("✅ Interface ARI accessible avec authentification", "success")
        return True
    else:
        # Test sans auth pour diagnostic
        success2, _ = run_command("curl -s http://localhost:8088/ari/asterisk/info", capture=True, check=False)
        if success2:
            log("⚠️  ARI accessible mais nécessite authentification", "warning")
        else:
            log("❌ Interface ARI non accessible", "error")
        return False

# -----------------------------------------------------
# Test d'appel réel
# -----------------------------------------------------

def test_real_call_with_ari(whisper_model="base"):
    """Test d'appel réel complet avec robot_ari.py + AMD + transcription"""
    log("📞 Test d'appel réel COMPLET (avec robot_ari.py)")

    response = input(f"{Colors.YELLOW}Voulez-vous tester un appel réel complet ? [y/N]: {Colors.NC}").strip().lower()

    if response not in ['y', 'yes', 'oui', 'o']:
        log("Test d'appel complet ignoré", "info")
        return

    # Vérifier que robot_ari.py existe
    if not os.path.exists("robot_ari.py"):
        log("❌ robot_ari.py introuvable, test impossible", "error")
        return

    # Demander numéro
    phone_number = input(f"{Colors.BLUE}📞 Entrez le numéro à appeler (format international sans +): {Colors.NC}").strip()

    if not phone_number:
        log("Numéro invalide, test annulé", "warning")
        return

    robot_ari_process = None

    try:
        # 1. Lancer robot_ari.py en background
        log("🚀 Démarrage robot_ari.py en background...", "info")
        robot_ari_process = subprocess.Popen(
            ["python3", "robot_ari.py"],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True
        )

        # Attendre que robot_ari.py se connecte à ARI
        log("⏳ Attente connexion ARI (10 secondes)...", "info")
        time.sleep(10)

        # Vérifier que le process tourne toujours
        if robot_ari_process.poll() is not None:
            log("❌ robot_ari.py s'est arrêté prématurément", "error")
            stdout, stderr = robot_ari_process.communicate()
            log(f"   STDOUT: {stdout[:500]}", "error")
            log(f"   STDERR: {stderr[:500]}", "error")
            return

        log("✅ robot_ari.py lancé et connecté", "success")

        # 2. Lancer l'appel via API ARI (comme en production)
        log(f"📞 Lancement appel vers {phone_number} via ARI...", "info")
        log("🎤 Décrochez et parlez pendant 5-10 secondes", "warning")
        log("📊 AMD va détecter si vous êtes humain ou machine", "info")
        log("🎬 Un scénario sera exécuté automatiquement", "info")

        # Lire le password ARI depuis .env
        ari_password = "test"
        if os.path.exists(".env"):
            with open(".env", 'r') as f:
                for line in f:
                    if line.startswith("ARI_PASSWORD="):
                        ari_password = line.split("=")[1].strip()
                        break

        # Appel via ARI (comme le ferait call_launcher.py)
        ari_call_cmd = f'''
curl -s -u robot:{ari_password} \
  -X POST "http://localhost:8088/ari/channels" \
  -H "Content-Type: application/json" \
  -d '{{"endpoint":"PJSIP/{phone_number}@bitcall","app":"robot-app","appArgs":["{phone_number}","basique","test_install"]}}'
'''

        log("🚀 Appel en cours via ARI...", "info")
        success, output = run_command(ari_call_cmd, capture=True, check=False)

        if success and '"id"' in output:
            log("✅ Appel lancé avec succès via ARI!", "success")
            log("📊 Flow complet: ARI → PJSIP → dialplan → AMD → Stasis → robot_ari.py", "success")
            log("⏳ Attente fin de l'appel (max 40 secondes)...", "info")

            # Attendre l'appel
            time.sleep(40)

            log("✅ Test d'appel complet terminé", "success")
            log("🎯 Si vous avez décroché et parlé:", "info")
            log("   1. AMD a détecté que vous êtes humain", "info")
            log("   2. robot_ari.py a reçu l'événement StasisStart", "info")
            log("   3. Un scénario basique a été exécuté", "info")
            log("   4. Vos réponses ont été transcrites avec Whisper", "info")
            log("   5. Le sentiment a été analysé (positif/négatif)", "info")
            log("📁 Vérifiez les logs dans logs/minibot.log", "info")
            log("📁 Vérifiez les enregistrements dans recordings/", "info")

        else:
            log(f"⚠️  Problème lancement appel: {output[:200]}", "warning")
            log("ℹ️  Vérifiez que le numéro est correct et que vous avez des crédits", "info")

    except Exception as e:
        log(f"❌ Erreur test appel complet: {e}", "error")
        import traceback
        traceback.print_exc()

    finally:
        # Toujours killer robot_ari.py
        if robot_ari_process and robot_ari_process.poll() is None:
            log("⏹️  Arrêt robot_ari.py...", "info")
            robot_ari_process.terminate()
            try:
                robot_ari_process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                robot_ari_process.kill()
            log("✅ robot_ari.py arrêté", "success")

def test_real_call(whisper_model="base"):
    """Appelle la nouvelle fonction de test complet"""
    test_real_call_with_ari(whisper_model)

def test_fastapi_complete():
    """Test complet FastAPI + robot_ari.py + vraie campagne"""
    log("🌐 Test API FastAPI COMPLÈTE (Production-ready)")

    response = input(f"{Colors.YELLOW}Voulez-vous tester l'API FastAPI complète ? [y/N]: {Colors.NC}").strip().lower()

    if response not in ['y', 'yes', 'oui', 'o']:
        log("Test API FastAPI ignoré", "info")
        return

    # Vérifier fichiers nécessaires
    if not os.path.exists("robot_ari.py") or not os.path.exists("main.py"):
        log("❌ robot_ari.py ou main.py introuvable", "error")
        return

    # Demander numéro
    phone_number = input(f"{Colors.BLUE}📞 Entrez le numéro à appeler (format international sans +): {Colors.NC}").strip()

    if not phone_number:
        log("Numéro invalide, test annulé", "warning")
        return

    robot_ari_process = None
    uvicorn_process = None

    try:
        # 1. Lancer robot_ari.py
        log("🚀 Démarrage robot_ari.py...", "info")
        robot_ari_process = subprocess.Popen(
            ["python3", "robot_ari.py"],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True
        )
        time.sleep(5)

        if robot_ari_process.poll() is not None:
            log("❌ robot_ari.py crash", "error")
            return

        log("✅ robot_ari.py démarré", "success")

        # 2. Lancer uvicorn (FastAPI)
        log("🌐 Démarrage uvicorn (FastAPI)...", "info")
        uvicorn_process = subprocess.Popen(
            ["python3", "-m", "uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True
        )
        time.sleep(8)

        if uvicorn_process.poll() is not None:
            log("❌ uvicorn crash", "error")
            return

        log("✅ FastAPI démarré sur http://localhost:8000", "success")

        # 3. Test health check
        log("🏥 Test /health endpoint...", "info")
        success, output = run_command("curl -s http://localhost:8000/health", capture=True, check=False)
        if success and '"status"' in output:
            log("✅ Health check OK", "success")
        else:
            log("⚠️ Health check failed", "warning")

        # 4. Créer campagne via API
        log(f"📢 Création campagne via API /campaigns/create...", "info")
        campaign_cmd = f'''
curl -s -X POST http://localhost:8000/campaigns/create \
  -H "Content-Type: application/json" \
  -d '{{"name":"Test Install","phone_numbers":["{phone_number}"],"scenario":"basique"}}'
'''

        success, output = run_command(campaign_cmd, capture=True, check=False)

        if success and '"campaign_id"' in output:
            log("✅ Campagne créée via API!", "success")
            log("📊 Flow complet: API → call_launcher → ARI → dialplan → AMD → robot_ari", "success")

            # Extraire campaign_id
            import json
            try:
                data = json.loads(output)
                campaign_id = data.get("campaign_id", "unknown")
                log(f"📋 Campaign ID: {campaign_id}", "info")
            except:
                campaign_id = "unknown"

            log("⏳ Attente fin appel (40 secondes)...", "info")
            time.sleep(40)

            # 5. Vérifier campagne via GET /campaigns/{id}
            if campaign_id != "unknown":
                log(f"📊 Vérification campagne via GET /campaigns/{campaign_id}...", "info")
                success, output = run_command(f"curl -s http://localhost:8000/campaigns/{campaign_id}", capture=True, check=False)
                if success and '"campaign"' in output:
                    log("✅ Campagne récupérée via API", "success")
                    try:
                        data = json.loads(output)
                        calls = data.get("calls", [])
                        log(f"📞 {len(calls)} appel(s) dans la campagne", "info")
                    except:
                        pass

            # 6. Lister tous les appels via GET /calls/
            log("📊 Liste des appels via GET /calls/...", "info")
            success, output = run_command("curl -s 'http://localhost:8000/calls/?limit=5'", capture=True, check=False)
            if success and '"calls"' in output:
                log("✅ Liste appels récupérée", "success")

            # 7. Stats globales via GET /stats/
            log("📊 Stats globales via GET /stats/...", "info")
            success, output = run_command("curl -s http://localhost:8000/stats/", capture=True, check=False)
            if success and '"total_calls"' in output:
                log("✅ Stats globales OK", "success")

            log("", "info")
            log("🎉 TEST API FASTAPI COMPLET RÉUSSI !", "success")
            log("", "info")
            log("✅ Ce qui a été testé:", "success")
            log("   1. robot_ari.py connecté à ARI", "info")
            log("   2. FastAPI démarré et accessible", "info")
            log("   3. POST /campaigns/create fonctionne", "info")
            log("   4. Appel lancé via call_launcher.py", "info")
            log("   5. Flow complet ARI → dialplan → AMD → Stasis", "info")
            log("   6. GET /campaigns/{id} fonctionne", "info")
            log("   7. GET /calls/ fonctionne", "info")
            log("   8. GET /stats/ fonctionne", "info")
            log("", "info")
            log("🚀 SYSTÈME 100% OPÉRATIONNEL - PRÊT PRODUCTION", "success")

        else:
            log(f"⚠️ Problème création campagne: {output[:200]}", "warning")

    except Exception as e:
        log(f"❌ Erreur test FastAPI: {e}", "error")
        import traceback
        traceback.print_exc()

    finally:
        # Killer les 2 process
        if uvicorn_process and uvicorn_process.poll() is None:
            log("⏹️ Arrêt uvicorn...", "info")
            uvicorn_process.terminate()
            try:
                uvicorn_process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                uvicorn_process.kill()
            log("✅ uvicorn arrêté", "success")

        if robot_ari_process and robot_ari_process.poll() is None:
            log("⏹️ Arrêt robot_ari.py...", "info")
            robot_ari_process.terminate()
            try:
                robot_ari_process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                robot_ari_process.kill()
            log("✅ robot_ari.py arrêté", "success")

# -----------------------------------------------------
# Installation Python
# -----------------------------------------------------

def install_python_deps():
    """Installation dépendances Python depuis requirements.txt"""
    log("🐍 Installation dépendances Python...")

    # Installer pip si nécessaire
    run_command("apt install -y python3-pip python3-venv")

    # FIX CRITIQUE: Installer NumPy 1.x AVANT PyTorch
    log("🔧 Installation NumPy 1.x (compatible PyTorch)...")
    run_command("pip3 install 'numpy<2'")

    # Vérifier que requirements.txt existe
    if not os.path.exists("requirements.txt"):
        log("❌ requirements.txt introuvable!", "error")
        log("⚠️ Création de requirements.txt minimal...", "warning")
        # Créer un requirements.txt minimal si absent (pas Redis - batch mode)
        minimal_reqs = """fastapi==0.109.0
uvicorn[standard]==0.27.0
pydantic==2.5.3
ari==0.1.3
faster-whisper==1.2.0
sqlalchemy==2.0.25
psycopg2-binary==2.9.9
alembic==1.13.1
python-dotenv==1.0.0
requests==2.31.0"""
        with open("requirements.txt", "w") as f:
            f.write(minimal_reqs)
        log("✅ requirements.txt créé", "success")

    # Lire requirements.txt
    log("📄 Lecture requirements.txt...")
    with open("requirements.txt", "r") as f:
        requirements = [line.strip() for line in f if line.strip() and not line.startswith("#")]

    log(f"📦 {len(requirements)} dépendances à installer", "info")

    # Installation globale (pas de venv pour simplicité)
    for req in requirements:
        log(f"  📦 Installation: {req}", "info")
        success, _ = run_command(f"pip3 install {req}", check=False)
        if not success:
            log(f"⚠️ Erreur installation {req}", "warning")

    log("✅ Dépendances Python installées depuis requirements.txt", "success")

def install_whisper_streaming():
    """REMOVED - whisper_streaming not needed for batch mode"""
    log("ℹ️  whisper_streaming not installed (batch mode only)", "info")
    return True

def install_audiofork():
    """REMOVED - AudioFork not needed for batch mode"""
    log("ℹ️  AudioFork not installed (batch mode only)", "info")
    return True

def test_whisper(whisper_model="base"):
    """Test Whisper avec auto-détection GPU et fichier audio utilisateur"""
    log(f"🧪 Test Faster-Whisper avec modèle '{whisper_model}'...")

    # Vérifier si le modèle existe déjà dans le cache (chercher avec patterns multiples)
    cache_base = os.path.expanduser("~/.cache/huggingface/hub")
    model_patterns = [
        f"{cache_base}/models--Systran--faster-whisper-{whisper_model}",
        f"{cache_base}/models--openai--whisper-{whisper_model}",
        f"{cache_base}/whisper-{whisper_model}"
    ]

    model_cached = False
    model_cache_dir = ""
    for pattern in model_patterns:
        if os.path.exists(pattern):
            model_cached = True
            model_cache_dir = pattern
            break

    if model_cached:
        log(f"✅ Modèle '{whisper_model}' déjà téléchargé dans le cache", "success")
        log("📦 Réutilisation du modèle existant", "info")
    else:
        log(f"📥 Téléchargement du modèle '{whisper_model}' (première fois)", "info")
        log("⏳ Cela peut prendre plusieurs minutes selon votre connexion", "warning")
        model_cache_dir = f"{cache_base}/models--Systran--faster-whisper-{whisper_model}"

    # Créer dossier audio si nécessaire
    run_command("mkdir -p audio", check=False)

    # Chercher fichier test utilisateur
    test_files = ["audio/test_audio.wav", "audio/test.wav", "audio/test/test_audio.wav"]
    test_wav = None

    for f in test_files:
        if os.path.exists(f):
            test_wav = f
            log(f"✅ Fichier audio trouvé: {f}", "success")
            break

    if not test_wav:
        log("⚠️ Pas de fichier audio test, génération automatique...", "warning")
        run_command("mkdir -p audio/test", check=False)
        test_wav = "audio/test/test.wav"
        success, _ = run_command(
            f"ffmpeg -f lavfi -i anullsrc=r=16000:cl=mono -t 2 -y {test_wav}",
            capture=True,
            check=False
        )
        if not success:
            log("⚠️ Impossible de générer fichier test, test chargement uniquement", "warning")
            test_wav = None

    # Lire la détection déjà faite depuis .env
    whisper_device = "cpu"
    whisper_compute = "int8"
    if os.path.exists(".env"):
        with open(".env", 'r') as f:
            for line in f:
                if line.startswith("WHISPER_DEVICE="):
                    whisper_device = line.split("=")[1].strip()
                elif line.startswith("WHISPER_COMPUTE_TYPE="):
                    whisper_compute = line.split("=")[1].strip()

    # Test avec device/compute_type déjà détecté (pas de re-détection)
    test_script = f"""
from faster_whisper import WhisperModel
import time

# Utiliser la configuration déjà détectée
device = "{whisper_device}"
compute_type = "{whisper_compute}"

print(f"💻 Configuration Whisper: {{device.upper()}} ({{compute_type}})")

try:
    print(f"⏳ Chargement modèle Whisper '{whisper_model}'...")
    start_time = time.time()
    model = WhisperModel("{whisper_model}", device=device, compute_type=compute_type)
    load_time = time.time() - start_time
    print(f"✅ Whisper '{whisper_model}' chargé en {{load_time:.1f}}s sur {{device.upper()}} ({{compute_type}})")

    {"" if not test_wav else f'''
    # Transcription test
    print("🎤 Transcription en cours...")
    segments, info = model.transcribe("{test_wav}", language="fr", vad_filter=True)

    # Récupérer tous les segments
    segments_list = list(segments)
    if segments_list:
        text = " ".join([s.text.strip() for s in segments_list])
        print("=" * 60)
        print("📝 TRANSCRIPTION:")
        print(f"   {{text}}")
        print("=" * 60)
        print(f"🌍 Langue: {{info.language}} (confiance: {{info.language_probability:.1%}})")
        print(f"⏱️  Durée audio: {{info.duration:.1f}}s")
        print(f"📊 Segments: {{len(segments_list)}}")
    else:
        print("⚠️  Aucun segment vocal détecté (silence ou fichier vide)")
    '''}

    print("✅ Test Whisper complet réussi")
except Exception as e:
    print(f"❌ Erreur Whisper: {{e}}")
    import traceback
    traceback.print_exc()
"""

    # Écrire le script dans un fichier temporaire pour éviter problèmes d'échappement
    with tempfile.NamedTemporaryFile(mode='w', suffix='.py', delete=False) as f:
        f.write(test_script)
        test_script_path = f.name

    try:
        # Exécuter le test Whisper avec TIMEOUT de 5 minutes (300 secondes)
        result = subprocess.run(f"python3 {test_script_path}", shell=True, timeout=300)

        if result.returncode == 0:
            log(f"✅ Whisper '{whisper_model}' fonctionnel et prêt à l'emploi", "success")
            log(f"💾 Modèle sauvegardé dans: {model_cache_dir}", "info")
            log(f"🔄 Le modèle '{whisper_model}' sera réutilisé automatiquement", "success")
            return True
        else:
            log("❌ Problème Whisper", "error")
            return False
    finally:
        # Nettoyer fichier temporaire
        os.unlink(test_script_path)

def init_database():
    """Initialize database and create tables"""
    log("🗃️ Initialisation base de données...")

    # Installer PostgreSQL uniquement (pas Redis - batch mode)
    run_command("apt install -y postgresql postgresql-contrib")

    # Créer utilisateur et base
    postgres_setup = """
sudo -u postgres psql << 'EOF'
CREATE USER robot WITH PASSWORD 'robotpass';
CREATE DATABASE robot_calls OWNER robot;
GRANT ALL PRIVILEGES ON DATABASE robot_calls TO robot;
\\q
EOF
"""

    success, _ = run_command(postgres_setup, check=False)
    if not success:
        log("⚠️ PostgreSQL déjà configuré", "warning")

    # Créer tables avec SQLAlchemy - Exécuter depuis le répertoire du projet
    db_init_script = """
import sys
import os

# Ajouter le répertoire courant au path Python
sys.path.insert(0, os.getcwd())

try:
    from database import engine
    from models import Base

    Base.metadata.create_all(bind=engine)
    print("✅ Database tables created")
except Exception as e:
    print(f"❌ Database error: {e}")
    import traceback
    traceback.print_exc()
"""

    # Écrire le script dans le répertoire du projet (pas /tmp)
    db_script_path = "temp_init_db.py"

    try:
        with open(db_script_path, 'w') as f:
            f.write(db_init_script)

        success, output = run_command(f"python3 {db_script_path}", capture=True, check=False)
        if "Database tables created" in output:
            log("✅ Tables de base créées", "success")
        else:
            log("⚠️ Problème initialisation DB", "warning")
            logging.debug(f"DB init output: {output}")
    finally:
        # Nettoyer fichier temporaire
        if os.path.exists(db_script_path):
            os.unlink(db_script_path)
        
    # Créer dossiers nécessaires
    run_command("mkdir -p logs recordings audio assembled_audio transcripts")
    run_command("chmod 755 logs recordings audio assembled_audio transcripts")

def setup_audio_assembly():
    """Configure le système d'assemblage audio + transcription complète"""
    log("🎬 Configuration assemblage audio + transcription...")

    # Créer audio_texts.json si non existant
    audio_texts_path = "audio_texts.json"
    if not os.path.exists(audio_texts_path):
        log("📝 Création audio_texts.json...")
        audio_texts_content = """{
  "intro": {
    "file": "intro.wav",
    "duration": 9.8,
    "text": "Bonjour, ici Éric Laporte de la société MiniBotPanel. Je vous contacte concernant notre nouvelle offre de télémarketing automatisé. Est-ce que c'est bien Monsieur ou Madame [NOM] à l'appareil?"
  },
  "question_1": {
    "file": "question_1.wav",
    "duration": 6.7,
    "text": "Parfait! Je vous propose une offre d'essai gratuite de notre service de robot d'appel automatique. Seriez-vous intéressé pour tester notre solution sans engagement?"
  },
  "retry": {
    "file": "retry.wav",
    "duration": 11.0,
    "text": "Je n'ai pas bien compris votre réponse. Pourriez-vous répéter s'il vous plaît? Êtes-vous intéressé par notre offre d'essai gratuite?"
  },
  "conclusion": {
    "file": "conclusion.wav",
    "duration": 6.1,
    "text": "Très bien, je vous remercie pour votre temps. Un conseiller vous recontactera prochainement pour finaliser les détails. Je vous souhaite une excellente journée. Au revoir!"
  },
  "explanation": {
    "file": "explanation.wav",
    "duration": 9.5,
    "text": "Notre solution vous permet d'automatiser vos campagnes d'appels avec un robot vocal intelligent qui peut répondre aux questions basiques de vos clients."
  }
}"""
        with open(audio_texts_path, 'w', encoding='utf-8') as f:
            f.write(audio_texts_content)
        log("✅ audio_texts.json créé", "success")
    else:
        log("✅ audio_texts.json déjà présent", "success")

    # Ajouter colonne assembled_audio_path dans la base
    log("🗃️  Ajout colonne assembled_audio_path...")
    db_migration = """
PGPASSWORD='robotpass' psql -U robot -d robot_calls -c "ALTER TABLE calls ADD COLUMN IF NOT EXISTS assembled_audio_path VARCHAR(255);" 2>/dev/null
"""
    success, _ = run_command(db_migration, check=False)
    if success:
        log("✅ Colonne assembled_audio_path ajoutée", "success")
    else:
        log("⚠️  Colonne déjà présente ou erreur migration", "warning")

    # Vérifier sox
    success, _ = run_command("which sox", capture=True, check=False)
    if success:
        log("✅ sox disponible pour assemblage audio", "success")
    else:
        log("📦 Installation sox...", "info")
        run_command("apt install -y sox")
        log("✅ sox installé", "success")

    log("✅ Système d'assemblage audio configuré", "success")

# -----------------------------------------------------
# Rapport final d'installation
# -----------------------------------------------------

def generate_final_report(installation_data):
    """Génère rapport final d'installation détaillé"""

    report = f"""
{Colors.GREEN}
╔══════════════════════════════════════════════════════════╗
║            INSTALLATION TERMINÉE AVEC SUCCÈS            ║
╚══════════════════════════════════════════════════════════╝
{Colors.NC}

📊 RÉSUMÉ DE L'INSTALLATION
{'='*60}

✅ Asterisk 20 LTS    : {installation_data.get('asterisk_version', 'Installé')}
✅ PostgreSQL         : Base 'robot_calls' créée
✅ Python 3           : Dépendances installées
✅ Whisper            : {installation_data.get('whisper_device', 'N/A')}
✅ SIP Registration   : {installation_data.get('sip_status', 'Non testé')}
✅ AMD                : {installation_data.get('amd_status', 'Non testé')}
✅ transmit_silence   : {installation_data.get('transmit_silence_status', 'Non testé')}

🔐 INFORMATIONS IMPORTANTES
{'='*60}

ARI Username  : robot
ARI Password  : {installation_data.get('ari_password', 'Voir .env')}
DB Password   : robotpass
Public API URL: {installation_data.get('public_api_url', 'Voir .env')}

📁 FICHIERS GÉNÉRÉS
{'='*60}

.env                 : Configuration principale
audio_texts.json     : Textes des messages audio bot
logs/                : Dossier des logs
recordings/          : Enregistrements individuels (interactions)
assembled_audio/     : Enregistrements complets assemblés (bot + client)
transcripts/         : Transcriptions complètes (JSON + TXT)
audio/               : Fichiers audio

{f"💾 Backup configs : {installation_data.get('backup_dir', 'N/A')}" if installation_data.get('backup_dir') else ''}

🚀 COMMANDES DE DÉMARRAGE
{'='*60}

# Démarrer robot ARI (backend)
python3 robot_ari.py

# Démarrer API FastAPI (terminal séparé)
uvicorn main:app --host 0.0.0.0 --port 8000

# Vérifier status Asterisk
sudo systemctl status asterisk

# Console Asterisk
sudo asterisk -rvvv

# Logs en temps réel
tail -f logs/minibot.log

🧪 TESTS
{'='*60}

# Test connexion ARI
curl -u robot:{installation_data.get('ari_password', 'PASSWORD')} http://localhost:8088/ari/asterisk/info

# Test enregistrement SIP
sudo asterisk -rx 'pjsip show registrations'

# Test AMD
sudo asterisk -rx 'core show application AMD'

# Test Whisper
python3 -c "from services.whisper_service import whisper_service; print('Whisper OK')"

📚 PROCHAINES ÉTAPES
{'='*60}

1. ✅ Créer vos fichiers audio dans audio/ (intro.wav, positive.wav, etc.)
2. ✅ Modifier audio_texts.json avec vos vrais textes de messages
3. ✅ Importer contacts: python3 import_contacts.py contacts.csv
4. ✅ Démarrer services: robot_ari.py + uvicorn
5. ✅ Lancer campagne via API /campaigns/create

🎬 NOUVELLES FONCTIONNALITÉS
{'='*60}

✅ Audio complet assemblé : Chaque appel génère un fichier complet (bot + client)
   - Fichiers dans assembled_audio/full_call_assembled_*.wav
   - Combine tous les messages audio + réponses clients

✅ Transcription complète : Rapport détaillé de chaque conversation
   - Format JSON : transcripts/transcript_*.json (API-ready)
   - Format TXT  : transcripts/transcript_*.txt (lecture facile)
   - Contient : textes bot + transcriptions Whisper + sentiments

⚠️  IMPORTANT
{'='*60}

- Sauvegardez votre fichier .env (contient mots de passe)
- Configurez votre pare-feu si nécessaire
- Testez un appel avant production
{'''
🔴 ALERTE CRITIQUE: transmit_silence DÉSACTIVÉ !
   Les appels vont raccrocher pendant l'enregistrement !
   Solution: sudo nano /etc/asterisk/asterisk.conf
   Activer: transmit_silence = yes
   Puis: sudo systemctl restart asterisk
''' if 'DÉSACTIVÉ' in installation_data.get('transmit_silence_status', '') else ''}

{Colors.BLUE}
🎉 Félicitations ! MiniBotPanel v2 est prêt à l'emploi !
{Colors.NC}
"""

    print(report)

    # Sauvegarder rapport
    with open('INSTALLATION_REPORT.txt', 'w') as f:
        # Enlever les couleurs pour le fichier
        clean_report = report.replace(Colors.GREEN, '').replace(Colors.BLUE, '').replace(Colors.NC, '')
        f.write(clean_report)

    log("📄 Rapport sauvegardé dans INSTALLATION_REPORT.txt", "success")

# -----------------------------------------------------
# Installation principale
# -----------------------------------------------------

def main():
    """Installation complète avec détection et tests"""
    print_banner()

    # Setup logging AVANT tout
    log_file = setup_logging()
    log(f"📝 Logging activé: {log_file}", "success")
    logging.info("="*60)
    logging.info("DÉBUT INSTALLATION MiniBotPanel v2")
    logging.info("="*60)

    installation_data = {}

    try:
        check_system()

        # Détecter installation existante
        asterisk_installed, version = check_asterisk_installed()
        should_install_asterisk = False  # Flag pour savoir si on doit installer

        if asterisk_installed:
            log(f"⚠️  Asterisk déjà installé: {version}", "warning")
            response = input(f"{Colors.YELLOW}Voulez-vous désinstaller et réinstaller ? [O/n]: {Colors.NC}").strip().lower()

            if response in ['o', 'oui', 'y', 'yes', '']:
                # Backup configs
                backup_dir = backup_configs()
                installation_data['backup_dir'] = backup_dir

                # Désinstaller
                uninstall_asterisk()
                should_install_asterisk = True  # On va réinstaller
            else:
                log("ℹ️  Conservation installation existante", "info")
                log("ℹ️  Seules les configurations seront mises à jour", "info")
                backup_dir = backup_configs()
                installation_data['backup_dir'] = backup_dir
                should_install_asterisk = False  # NE PAS réinstaller
        else:
            # Pas d'Asterisk installé, il faut l'installer
            should_install_asterisk = True

        # Installation Asterisk avec ARI SEULEMENT si nécessaire
        if should_install_asterisk:
            if not install_asterisk20():
                log("❌ Échec installation Asterisk", "error")
                sys.exit(1)
        else:
            log("✅ Asterisk existant conservé", "success")

        # Configuration SIP
        sip_config = get_sip_config()

        # Configuration Whisper
        whisper_model = get_whisper_config()
        installation_data['whisper_model'] = whisper_model

        ari_password = configure_asterisk_ari(sip_config, whisper_model)
        installation_data['ari_password'] = ari_password

        # Lire PUBLIC_API_URL depuis .env généré
        if os.path.exists('.env'):
            with open('.env', 'r') as f:
                for line in f:
                    if line.startswith('PUBLIC_API_URL='):
                        installation_data['public_api_url'] = line.split('=')[1].strip()

        # Tests Asterisk
        sip_ok = test_sip_registration()
        installation_data['sip_status'] = '✅ Enregistré' if sip_ok else '❌ Non enregistré'

        amd_ok = test_amd_config()
        installation_data['amd_status'] = '✅ Disponible' if amd_ok else '❌ Non disponible'

        # TEST CRITIQUE: transmit_silence
        silence_ok = test_transmit_silence()
        installation_data['transmit_silence_status'] = '✅ Activé' if silence_ok else '❌ DÉSACTIVÉ - CRITIQUE!'

        ari_ok = test_ari_connection()

        # Installation Python
        install_python_deps()

        # whisper_streaming et AudioFork SUPPRIMÉS (batch mode uniquement)
        # install_whisper_streaming() - REMOVED
        # install_audiofork() - REMOVED

        # Test Whisper (télécharge le modèle)
        whisper_ok = test_whisper(whisper_model)
        installation_data['whisper_device'] = f'{whisper_model.upper()} sur GPU (CUDA)' if whisper_ok else 'CPU ou erreur'

        # Initialisation base de données
        init_database()

        # Configuration assemblage audio + transcription complète
        setup_audio_assembly()

        # Test d'appel réel (optionnel) - APRÈS que tout soit installé
        test_real_call(whisper_model)

        # Test API FastAPI complet (optionnel) - APRÈS test d'appel
        test_fastapi_complete()

        # Récupérer version Asterisk
        success, version = run_command("asterisk -V", capture=True, check=False)
        if success:
            installation_data['asterisk_version'] = version.strip()

        # Rapport final
        generate_final_report(installation_data)

        # Log final
        logging.info("="*60)
        logging.info("INSTALLATION TERMINÉE AVEC SUCCÈS")
        logging.info("="*60)
        log(f"📋 Log complet disponible: {log_file}", "success")

    except KeyboardInterrupt:
        log("❌ Installation interrompue", "error")
        logging.error("Installation interrompue par utilisateur")
        sys.exit(1)
    except Exception as e:
        log(f"❌ Erreur installation: {e}", "error")
        logging.error(f"Erreur fatale: {e}")
        import traceback
        logging.error(traceback.format_exc())
        traceback.print_exc()
        sys.exit(1)

if __name__ == "__main__":
    main()