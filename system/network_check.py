#!/usr/bin/env python3
"""
Test de connectivité réseau au VPS
"""

import socket
import sys

def check_port(host, port, timeout=5):
    """Test si un port est ouvert"""
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(timeout)
        result = sock.connect_ex((host, port))
        sock.close()
        return result == 0
    except Exception as e:
        print(f"❌ Erreur test port {port}: {e}")
        return False

def main():
    host = "94.103.0.38"
    
    print(f"🔍 Test de connectivité vers {host}")
    print("=" * 50)
    
    # Ports courants à tester
    ports = [22, 2222, 5060, 8088, 8000, 80, 443]
    
    for port in ports:
        is_open = check_port(host, port)
        status = "✅ OUVERT" if is_open else "❌ FERMÉ"
        service = {22: "SSH", 2222: "SSH alt", 5060: "SIP", 8088: "ARI", 8000: "API", 80: "HTTP", 443: "HTTPS"}.get(port, "")
        print(f"Port {port:4d} ({service:8s}): {status}")

if __name__ == "__main__":
    main()