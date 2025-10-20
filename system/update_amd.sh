#!/bin/bash
# Script pour mettre à jour extensions.conf avec AMD optimisé

echo "🔧 Mise à jour AMD dans extensions.conf"

# Backup
sudo cp /etc/asterisk/extensions.conf /etc/asterisk/extensions.conf.backup_$(date +%Y%m%d_%H%M%S)
echo "✅ Backup créé"

# Copier nouveau fichier
sudo cp /tmp/extensions_amd_optimized.conf /etc/asterisk/extensions.conf
echo "✅ Fichier mis à jour"

# Reload Asterisk
sudo asterisk -rx "dialplan reload"
echo "✅ Dialplan rechargé"

echo ""
echo "📊 Vérification:"
sudo asterisk -rx "dialplan show outbound-robot"
