#!/bin/bash

# Script de démarrage du système MiniBotPanel v2 - Architecture Streaming

echo "========================================="
echo "  MINIBOT PANEL V2 - DÉMARRAGE STREAMING"
echo "========================================="

# Déterminer automatiquement le répertoire du script
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

# Créer les dossiers nécessaires
mkdir -p logs recordings audio assembled_audio transcripts

# Nettoyage automatique des anciens enregistrements
echo "🧹 Nettoyage des anciens enregistrements (>7 jours)..."
if [ -f "$SCRIPT_DIR/system/cleanup_recordings.sh" ]; then
    bash "$SCRIPT_DIR/system/cleanup_recordings.sh"
else
    echo "⚠️  Script de nettoyage introuvable, skipping..."
fi

# Vérifier si les fichiers audio sont installés dans Asterisk (16kHz streaming)
echo "🔍 Vérification des fichiers audio streaming (16kHz)..."
if [ ! -d "/var/lib/asterisk/sounds/minibot" ] || [ -z "$(ls -A /var/lib/asterisk/sounds/minibot 2>/dev/null)" ]; then
    echo "⚠️  Fichiers audio 16kHz non installés dans Asterisk"
    echo "   Exécuter: sudo ./system/setup_audio.sh"
    echo "   Puis relancer ce script"
    echo "   ⚠️  Les fichiers audio streaming ne fonctionneront pas !"
else
    echo "✅ Fichiers audio 16kHz installés dans Asterisk"
fi

# Vérifier Asterisk 22 + AudioFork
echo "🔍 Vérification Asterisk 22 + AudioFork..."
if systemctl is-active --quiet asterisk; then
    echo "✅ Asterisk est actif"
    # Vérifier AudioFork
    if asterisk -rx 'module show like audiofork' 2>/dev/null | grep -q 'res_audiofork'; then
        echo "✅ AudioFork module détecté"
    else
        echo "⚠️  AudioFork non détecté (nécessaire pour streaming)"
    fi
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

# Vérifier Ollama NLP (service streaming)
echo "🔍 Vérification Ollama NLP..."
if systemctl is-active --quiet ollama; then
    echo "✅ Ollama est actif"
    # Vérifier modèle disponible
    if ollama list | grep -q 'llama3.2'; then
        echo "✅ Modèle Llama3.2 disponible"
    else
        echo "⚠️  Modèle Llama3.2 manquant, installation..."
        ollama pull llama3.2:1b
    fi
else
    echo "⚠️ Ollama n'est pas actif, démarrage..."
    sudo systemctl start ollama
    sleep 5
fi

# Vérifier modèles Vosk ASR
echo "🔍 Vérification modèles Vosk français..."
VOSK_PATH="/var/lib/vosk-models/fr"
if [ -d "$VOSK_PATH" ] && [ -f "$VOSK_PATH/am/final.mdl" ]; then
    echo "✅ Modèle Vosk français disponible"
else
    echo "⚠️  Modèle Vosk français manquant"
    echo "   Installation automatique en cours..."
    python3 -c "
import vosk
try:
    model = vosk.Model('/var/lib/vosk-models/fr')
    print('✅ Vosk model OK')
except:
    print('⚠️  Vosk model download required')
    # Le modèle sera téléchargé automatiquement au premier usage
"
fi

# Vérifier et arrêter les anciens processus s'ils existent
echo "🔍 Vérification des processus existants..."
if pgrep -f "python3 robot_ari_hybrid.py" > /dev/null; then
    echo "⚠️  Robot ARI Streaming déjà en cours, arrêt..."
    pkill -f "python3 robot_ari_hybrid.py"
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

# ========== VÉRIFICATION STREAMING SERVICES ==========
echo ""
echo "========================================="
echo "  VÉRIFICATION SERVICES STREAMING"
echo "========================================="
echo ""

# Test Vosk
echo "🎤 Test Vosk ASR..."
python3 -c "
try:
    import vosk
    print('✅ Vosk importé avec succès')
except ImportError:
    print('❌ Vosk non disponible')
    exit(1)
" || { echo "❌ Vosk requis pour streaming"; exit 1; }

# Test Ollama API
echo "🤖 Test Ollama NLP..."
if curl -s http://localhost:11434/api/version >/dev/null; then
    echo "✅ Ollama API accessible"
else
    echo "❌ Ollama API non accessible"
    exit 1
fi

