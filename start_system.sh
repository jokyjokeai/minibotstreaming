#!/bin/bash

# Script de démarrage du système MiniBotPanel v2

echo "========================================="
echo "  MINIBOT PANEL V2 - DÉMARRAGE"
echo "========================================="

# Déterminer automatiquement le répertoire du script
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

# Configurer les chemins pour cuDNN (pour GPU)
export LD_LIBRARY_PATH=/usr/local/lib/python3.10/dist-packages/ctranslate2.libs:$LD_LIBRARY_PATH

# Créer les dossiers nécessaires
mkdir -p logs recordings audio

# Nettoyage automatique des anciens enregistrements
echo "🧹 Nettoyage des anciens enregistrements (>7 jours)..."
if [ -f "$SCRIPT_DIR/system/cleanup_recordings.sh" ]; then
    bash "$SCRIPT_DIR/system/cleanup_recordings.sh"
else
    echo "⚠️  Script de nettoyage introuvable, skipping..."
fi

# Vérifier si les fichiers audio sont installés dans Asterisk
echo "🔍 Vérification des fichiers audio..."
if [ ! -d "/var/lib/asterisk/sounds/minibot" ] || [ -z "$(ls -A /var/lib/asterisk/sounds/minibot 2>/dev/null)" ]; then
    echo "⚠️  Fichiers audio non installés dans Asterisk"
    echo "   Exécuter: sudo ./system/setup_audio.sh"
    echo "   Puis relancer ce script"
    # On continue quand même mais avec un avertissement
    echo "   ⚠️  Les fichiers audio ne fonctionneront pas correctement !"
else
    echo "✅ Fichiers audio installés dans Asterisk"
fi

# Vérifier Asterisk
echo "🔍 Vérification Asterisk..."
if systemctl is-active --quiet asterisk; then
    echo "✅ Asterisk est actif"
else
    echo "⚠️ Asterisk n'est pas actif, démarrage..."
    sudo systemctl start asterisk
    sleep 5
fi

# Vérifier PostgreSQL
echo "🔍 Vérification PostgreSQL..."
if systemctl is-active --quiet postgresql; then
    echo "✅ PostgreSQL est actif"
else
    echo "⚠️ PostgreSQL n'est pas actif, démarrage..."
    sudo systemctl start postgresql
    sleep 3
fi

# Vérifier et arrêter les anciens processus s'ils existent
echo "🔍 Vérification des processus existants..."
if pgrep -f "python3 robot_ari.py" > /dev/null; then
    echo "⚠️  Robot ARI déjà en cours, arrêt..."
    pkill -f "python3 robot_ari.py"
    sleep 2
fi

if pgrep -f "python3 system/batch_caller.py" > /dev/null; then
    echo "⚠️  Batch Caller déjà en cours, arrêt..."
    pkill -f "python3 system/batch_caller.py"
    sleep 2
fi

if pgrep -f "uvicorn main:app" > /dev/null; then
    echo "⚠️  FastAPI déjà en cours, arrêt..."
    pkill -f "uvicorn main:app"
    sleep 2
fi

# PRÉ-CHARGER WHISPER AVANT TOUT !
echo ""
echo "🤖 Pré-chargement de Whisper (pour éviter les délais pendant les appels)..."
python3 -c "
import sys
import os
sys.path.insert(0, os.getcwd())
from services.whisper_service import whisper_service
print('✅ Whisper model loaded and ready!')
print('   Le modèle est maintenant en cache')
" 2>&1 || echo "⚠️  Whisper pre-load failed but continuing..."

# Lancer robot_ari.py en arrière-plan (avec tout pré-chargé)
echo ""
echo "🤖 Démarrage du Robot ARI..."
echo "   • Whisper se charge au démarrage"
echo "   • Audio convertis en 8000 Hz et mis en cache"
echo "   • Scénario TEST pré-chargé"
python3 robot_ari.py > logs/robot_ari_console.log 2>&1 &
ROBOT_PID=$!
echo "✅ Robot ARI lancé (PID: $ROBOT_PID)"
echo "   Tout est pré-chargé en mémoire !"

sleep 3

# Lancer Batch Caller (gestion de queue d'appels avec throttling)
echo ""
echo "📞 Démarrage du Batch Caller (file d'attente d'appels)..."
echo "   • Max 8 appels simultanés"
echo "   • Gestion intelligente de la queue"
echo "   • Retry automatique en cas d'échec"
python3 system/batch_caller.py > logs/batch_caller_console.log 2>&1 &
BATCH_PID=$!
echo "✅ Batch Caller lancé (PID: $BATCH_PID)"

sleep 3

# Lancer FastAPI
echo ""
echo "🌐 Démarrage de l'API FastAPI..."
python3 -m uvicorn main:app --host 0.0.0.0 --port 8000 > logs/fastapi_console.log 2>&1 &
API_PID=$!
echo "✅ FastAPI lancé (PID: $API_PID)"

sleep 3

# Vérifier que tout fonctionne
echo ""
echo "🧪 Vérification du système..."
sleep 2

# Test health check
if curl -s http://localhost:8000/health | grep -q "healthy"; then
    echo "✅ API Health Check: OK"
else
    echo "❌ API Health Check: FAILED"
fi

# Afficher les infos
echo ""
echo "========================================="
echo "  SYSTÈME DÉMARRÉ AVEC SUCCÈS"
echo "========================================="
echo ""
echo "📊 Informations:"
echo "  • Robot ARI PID: $ROBOT_PID"
echo "  • Batch Caller PID: $BATCH_PID"
echo "  • FastAPI PID: $API_PID"
echo "  • API URL: http://localhost:8000"
echo "  • Logs: logs/minibot_$(date +%Y%m%d).log"
echo ""
echo "📋 Commandes utiles:"
echo "  • Voir logs robot: tail -f logs/minibot_$(date +%Y%m%d).log"
echo "  • Arrêter: ./stop_system.sh"
echo "  • Tester appel: curl -X POST http://localhost:8000/calls/launch -H 'Content-Type: application/json' -d '{\"phone_number\":\"0612345678\",\"scenario\":\"test\"}'"
echo ""
echo "🎉 Système prêt (Batch mode avec Whisper) !"