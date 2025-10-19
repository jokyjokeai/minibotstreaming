#!/bin/bash

# Script d'arrêt du système MiniBotPanel v2

echo "========================================="
echo "  MINIBOT PANEL V2 - ARRÊT"
echo "========================================="

# Trouver et tuer robot_ari.py
echo "⏹️ Arrêt du Robot ARI..."
pkill -f "python3 robot_ari.py" 2>/dev/null
if [ $? -eq 0 ]; then
    echo "✅ Robot ARI arrêté"
else
    echo "ℹ️ Robot ARI n'était pas en cours d'exécution"
fi

# Trouver et tuer batch_caller.py
echo "⏹️ Arrêt du Batch Caller..."
pkill -f "python3 system/batch_caller.py" 2>/dev/null
if [ $? -eq 0 ]; then
    echo "✅ Batch Caller arrêté"
else
    echo "ℹ️ Batch Caller n'était pas en cours d'exécution"
fi

# Trouver et tuer uvicorn
echo "⏹️ Arrêt de FastAPI..."
pkill -f "uvicorn main:app" 2>/dev/null
if [ $? -eq 0 ]; then
    echo "✅ FastAPI arrêté"
else
    echo "ℹ️ FastAPI n'était pas en cours d'exécution"
fi

# Attendre un peu
sleep 2

# Vérifier qu'il ne reste rien
echo ""
echo "🔍 Vérification des processus..."

if pgrep -f "robot_ari.py" > /dev/null; then
    echo "⚠️ Robot ARI encore actif, arrêt forcé..."
    pkill -9 -f "robot_ari.py"
fi

if pgrep -f "system/batch_caller.py" > /dev/null; then
    echo "⚠️ Batch Caller encore actif, arrêt forcé..."
    pkill -9 -f "system/batch_caller.py"
fi

if pgrep -f "uvicorn main:app" > /dev/null; then
    echo "⚠️ FastAPI encore actif, arrêt forcé..."
    pkill -9 -f "uvicorn main:app"
fi

echo ""
echo "✅ Système arrêté avec succès"
echo ""
echo "📋 Pour redémarrer: ./start_system.sh"