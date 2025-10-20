#!/bin/bash
# Script pour restaurer l'ancien dialplan (sans Wait(4) AMD)

echo "🔄 Restauration de l'ancien dialplan"

# Restaurer le backup d'avant update_amd.sh
sudo cp /etc/asterisk/extensions.conf.backup_20251020_091620 /etc/asterisk/extensions.conf

echo "✅ Fichier restauré"

# Reload Asterisk
sudo asterisk -rx "dialplan reload"
echo "✅ Dialplan rechargé"

echo ""
echo "📊 Vérification:"
sudo asterisk -rx "dialplan show outbound-robot" | grep -E "AMD|Wait"
