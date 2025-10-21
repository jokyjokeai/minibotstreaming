#!/usr/bin/env python3
"""
Diagnostic SIP pour VPS
"""
import paramiko
import time
import sys

def connect_and_debug():
    """Se connecter au VPS et diagnostiquer le problème SIP"""
    try:
        # Connexion SSH
        ssh = paramiko.SSHClient()
        ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        
        print("🔌 Connexion au VPS...")
        ssh.connect(
            hostname='188.34.143.144',
            username='root',
            password='Minibot2024!',
            timeout=30
        )
        
        print("✅ Connecté au VPS")
        
        # DIAGNOSTIC ET CORRECTION ASTERISK
        print("\n🔧 Diagnostic Asterisk...")
        
        # 1. Vérifier le statut du service
        print("1️⃣ Statut service Asterisk...")
        stdin, stdout, stderr = ssh.exec_command('systemctl status asterisk.service')
        status = stdout.read().decode()
        print("Status Asterisk:")
        print(status[-800:])
        
        # 2. Vérifier les logs d'erreur
        print("\n2️⃣ Logs d'erreur Asterisk...")
        stdin, stdout, stderr = ssh.exec_command('journalctl -xeu asterisk.service --no-pager -n 20')
        journal_logs = stdout.read().decode()
        print("Journal logs:")
        print(journal_logs[-1000:])
        
        # 3. Tester la configuration
        print("\n3️⃣ Test configuration Asterisk...")
        stdin, stdout, stderr = ssh.exec_command('asterisk -T')
        test_config = stdout.read().decode()
        error_config = stderr.read().decode()
        print("Test config stdout:")
        print(test_config)
        print("Test config stderr:")
        print(error_config)
        
        # 4. Vérifier les permissions
        print("\n4️⃣ Permissions fichiers config...")
        stdin, stdout, stderr = ssh.exec_command('ls -la /etc/asterisk/ | head -10')
        permissions = stdout.read().decode()
        print("Permissions /etc/asterisk/:")
        print(permissions)
        
        # 5. Tenter de démarrer Asterisk manuellement
        print("\n5️⃣ Tentative démarrage manuel...")
        stdin, stdout, stderr = ssh.exec_command('systemctl stop asterisk; sleep 2; systemctl start asterisk; sleep 3; systemctl status asterisk')
        manual_start = stdout.read().decode()
        print("Résultat démarrage manuel:")
        print(manual_start[-800:])
        
        # 6. Si Asterisk démarre, vérifier PJSIP
        print("\n6️⃣ Vérification PJSIP si Asterisk actif...")
        stdin, stdout, stderr = ssh.exec_command('asterisk -rx "pjsip show registrations" 2>/dev/null || echo "Asterisk non accessible"')
        pjsip_status = stdout.read().decode()
        print("Statut PJSIP:")
        print(pjsip_status)
        
        ssh.close()
        
    except Exception as e:
        print(f"❌ Erreur connexion: {e}")

if __name__ == "__main__":
    connect_and_debug()