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
            password='Minibot2024!'
        )
        
        print("✅ Connecté au VPS")
        
        # Vérifier les logs Asterisk
        print("\n📋 Vérification logs Asterisk...")
        stdin, stdout, stderr = ssh.exec_command('tail -20 /var/log/asterisk/messages')
        logs = stdout.read().decode()
        print("Logs Asterisk:")
        print(logs)
        
        # Vérifier la config PJSIP
        print("\n📋 Vérification config PJSIP...")
        stdin, stdout, stderr = ssh.exec_command('asterisk -rx "pjsip show endpoints"')
        endpoints = stdout.read().decode()
        print("Endpoints PJSIP:")
        print(endpoints)
        
        # Vérifier les registrations
        print("\n📋 Statut registrations...")
        stdin, stdout, stderr = ssh.exec_command('asterisk -rx "pjsip show registrations"')
        registrations = stdout.read().decode()
        print("Registrations:")
        print(registrations)
        
        # Vérifier auth
        print("\n📋 Auth outbounds...")
        stdin, stdout, stderr = ssh.exec_command('asterisk -rx "pjsip show auths"')
        auths = stdout.read().decode()
        print("Auths:")
        print(auths)
        
        # Vérifier le fichier de config
        print("\n📋 Contenu pjsip.conf...")
        stdin, stdout, stderr = ssh.exec_command('cat /etc/asterisk/pjsip.conf')
        pjsip_conf = stdout.read().decode()
        print("pjsip.conf:")
        print(pjsip_conf[-1000:])  # Derniers 1000 caractères
        
        ssh.close()
        
    except Exception as e:
        print(f"❌ Erreur connexion: {e}")

if __name__ == "__main__":
    connect_and_debug()