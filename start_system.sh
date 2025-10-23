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

# Vérifier et démarrer Asterisk 22 + AudioFork (méthode robuste)
echo "🔍 Vérification Asterisk 22 + AudioFork..."
if systemctl is-active --quiet asterisk; then
    echo "✅ Asterisk est actif"
    # Vérifier modules streaming (AudioFork ou équivalents)
    if asterisk -rx 'module show like stasis' 2>/dev/null | grep -q 'res_stasis'; then
        echo "✅ Modules streaming (Stasis) détectés"
        # Vérifier spécifiquement les modules pour streaming audio
        if asterisk -rx 'module show like snoop' 2>/dev/null | grep -q 'res_stasis_snoop'; then
            echo "✅ Module snoop audio détecté"
        else
            echo "⚠️  Module snoop audio non détecté"
        fi
    else
        echo "⚠️  Modules streaming non détectés"
    fi
else
    echo "⚠️ Asterisk n'est pas actif, démarrage robuste..."
    
    # Méthode robuste de démarrage Asterisk
    echo "🧹 Nettoyage processus Asterisk existants..."
    sudo systemctl stop asterisk 2>/dev/null || true
    sudo pkill -f asterisk 2>/dev/null || true
    sleep 3
    
    echo "🔒 Nettoyage fichiers de lock..."
    sudo rm -f /var/run/asterisk/asterisk.ctl 2>/dev/null || true
    sudo rm -f /var/run/asterisk/asterisk.pid 2>/dev/null || true
    
    echo "📋 Correction permissions configurations..."
    sudo chown asterisk:asterisk /etc/asterisk/pjsip.conf 2>/dev/null || true
    sudo chown asterisk:asterisk /etc/asterisk/asterisk.conf 2>/dev/null || true
    sudo chmod 644 /etc/asterisk/pjsip.conf 2>/dev/null || true
    sudo chmod 644 /etc/asterisk/asterisk.conf 2>/dev/null || true
    
    echo "📁 Correction permissions répertoires..."
    for dir in "/var/run/asterisk" "/var/lib/asterisk" "/var/log/asterisk" "/var/spool/asterisk"; do
        sudo mkdir -p "$dir" 2>/dev/null || true
        sudo chown -R asterisk:asterisk "$dir" 2>/dev/null || true
        sudo chmod 755 "$dir" 2>/dev/null || true
    done
    
    echo "🎯 Démarrage Asterisk avec retry..."
    max_attempts=3
    for attempt in $(seq 1 $max_attempts); do
        echo "   Tentative $attempt/$max_attempts"
        
        sudo systemctl start asterisk
        sleep 5
        
        if systemctl is-active --quiet asterisk; then
            echo "✅ Asterisk démarré avec succès (tentative $attempt)"
            break
        elif [ $attempt -eq $max_attempts ]; then
            echo "❌ Échec démarrage Asterisk après $max_attempts tentatives"
            echo "   Vérifiez: sudo journalctl -u asterisk"
        else
            echo "⚠️  Tentative $attempt échouée, retry..."
            sudo systemctl stop asterisk 2>/dev/null || true
            sleep 2
        fi
    done
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
VOSK_PATH="/opt/minibot/models/vosk-fr"
VOSK_REAL_PATH="/var/lib/vosk-models/vosk-fr-small"

if [ -d "$VOSK_PATH" ] && [ -f "$VOSK_PATH/conf/model.conf" ]; then
    echo "✅ Modèle Vosk français disponible"
elif [ -d "$VOSK_REAL_PATH" ]; then
    echo "🔗 Recréation du lien symbolique Vosk..."
    sudo mkdir -p /opt/minibot/models
    sudo ln -sf "$VOSK_REAL_PATH" "$VOSK_PATH"
    echo "✅ Lien Vosk recréé"
