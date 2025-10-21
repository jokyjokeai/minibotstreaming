#!/usr/bin/env python3
"""
Debug VPS via SSH avec Paramiko
Fix du problème Asterisk bloqué
"""

import paramiko
import time
import sys

def connect_vps():
    """Connexion SSH au VPS"""
    print("🔌 Connexion au VPS...")
    
    # Informations de connexion (via arguments ou variables d'environnement)
    import os
    
    host = os.getenv('VPS_HOST') or sys.argv[1] if len(sys.argv) > 1 else input("🌐 IP du VPS: ").strip()
    username = os.getenv('VPS_USER') or (sys.argv[2] if len(sys.argv) > 2 else "root")
    password = os.getenv('VPS_PASS') or (sys.argv[3] if len(sys.argv) > 3 else input("🔐 Password: ").strip())
    
    try:
        # Connexion SSH
        ssh = paramiko.SSHClient()
        ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        ssh.connect(hostname=host, username=username, password=password, timeout=30, auth_timeout=30, banner_timeout=30)
        
        print(f"✅ Connecté à {host}")
        return ssh
        
    except Exception as e:
        print(f"❌ Erreur connexion: {e}")
        return None

def run_command(ssh, cmd, description=""):
    """Exécute une commande et affiche le résultat"""
    if description:
        print(f"\n🔧 {description}")
    print(f"💻 {cmd}")
    
    try:
        stdin, stdout, stderr = ssh.exec_command(cmd)
        
        # Attendre la fin de la commande
        exit_status = stdout.channel.recv_exit_status()
        
        # Lire les résultats
        output = stdout.read().decode('utf-8')
        error = stderr.read().decode('utf-8')
        
        if output:
            print(f"📤 {output.strip()}")
        if error and exit_status != 0:
            print(f"📥 Error: {error.strip()}")
            
        return exit_status == 0, output, error
        
    except Exception as e:
        print(f"❌ Erreur commande: {e}")
        return False, "", str(e)

def debug_asterisk(ssh):
    """Debug et fix du problème Asterisk"""
    print("\n🚨 DEBUG ASTERISK BLOQUÉ")
    print("=" * 40)
    
    # 1. Vérifier processus Asterisk
    run_command(ssh, "ps aux | grep asterisk | grep -v grep", "Processus Asterisk")
    
    # 2. Arrêt forcé
    run_command(ssh, "pkill -9 asterisk", "Arrêt forcé Asterisk")
    run_command(ssh, "systemctl stop asterisk", "Arrêt service")
    time.sleep(2)
    
    # 3. Bloquer port SIP temporairement
    run_command(ssh, "iptables -I INPUT -p udp --dport 5060 -j DROP", "Blocage port SIP")
    
    # 4. Nettoyer
    run_command(ssh, "rm -f /var/run/asterisk/asterisk.pid", "Nettoyage PID")
    
    # 5. Démarrer Asterisk
    print("\n⏳ Démarrage Asterisk...")
    success, output, error = run_command(ssh, "systemctl start asterisk", "Démarrage Asterisk")
    
    time.sleep(5)
    
    # 6. Vérifier statut
    success, output, error = run_command(ssh, "systemctl is-active asterisk", "Vérification statut")
    
    if "active" in output:
        print("✅ Asterisk démarré avec succès!")
        
        # 7. Débloquer port SIP
        run_command(ssh, "iptables -D INPUT -p udp --dport 5060 -j DROP", "Déblocage port SIP")
        
        # 8. Vérifier endpoints PJSIP
        run_command(ssh, "asterisk -rx 'pjsip show endpoints'", "Vérification endpoints")
        
    else:
        print("❌ Asterisk toujours bloqué")
        run_command(ssh, "tail -20 /var/log/asterisk/messages", "Logs d'erreur")

def main():
    """Point d'entrée principal"""
    ssh = connect_vps()
    if not ssh:
        sys.exit(1)
    
    try:
        debug_asterisk(ssh)
        
        print("\n🎯 Diagnostic terminé")
        
    except KeyboardInterrupt:
        print("\n⏹️ Interruption utilisateur")
    
    finally:
        ssh.close()
        print("🔌 Connexion fermée")

if __name__ == "__main__":
    main()