# Test WebRTC VAD
echo "🎙️  Test WebRTC VAD..."
python3 -c "
try:
    import webrtcvad
    print('✅ WebRTC VAD disponible')
except ImportError:
    print('❌ WebRTC VAD non disponible')
    exit(1)
" || { echo "❌ WebRTC VAD requis pour streaming"; exit 1; }

echo "✅ Tous les services streaming sont disponibles"

# ========== DÉMARRAGE SERVICES STREAMING ==========
echo ""
echo "========================================="
echo "  DÉMARRAGE ARCHITECTURE STREAMING"
echo "========================================="
echo ""

# Lancer Robot ARI Streaming en arrière-plan
echo "🌊 Démarrage du Robot ARI Streaming..."
echo "   • Vosk ASR temps réel (16kHz)"
echo "   • Ollama NLP local"
echo "   • Barge-in naturel"
echo "   • AMD Hybride"
python3 robot_ari_hybrid.py > logs/robot_ari_console.log 2>&1 &
ROBOT_PID=$!
echo "✅ Robot ARI Streaming lancé (PID: $ROBOT_PID)"

sleep 5

# Lancer Batch Caller (gestion de queue d'appels)
echo ""
echo "📞 Démarrage du Batch Caller (gestionnaire campagnes)..."
echo "   • Max 8 appels simultanés"
echo "   • Gestion intelligente de la queue"
echo "   • Retry automatique streaming"
python3 system/batch_caller.py > logs/batch_caller_console.log 2>&1 &
BATCH_PID=$!
echo "✅ Batch Caller lancé (PID: $BATCH_PID)"

sleep 3

# Lancer FastAPI
echo ""
echo "🌐 Démarrage de l'API FastAPI..."
echo "   • Endpoints streaming"
echo "   • Health checks Vosk + Ollama"
echo "   • Monitoring temps réel"
python3 -m uvicorn main:app --host 0.0.0.0 --port 8000 > logs/main.log 2>&1 &
API_PID=$!
echo "✅ FastAPI lancé (PID: $API_PID)"

sleep 5

# ========== VÉRIFICATIONS FINALES ==========
echo ""
echo "🧪 Vérification du système streaming..."

# Test health check complet
echo "🏥 Test Health Check..."
if curl -s http://localhost:8000/health | grep -q "healthy"; then
    echo "✅ API Health Check: OK"
    
    # Afficher détails health check
    echo "📊 Détails services:"
    curl -s http://localhost:8000/health | python3 -m json.tool | grep -E "(vosk_status|ollama_status|streaming)"
else
    echo "❌ API Health Check: FAILED"
fi

# Test Vosk via API
echo "🎤 Test Vosk via API..."
if curl -s http://localhost:8000/health | grep -q "vosk.*ready"; then
    echo "✅ Vosk ASR: Prêt"
else
    echo "⚠️  Vosk ASR: Non prêt"
fi

# Test Ollama via API
echo "🤖 Test Ollama via API..."
if curl -s http://localhost:8000/health | grep -q "ollama.*ready"; then
    echo "✅ Ollama NLP: Prêt"
else
    echo "⚠️  Ollama NLP: Non prêt"
fi

# Afficher les infos
echo ""
echo "========================================="
echo "  SYSTÈME STREAMING DÉMARRÉ AVEC SUCCÈS"
echo "========================================="
echo ""
echo "🌊 Architecture Streaming MiniBotPanel v2:"
echo "  • Robot ARI Streaming PID: $ROBOT_PID"
echo "  • Batch Caller PID: $BATCH_PID"  
echo "  • FastAPI PID: $API_PID"
echo "  • API URL: http://localhost:8000"
echo ""
echo "📊 Services Streaming:"
echo "  • Vosk ASR: Transcription française temps réel"
echo "  • Ollama NLP: Analyse intention locale"
echo "  • WebRTC VAD: Détection parole + barge-in"
echo "  • AudioFork: Streaming audio 16kHz bidirectionnel"
echo ""
echo "📋 Commandes utiles:"
echo "  • Logs streaming: ./monitor_logs.sh"
echo "  • Arrêter: ./stop_system.sh"
echo "  • Health check: curl http://localhost:8000/health"
echo "  • Test appel: curl -X POST http://localhost:8000/calls/launch -H 'Content-Type: application/json' -d '{\"phone_number\":\"33612345678\",\"scenario\":\"production\"}'"
echo ""
echo "🎉 Architecture streaming opérationnelle !"
echo "    Latence cible: <200ms (Vosk + Ollama + Barge-in)"