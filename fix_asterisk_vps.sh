#!/bin/bash
# Script de correction Asterisk pour VPS
# À exécuter directement sur le VPS en tant que root

echo "🔧 DIAGNOSTIC ET CORRECTION ASTERISK"
echo "=================================="

echo "1️⃣ Statut actuel Asterisk..."
systemctl status asterisk.service --no-pager -l

echo -e "\n2️⃣ Logs d'erreur récents..."
journalctl -xeu asterisk.service --no-pager -n 20

echo -e "\n3️⃣ Test de configuration..."
asterisk -T

echo -e "\n4️⃣ Vérification permissions..."
ls -la /etc/asterisk/ | head -5

echo -e "\n5️⃣ Arrêt propre et redémarrage..."
systemctl stop asterisk
sleep 3

echo "   Nettoyage des processus zombies..."
pkill -f asterisk 2>/dev/null || true
sleep 2

echo "   Vérification des ports..."
netstat -tlnp | grep 5060

echo "   Redémarrage Asterisk..."
systemctl start asterisk
sleep 5

echo -e "\n6️⃣ Statut après redémarrage..."
systemctl status asterisk.service --no-pager -l

echo -e "\n7️⃣ Test PJSIP si Asterisk fonctionne..."
if systemctl is-active --quiet asterisk; then
    echo "✅ Asterisk actif, test PJSIP..."
    asterisk -rx "pjsip show registrations"
    echo -e "\nEndpoints PJSIP:"
    asterisk -rx "pjsip show endpoints"
else
    echo "❌ Asterisk toujours inactif"
    echo "Logs détaillés:"
    tail -20 /var/log/asterisk/messages
fi

echo -e "\n8️⃣ Vérification finale services..."
echo "PostgreSQL:" $(systemctl is-active postgresql)
echo "Asterisk:" $(systemctl is-active asterisk)
echo "Ports en écoute:"
netstat -tlnp | grep -E "(5060|5432|8000|11434)"

echo -e "\n🎉 Diagnostic terminé!"