else
    echo "⚠️  Modèle Vosk français manquant"
    echo "   Téléchargement automatique en cours..."
    
    # Télécharger le modèle s'il n'existe pas
    sudo mkdir -p /var/lib/vosk-models
    cd /tmp
    wget -q -O vosk-fr-small.zip "https://alphacephei.com/vosk/models/vosk-model-fr-0.22-linto-2.2.zip" || \
    wget -q -O vosk-fr-small.zip "https://storage.googleapis.com/linagora-ai/models/vosk-fr-small.zip"
    
    if [ -f "vosk-fr-small.zip" ]; then
        sudo unzip -q vosk-fr-small.zip
        sudo mv vosk-model-* "$VOSK_REAL_PATH" 2>/dev/null || sudo mv vosk-* "$VOSK_REAL_PATH" 2>/dev/null
        sudo chown -R root:root "$VOSK_REAL_PATH"
        sudo chmod -R 755 "$VOSK_REAL_PATH"
        
        # Créer le lien symbolique
        sudo mkdir -p /opt/minibot/models
        sudo ln -sf "$VOSK_REAL_PATH" "$VOSK_PATH"
        
        rm -f vosk-fr-small.zip
        echo "✅ Modèle Vosk téléchargé et installé"
    else
        echo "❌ Échec téléchargement modèle Vosk"
    fi
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

# ========== PRÉCHARGEMENT HEAVY LIFTING OPTIMISÉ ==========
echo ""
echo "========================================="
echo "  PRÉCHARGEMENT OPTIMISÉ (PARALLEL)"
echo "========================================="
echo ""

# Préchargement parallèle de tous les modèles avec optimisations
python3 << 'EOF'
import os
import sys
import time
import threading
import subprocess
import requests
import json

print("⚡ OPTIMISEUR PIPELINE MiniBotPanel v2")
print("=" * 60)

# 1️⃣ Variables d'environnement optimales
optimizations = {
    "OMP_NUM_THREADS": "4",
    "PYTHONUNBUFFERED": "1",
    "TTS_THREADS": "4",
    "VOSK_SAMPLE_RATE": "16000",
    "VAD_MODE": "2",  # Mode 2 = balanced (optimal)
    "VAD_FRAME_MS": "30",
    "OLLAMA_NUM_PARALLEL": "4",
    "OLLAMA_NUM_THREAD": "4"
}

for key, value in optimizations.items():
    os.environ[key] = value

print("✅ Variables d'environnement optimisées")
print()

# 2️⃣ Fonctions de préchargement

def preload_vosk():
    """Précharge Vosk ASR"""
    try:
        from vosk import Model, KaldiRecognizer

        possible_paths = [
            '/opt/minibot/models/vosk-fr',
            '/var/lib/vosk-models/vosk-fr-small',
            '/opt/minibot/models/vosk-fr-small'
        ]

        model_path = None
        for path in possible_paths:
            if os.path.exists(path) and os.path.exists(os.path.join(path, 'conf')):
                model_path = path
                break

        if not model_path:
            print("❌ [Vosk] Modèle non trouvé")
            sys.exit(1)

        print(f"🎤 [Vosk] Chargement depuis {model_path}...")
        start = time.time()
        model = Model(model_path)

        # Test recognizer
        rec = KaldiRecognizer(model, 16000)
        rec.SetWords(True)

        elapsed = time.time() - start
        print(f"✅ [Vosk] Modèle prêt ({elapsed:.2f}s)")

    except ImportError:
        print("❌ [Vosk] Module non disponible")
        sys.exit(1)
    except Exception as e:
        print(f"❌ [Vosk] Erreur: {e}")
        sys.exit(1)

