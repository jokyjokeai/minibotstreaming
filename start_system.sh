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

# ========== MENU INTERACTIF CPU/GPU + MODÈLE WHISPER ==========
echo ""
echo "========================================="
echo "  CONFIGURATION WHISPER"
echo "========================================="
echo ""

# Lire config actuelle depuis .env
CURRENT_DEVICE=$(grep "^WHISPER_DEVICE=" .env 2>/dev/null | cut -d '=' -f2)
CURRENT_MODEL=$(grep "^WHISPER_MODEL=" .env 2>/dev/null | cut -d '=' -f2)

echo "📊 Configuration actuelle:"
echo "   Device: ${CURRENT_DEVICE:-non défini}"
echo "   Modèle: ${CURRENT_MODEL:-non défini}"
echo ""

# Menu Device (CPU/GPU)
echo "💻 Choisissez le mode de transcription:"
echo "  1. CPU (compatible partout, plus lent: ~3-5s)"
echo "  2. GPU (RTX 4090, très rapide: ~0.5-1s)"
echo ""
read -p "Votre choix [1-CPU/2-GPU, défaut=actuel]: " device_choice

if [ "$device_choice" = "1" ]; then
    WHISPER_DEVICE="cpu"
    WHISPER_COMPUTE_TYPE="int8"
    echo "✅ Mode CPU sélectionné"
elif [ "$device_choice" = "2" ]; then
    # Vérifier que GPU est disponible
    if python3 -c "import torch; exit(0 if torch.cuda.is_available() else 1)" 2>/dev/null; then
        WHISPER_DEVICE="cuda"
        WHISPER_COMPUTE_TYPE="float16"
        echo "✅ Mode GPU sélectionné"
    else
        echo "⚠️  GPU non détecté, utilisation CPU par défaut"
        WHISPER_DEVICE="cpu"
        WHISPER_COMPUTE_TYPE="int8"
    fi
else
    # Garder config actuelle si pas de choix
    WHISPER_DEVICE="${CURRENT_DEVICE:-cpu}"
    WHISPER_COMPUTE_TYPE=$(grep "^WHISPER_COMPUTE_TYPE=" .env 2>/dev/null | cut -d '=' -f2)
    WHISPER_COMPUTE_TYPE="${WHISPER_COMPUTE_TYPE:-int8}"
    echo "ℹ️  Configuration actuelle conservée: ${WHISPER_DEVICE}"
fi

echo ""

# Menu Modèle Whisper
echo "🤖 Choisissez le modèle Whisper:"
echo "  1. tiny   - Le plus rapide, moins précis (~75MB)"
echo "  2. base   - Équilibre vitesse/précision (~150MB)"
echo "  3. small  - Plus précis, plus lent (~500MB) [RECOMMANDÉ GPU]"
echo "  4. medium - Très précis, lent (~1.5GB)"
echo "  5. large  - Meilleure précision, très lent (~3GB)"
echo ""

# Vérifier modèles déjà téléchargés
CACHE_DIR="${HOME}/.cache/huggingface/hub"
DOWNLOADED=""
for model in tiny base small medium large; do
    if [ -d "${CACHE_DIR}/models--Systran--faster-whisper-${model}" ] || \
       [ -d "${CACHE_DIR}/models--openai--whisper-${model}" ]; then
        DOWNLOADED="${DOWNLOADED}${model}, "
    fi
done
if [ -n "$DOWNLOADED" ]; then
    echo "💾 Modèles déjà téléchargés : ${DOWNLOADED%, }"
    echo ""
fi

read -p "Votre choix [1/2/3/4/5, défaut=actuel]: " model_choice

case "$model_choice" in
    1) WHISPER_MODEL="tiny" ;;
    2) WHISPER_MODEL="base" ;;
    3) WHISPER_MODEL="small" ;;
    4) WHISPER_MODEL="medium" ;;
    5) WHISPER_MODEL="large" ;;
    *) WHISPER_MODEL="${CURRENT_MODEL:-small}"
       echo "ℹ️  Modèle actuel conservé: ${WHISPER_MODEL}" ;;
esac

if [ "$model_choice" -ge 1 ] && [ "$model_choice" -le 5 ]; then
    echo "✅ Modèle ${WHISPER_MODEL} sélectionné"
fi

echo ""

# Mettre à jour .env avec les nouveaux paramètres
sed -i "s/^WHISPER_DEVICE=.*/WHISPER_DEVICE=${WHISPER_DEVICE}/" .env
sed -i "s/^WHISPER_COMPUTE_TYPE=.*/WHISPER_COMPUTE_TYPE=${WHISPER_COMPUTE_TYPE}/" .env
sed -i "s/^WHISPER_MODEL=.*/WHISPER_MODEL=${WHISPER_MODEL}/" .env

echo "📝 Fichier .env mis à jour:"
echo "   WHISPER_DEVICE=${WHISPER_DEVICE}"
echo "   WHISPER_COMPUTE_TYPE=${WHISPER_COMPUTE_TYPE}"
echo "   WHISPER_MODEL=${WHISPER_MODEL}"
echo ""

# PRÉ-CHARGER WHISPER AVANT TOUT !
echo "🤖 Pré-chargement de Whisper (pour éviter les délais pendant les appels)..."
echo "   Modèle: ${WHISPER_MODEL} sur ${WHISPER_DEVICE}"
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