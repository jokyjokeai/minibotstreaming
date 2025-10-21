#!/usr/bin/env python3
# ==============================================
# SCRIPT DÉSINSTALLATION MiniBotPanel v2
# Suppression complète et propre du système
# ==============================================

import os
import sys
import subprocess

class Colors:
    GREEN = '\033[92m'
    RED = '\033[91m'
    YELLOW = '\033[93m'
    BLUE = '\033[94m'
    NC = '\033[0m'

def run_command(command, check=True):
    """Exécute une commande shell"""
    try:
        result = subprocess.run(command, shell=True, check=check, capture_output=True, text=True)
        return True, result.stdout
    except subprocess.CalledProcessError as e:
        return False, str(e)

def log(msg, level="info"):
    """Logger avec couleurs"""
    if level == "success":
        print(f"{Colors.GREEN}✅ {msg}{Colors.NC}")
    elif level == "error":
        print(f"{Colors.RED}❌ {msg}{Colors.NC}")
    elif level == "warning":
        print(f"{Colors.YELLOW}⚠️  {msg}{Colors.NC}")
    else:
        print(f"{Colors.BLUE}ℹ️  {msg}{Colors.NC}")

def print_banner():
    """Bannière de désinstallation"""
    print(f"""
{Colors.RED}
╔══════════════════════════════════════════════════════════╗
║            DÉSINSTALLATION MiniBotPanel v2              ║
║              ⚠️  ATTENTION: SUPPRESSION COMPLÈTE          ║
╚══════════════════════════════════════════════════════════╝
{Colors.NC}
""")

def confirm_uninstall():
    """Demande confirmation"""
    print(f"{Colors.YELLOW}")
    print("Cette opération va supprimer:")
    print("  • Asterisk 22 + AudioFork (binaires + configs)")
    print("  • Base de données PostgreSQL 'minibot_db'")
    print("  • Utilisateur PostgreSQL 'robot'")
    print("  • Ollama + modèles NLP locaux")
    print("  • Modèles Vosk français")
    print("  • Fichiers logs, recordings, audio")
    print("  • Configurations /etc/asterisk/")
    print(f"{Colors.NC}")

    response = input(f"{Colors.RED}Voulez-vous VRAIMENT continuer ? Tapez 'yes' pour confirmer: {Colors.NC}").strip()

    if response != "yes":
        log("Désinstallation annulée", "info")
        sys.exit(0)

def uninstall_asterisk():
    """Désinstallation Asterisk"""
    log("🗑️  Désinstallation Asterisk...")

    # Arrêter Asterisk
    log("⏹️  Arrêt Asterisk...")
    run_command("systemctl stop asterisk", check=False)
    run_command("killall -9 asterisk", check=False)

    # Désinstaller via make
    asterisk_src = "/usr/src/asterisk-22*"
    success, dirs = run_command(f"ls -d {asterisk_src} 2>/dev/null", check=False)
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
        "/usr/src/asterisk-*",
        "/opt/minibot",
        "/var/lib/vosk-models"
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

    log("Asterisk désinstallé", "success")

def uninstall_database():
    """Suppression base PostgreSQL"""
    log("🗃️  Suppression base de données...")

    # Supprimer base
    run_command("sudo -u postgres dropdb minibot_db", check=False)

    # Supprimer utilisateur
    run_command("sudo -u postgres dropuser robot", check=False)

    log("Base de données supprimée", "success")

def remove_python_deps():
    """Suppression dépendances Python"""
    log("🐍 Désinstallation packages Python...")

    packages = [
        "fastapi",
        "uvicorn",
        "sqlalchemy",
        "alembic",
        "pydantic",
        "ari",
        "vosk",
        "webrtcvad",
        "websockets",
        "ollama",
        "psycopg2-binary",
        "librosa",
        "scipy",
        "soundfile"
    ]

    for pkg in packages:
        run_command(f"pip3 uninstall -y {pkg}", check=False)

    log("Packages Python désinstallés", "success")

def uninstall_ollama():
    """Désinstallation Ollama"""
    log("🤖 Désinstallation Ollama...")

    # Arrêter Ollama
    run_command("systemctl stop ollama", check=False)
    run_command("systemctl disable ollama", check=False)

    # Supprimer binaire et service
    run_command("rm -f /usr/local/bin/ollama", check=False)
    run_command("rm -f /etc/systemd/system/ollama.service", check=False)
    run_command("systemctl daemon-reload")

    # Supprimer modèles et données
    run_command("rm -rf ~/.ollama", check=False)
    run_command("rm -rf /usr/share/ollama", check=False)

    log("Ollama désinstallé", "success")

def remove_project_files():
    """Suppression fichiers projet"""
    log("📁 Nettoyage fichiers projet...")

    files_to_remove = [
        ".env",
        "logs",
        "recordings",
        "audio/test",
        "INSTALLATION_REPORT.txt"
    ]

    for f in files_to_remove:
        if os.path.exists(f):
            run_command(f"rm -rf {f}", check=False)

    log("Fichiers projet nettoyés", "success")

def main():
    """Désinstallation principale"""
    # Vérifier root
    if os.geteuid() != 0:
        log("Script doit être exécuté en tant que root (sudo)", "error")
        sys.exit(1)

    print_banner()
    confirm_uninstall()

    log("🚀 Début désinstallation...")

    try:
        uninstall_asterisk()
        uninstall_database()
        uninstall_ollama()
        remove_python_deps()
        remove_project_files()

        print(f"""
{Colors.GREEN}
╔══════════════════════════════════════════════════════════╗
║           DÉSINSTALLATION TERMINÉE AVEC SUCCÈS          ║
╚══════════════════════════════════════════════════════════╝
{Colors.NC}

✅ Tous les composants ont été supprimés:
   • Asterisk 22 + AudioFork
   • PostgreSQL (base minibot_db)
   • Ollama + modèles NLP
   • Modèles Vosk français
   • Packages Python streaming
   • Fichiers projet

💡 Le code source est conservé. Pour le supprimer:
   rm -rf {os.getcwd()}

""")

    except Exception as e:
        log(f"Erreur lors de la désinstallation: {e}", "error")
        sys.exit(1)

if __name__ == "__main__":
    main()
