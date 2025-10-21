#!/bin/bash
# Script de diagnostic PJSIP pour MiniBotPanel v2
# Identifie pourquoi aucun endpoint n'est chargé

echo "🔍 DIAGNOSTIC PJSIP - MiniBotPanel v2"
echo "===================================="

echo "1. 📁 Vérification fichiers de configuration..."
echo "----------------------------------------------"
ls -la /etc/asterisk/pjsip*.conf 2>/dev/null || echo "❌ Aucun fichier pjsip*.conf trouvé"

echo ""
echo "2. 📋 Contenu pjsip.conf (premières lignes)..."
echo "-----------------------------------------------"
if [ -f "/etc/asterisk/pjsip.conf" ]; then
    head -20 /etc/asterisk/pjsip.conf
else
    echo "❌ /etc/asterisk/pjsip.conf n'existe pas"
fi

echo ""
echo "3. 🔧 Modules PJSIP chargés..."
echo "------------------------------"
asterisk -rx "module show like pjsip" 2>/dev/null || echo "❌ Impossible de se connecter à Asterisk"

echo ""
echo "4. 🎯 Endpoints PJSIP..."
echo "------------------------"
asterisk -rx "pjsip show endpoints" 2>/dev/null || echo "❌ Erreur lecture endpoints"

echo ""
echo "5. 📞 Registrations PJSIP..."
echo "-----------------------------"
asterisk -rx "pjsip show registrations" 2>/dev/null || echo "❌ Erreur lecture registrations"

echo ""
echo "6. 🚀 Transport PJSIP..."
echo "-------------------------"
asterisk -rx "pjsip show transports" 2>/dev/null || echo "❌ Erreur lecture transports"

echo ""
echo "7. 📄 Configuration reload test..."
echo "----------------------------------"
asterisk -rx "module reload res_pjsip.so" 2>/dev/null || echo "❌ Erreur reload PJSIP"
sleep 2
asterisk -rx "pjsip show endpoints" 2>/dev/null || echo "❌ Toujours aucun endpoint après reload"

echo ""
echo "8. 🗂️ Permissions fichiers..."
echo "-----------------------------"
ls -la /etc/asterisk/pjsip.conf 2>/dev/null || echo "❌ Fichier pjsip.conf inaccessible"

echo ""
echo "9. 📊 Status processus Asterisk..."
echo "----------------------------------"
ps aux | grep asterisk | grep -v grep || echo "❌ Asterisk ne semble pas tourner"

echo ""
echo "10. 📝 Logs Asterisk récents (erreurs PJSIP)..."
echo "-----------------------------------------------"
tail -50 /var/log/asterisk/messages | grep -i pjsip | tail -10 || echo "❌ Pas de logs PJSIP récents"

echo ""
echo "🔚 Diagnostic terminé"