def preload_ollama():
    """Warm-up Ollama NLP"""
    try:
        # Vérifier service
        result = subprocess.run(
            ["systemctl", "is-active", "ollama"],
            capture_output=True
        )

        if result.returncode != 0:
            print("⚠️  [Ollama] Service non actif, démarrage...")
            subprocess.run(["systemctl", "start", "ollama"])
            time.sleep(5)

        # Vérifier modèle llama3.2:1b
        result = subprocess.run(["ollama", "list"], capture_output=True, text=True)

        if "llama3.2:1b" not in result.stdout:
            print("📥 [Ollama] Installation llama3.2:1b...")
            subprocess.run(["ollama", "pull", "llama3.2:1b"])

        # Supprimer phi3:mini si présent
        if "phi3:mini" in result.stdout or "phi3" in result.stdout:
            print("🗑️  [Ollama] Suppression phi3 (obsolète)...")
            subprocess.run(["ollama", "rm", "phi3:mini"], stderr=subprocess.DEVNULL)
            subprocess.run(["ollama", "rm", "phi3"], stderr=subprocess.DEVNULL)

        print("🤖 [Ollama] Warming llama3.2:1b...")
        start = time.time()

        payload = {
            "model": "llama3.2:1b",
            "prompt": "test warmup",
            "stream": False,
            "options": {
                "temperature": 0.05,
                "top_p": 0.15,
                "num_predict": 5
            }
        }

        response = requests.post(
            "http://localhost:11434/api/generate",
            json=payload,
            timeout=30
        )

        if response.status_code == 200:
            elapsed = time.time() - start
            print(f"✅ [Ollama] Modèle prêt ({elapsed:.2f}s)")
        else:
            print(f"⚠️  [Ollama] Réponse: {response.status_code}")
            sys.exit(1)

    except Exception as e:
        print(f"❌ [Ollama] Erreur: {e}")
        sys.exit(1)

def preload_tts():
    """Précharge Coqui TTS"""
    try:
        from TTS.api import TTS
        import torch

        device = "cuda" if torch.cuda.is_available() else "cpu"
        print(f"🔊 [TTS] Chargement XTTS v2 (device: {device})...")

        start = time.time()
        tts = TTS(model_name="tts_models/multilingual/multi-dataset/xtts_v2").to(device)

        elapsed = time.time() - start
        print(f"✅ [TTS] Modèle prêt ({elapsed:.2f}s)")

    except ImportError as e:
        print(f"⚠️  [TTS] Non disponible: {e}")
    except Exception as e:
        print(f"⚠️  [TTS] Warning: {e}")

def preload_vad():
    """Précharge WebRTC VAD"""
    try:
        import webrtcvad
        vad = webrtcvad.Vad(2)  # Mode 2 balanced
        print("✅ [VAD] WebRTC VAD prêt")
    except ImportError:
        print("❌ [VAD] Module non disponible")
        sys.exit(1)
    except Exception as e:
        print(f"⚠️  [VAD] Warning: {e}")

def preload_scenario():
    """Précharge scénario"""
    try:
        from scenario_cache import scenario_manager
        success = scenario_manager.preload_single_scenario()
        if success:
            print("✅ [Scénario] Cache préchargé")
        else:
            print("⚠️  [Scénario] Fallback utilisé")
    except Exception as e:
        print(f"⚠️  [Scénario] Warning: {e}")

# 3️⃣ Chargement parallèle
print("🔄 Préchargement parallèle des modèles...")
print()

threads = [
    threading.Thread(target=preload_vosk, name="Vosk"),
    threading.Thread(target=preload_ollama, name="Ollama"),
    threading.Thread(target=preload_tts, name="TTS"),
    threading.Thread(target=preload_vad, name="VAD"),
    threading.Thread(target=preload_scenario, name="Scenario")
]

start_time = time.time()

for t in threads:
    t.start()

for t in threads:
    t.join()

total_time = time.time() - start_time

print()
print("=" * 60)
print(f"⚡ Temps total de préchargement: {total_time:.2f}s (parallèle)")
print("=" * 60)
print()
print("⚙️  Optimisations actives:")
print("   • SLIN16 16kHz pour streaming Asterisk")
print("   • Exécution parallèle TTS + NLP")
print("   • WebRTC VAD mode 2 (balanced sensitivity)")
print("   • Ollama optimisé (temp=0.05, top_p=0.15)")
print("   • Latence cible: <1s end-to-end")
print()
print("✅ Pipeline optimisé et prêt pour streaming!")

EOF

[ $? -eq 0 ] || { echo "❌ Préchargement échoué"; exit 1; }

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

