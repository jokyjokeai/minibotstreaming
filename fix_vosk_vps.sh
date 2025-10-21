#!/bin/bash
# Script de correction Vosk pour VPS
echo "🎤 DIAGNOSTIC ET CORRECTION VOSK"
echo "================================"

echo "1️⃣ Vérification modèles Vosk..."
echo "Contenu /opt/minibot/models/:"
ls -la /opt/minibot/models/ 2>/dev/null || echo "❌ Répertoire models manquant"

echo -e "\nContenu /var/lib/vosk-models/:"
ls -la /var/lib/vosk-models/ 2>/dev/null || echo "❌ Répertoire vosk-models manquant"

echo -e "\nLien symbolique vosk-fr:"
ls -la /opt/minibot/models/vosk-fr 2>/dev/null || echo "❌ Lien vosk-fr manquant"

echo -e "\n2️⃣ Test modèle Vosk français..."
if [ -d "/opt/minibot/models/vosk-fr" ]; then
    echo "✅ Modèle vosk-fr trouvé"
    echo "Contenu du modèle:"
    ls -la /opt/minibot/models/vosk-fr/ | head -10
else
    echo "❌ Modèle vosk-fr manquant, création du lien..."
    mkdir -p /opt/minibot/models
    if [ -d "/var/lib/vosk-models/vosk-fr-small" ]; then
        ln -sf /var/lib/vosk-models/vosk-fr-small /opt/minibot/models/vosk-fr
        echo "✅ Lien vosk-fr créé"
    else
        echo "❌ vosk-fr-small manquant aussi"
    fi
fi

echo -e "\n3️⃣ Téléchargement si manquant..."
if [ ! -d "/var/lib/vosk-models/vosk-fr-small" ]; then
    echo "Téléchargement modèle Vosk français..."
    mkdir -p /var/lib/vosk-models
    cd /tmp
    wget -O vosk-fr-small.zip "https://storage.googleapis.com/linagora-ai/models/vosk-fr-small.zip" || \
    wget -O vosk-fr-small.zip "https://alphacephei.com/vosk/models/vosk-model-fr-0.22-linto-2.2.zip"
    
    if [ -f "vosk-fr-small.zip" ]; then
        unzip -q vosk-fr-small.zip
        mv vosk-model-* /var/lib/vosk-models/vosk-fr-small 2>/dev/null || \
        mv vosk-* /var/lib/vosk-models/vosk-fr-small 2>/dev/null
        rm -f vosk-fr-small.zip
        echo "✅ Modèle téléchargé"
    else
        echo "❌ Échec téléchargement"
    fi
fi

echo -e "\n4️⃣ Correction des permissions..."
chown -R root:root /var/lib/vosk-models/ 2>/dev/null
chown -R root:root /opt/minibot/models/ 2>/dev/null
chmod -R 755 /var/lib/vosk-models/ 2>/dev/null
chmod -R 755 /opt/minibot/models/ 2>/dev/null

echo -e "\n5️⃣ Recréation lien symbolique..."
rm -f /opt/minibot/models/vosk-fr
ln -sf /var/lib/vosk-models/vosk-fr-small /opt/minibot/models/vosk-fr

echo -e "\n6️⃣ Vérification finale..."
if [ -f "/opt/minibot/models/vosk-fr/conf/model.conf" ]; then
    echo "✅ Modèle Vosk opérationnel"
    echo "Config modèle:"
    head -5 /opt/minibot/models/vosk-fr/conf/model.conf
else
    echo "❌ Modèle toujours non opérationnel"
fi

echo -e "\n7️⃣ Test API Vosk..."
curl -X POST http://localhost:8000/test/vosk -H 'Content-Type: application/json' -d '{"text":"bonjour"}' 2>/dev/null || echo "❌ API Vosk non accessible"

echo -e "\n🎉 Diagnostic Vosk terminé!"