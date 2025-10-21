#!/bin/bash
# Script de sécurité SIP pour MiniBotPanel v2
# Bloque les attaques SIP automatiquement

echo "🔐 SIP Security Script - MiniBotPanel v2"
echo "========================================"

# IP attaquante identifiée
ATTACK_IP="77.110.109.104"

echo "🚫 Blocage de l'IP attaquante: $ATTACK_IP"

# Bloquer avec UFW si disponible
if command -v ufw >/dev/null 2>&1; then
    echo "   → Utilisation d'UFW"
    sudo ufw deny from $ATTACK_IP
    sudo ufw reload
else
    # Fallback avec iptables
    echo "   → Utilisation d'iptables"
    sudo iptables -I INPUT -s $ATTACK_IP -j DROP
fi

echo "🔍 Vérification des connexions SIP actives..."
sudo netstat -tuln | grep :5060

echo "📊 Analyse des logs Asterisk récents..."
sudo tail -50 /var/log/asterisk/messages | grep "REGISTER" | tail -10

echo "🔄 Redémarrage des services Asterisk..."
sudo systemctl stop asterisk
sleep 3
sudo systemctl start asterisk
sleep 5

echo "✅ Vérification du statut Asterisk..."
sudo systemctl status asterisk --no-pager -l

echo "🔍 Test PJSIP endpoints..."
sudo asterisk -rx "pjsip show endpoints"

echo "🔐 Sécurité SIP appliquée"