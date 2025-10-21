#!/usr/bin/env python3
"""
Diagnostic réseau pour problème PJSIP Unregistered
"""
import paramiko
import time
import sys

def network_diagnostics():
    """Diagnostics réseau complets"""
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
        
        # 1. Test connectivité réseau de base
        print("\n🌐 Test connectivité réseau...")
        stdin, stdout, stderr = ssh.exec_command('ping -c 3 8.8.8.8')
        ping_result = stdout.read().decode()
        print("Ping Google DNS:")
        print(ping_result)
        
        # 2. Vérifier firewall/iptables
        print("\n🔥 Vérification firewall...")
        stdin, stdout, stderr = ssh.exec_command('iptables -L -n | grep 5060')
        firewall_sip = stdout.read().decode()
        print("Règles firewall SIP (5060):")
        print(firewall_sip or "Aucune règle trouvée")
        
        # 3. Test port SIP avec telnet
        print("\n📞 Test connectivité SIP...")
        stdin, stdout, stderr = ssh.exec_command('timeout 5 telnet 188.34.143.144 5060')
        telnet_result = stdout.read().decode()
        print("Test telnet vers 188.34.143.144:5060:")
        print(telnet_result or "Pas de réponse")
        
        # 4. Vérifier interface réseau
        print("\n🌍 Configuration réseau...")
        stdin, stdout, stderr = ssh.exec_command('ip addr show')
        ip_config = stdout.read().decode()
        print("Configuration IP:")
        print(ip_config[-500:])  # Dernières 500 chars
        
        # 5. Test DNS
        print("\n🔍 Test résolution DNS...")
        stdin, stdout, stderr = ssh.exec_command('nslookup gateway.bitcall.io')
        dns_result = stdout.read().decode()
        print("Résolution gateway.bitcall.io:")
        print(dns_result)
        
        # 6. Vérifier NAT/routing
        print("\n🛣️ Table de routage...")
        stdin, stdout, stderr = ssh.exec_command('route -n')
        route_table = stdout.read().decode()
        print("Table de routage:")
        print(route_table)
        
        # 7. Logs système réseau
        print("\n📋 Logs réseau récents...")
        stdin, stdout, stderr = ssh.exec_command('dmesg | tail -10 | grep -i network')
        network_logs = stdout.read().decode()
        print("Logs réseau:")
        print(network_logs or "Aucun log réseau récent")
        
        # 8. Processus Asterisk réseau
        print("\n🔌 Connexions réseau Asterisk...")
        stdin, stdout, stderr = ssh.exec_command('netstat -tlnp | grep 5060')
        asterisk_network = stdout.read().decode()
        print("Asterisk écoute sur port 5060:")
        print(asterisk_network or "Asterisk n'écoute pas sur 5060!")
        
        ssh.close()
        
    except Exception as e:
        print(f"❌ Erreur connexion: {e}")

if __name__ == "__main__":
    network_diagnostics()