# ========== AUTO-HEALING STREAMING CHECKS ==========
echo ""
echo "🔧 Auto-healing streaming checks..."

# Fonction de vérification et correction automatique
check_and_fix() {
    local service_name=$1
    local check_command=$2
    local fix_command=$3
    local description=$4
    
    echo "🔍 Checking $description..."
    
    if eval "$check_command"; then
        echo "✅ $description: OK"
        return 0
    else
        echo "⚠️  $description: ISSUE DETECTED, auto-fixing..."
        eval "$fix_command"
        sleep 2
        
        # Re-vérifier après correction
        if eval "$check_command"; then
            echo "✅ $description: FIXED"
            return 0
        else
            echo "❌ $description: FAILED TO FIX"
            return 1
        fi
    fi
}

# Auto-healing checks
check_and_fix "ollama_model" \
    "ollama list | grep -q 'llama3.2:1b'" \
    "ollama pull llama3.2:1b" \
    "Ollama optimal model (llama3.2:1b)"

check_and_fix "asterisk_ari_config" \
    "grep -q 'enabled = yes' /etc/asterisk/ari.conf && grep -q 'MiniBotAI2025!' /etc/asterisk/ari.conf" \
    "echo 'Auto-fixing ARI config...' && sudo sed -i 's/\${ARI_PASSWORD}/MiniBotAI2025!/g' /etc/asterisk/ari.conf" \
    "Asterisk ARI configuration"

check_and_fix "asterisk_http_config" \
    "grep -q 'enabled=yes' /etc/asterisk/http.conf" \
    "echo '[general]\nenabled=yes\nbindaddr=0.0.0.0\nbindport=8088\nwebsocket_timeout=30\n\n[websockets]\nenabled=yes' | sudo tee /etc/asterisk/http.conf > /dev/null" \
    "Asterisk HTTP configuration"

echo "✅ Auto-healing checks completed"

# Vérifications supplémentaires optimisations
echo "🔧 Vérifications optimisations supplémentaires..."

# Vérifier modèle Ollama optimal
if ollama list 2>/dev/null | grep -q 'llama3.2:1b'; then
    echo "✅ Modèle Ollama optimal présent"
else
    echo "📥 Installation modèle optimal..."
    ollama pull llama3.2:1b >/dev/null 2>&1 &
fi

# Vérifier configuration timeout
if grep -q 'OLLAMA_TIMEOUT.*8' config.py 2>/dev/null; then
    echo "✅ Configuration timeout optimisée"
else
    echo "🔧 Optimisation timeout..."
    sed -i 's/OLLAMA_TIMEOUT = int(os.getenv("OLLAMA_TIMEOUT", "10"))/OLLAMA_TIMEOUT = int(os.getenv("OLLAMA_TIMEOUT", "8"))/' config.py 2>/dev/null || true
fi

# Vérifier optimisations NLP
if grep -q '"temperature": 0.05' services/nlp_intent.py 2>/dev/null; then
    echo "✅ Paramètres NLP optimisés"
else
    echo "🧠 Optimisation paramètres NLP..."
    sed -i 's/"temperature": 0.1/"temperature": 0.05/' services/nlp_intent.py 2>/dev/null || true
    sed -i 's/"num_predict": 50/"num_predict": 20/' services/nlp_intent.py 2>/dev/null || true
    sed -i 's/"top_p": 0.9/"top_p": 0.15/' services/nlp_intent.py 2>/dev/null || true
fi

echo "✅ Optimisations vérifiées et appliquées"

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

# Test services via health check
echo "🎤 Test Vosk via API..."
HEALTH_RESPONSE=$(curl -s http://localhost:8000/health 2>/dev/null)
if echo "$HEALTH_RESPONSE" | grep -q '"streaming":"enabled"'; then
    echo "✅ Vosk ASR: Intégré dans streaming"
else
    echo "⚠️  Vosk ASR: Non prêt"
fi

# Test Ollama via API  
echo "🤖 Test Ollama via API..."
if echo "$HEALTH_RESPONSE" | grep -q '"ollama":"running"'; then
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