# 🚀 MiniBotPanel v2 - GUIDE COMPLET STREAMING

**Architecture Temps Réel avec Vosk ASR + Ollama NLP**
Version 2.0.0 - Mode Streaming Uniquement

---

## 📋 TABLE DES MATIÈRES

1. [🎯 Vue d'ensemble](#vue-densemble)
2. [🛠️ Installation](#installation)
3. [⚙️ Configuration](#configuration)
4. [🎵 Setup Audio](#setup-audio)
5. [📊 Gestion des Contacts](#gestion-des-contacts)
6. [🚀 Lancement de Campagnes](#lancement-de-campagnes)
7. [📈 Monitoring et Analytics](#monitoring-et-analytics)
8. [🔧 Troubleshooting](#troubleshooting)
9. [🏗️ Architecture Technique](#architecture-technique)

---

## 🎯 Vue d'ensemble

MiniBotPanel v2 est une solution de robot d'appels automatique **100% streaming** avec intelligence artificielle locale.

### ✨ Fonctionnalités Streaming
- **ASR Temps Réel**: Vosk français (< 400ms latence)
- **NLP Local**: Ollama pour analyse d'intention 
- **Barge-in**: Interruption naturelle des conversations
- **AMD Hybride**: Détection répondeur Asterisk + IA Python
- **Analytics Temps Réel**: Statistiques live des campagnes

### 🎯 Performances Cibles
- **Latence Barge-in**: < 150ms
- **Latence ASR**: < 400ms  
- **Latence Intent**: < 600ms
- **Latence Totale**: < 1000ms

---

## 🛠️ Installation

### Prérequis Système
```bash
# OS supportés
Ubuntu 20.04+ / Debian 11+
4GB RAM minimum (8GB recommandé)
20GB espace disque libre
Connexion internet (installation uniquement)
```

### Installation Automatique
```bash
# 1. Cloner le projet
git clone <repository-url>
cd minibotpanelv2

# 2. Lancer l'installation streaming
sudo python3 system/install_hybrid.py

# L'installateur configure automatiquement :
# - Asterisk 22 avec AudioFork
# - PostgreSQL
# - Vosk modèles français
# - Ollama + modèles NLP
# - Services Python
```

### Vérification Installation
```bash
# Status des services
sudo systemctl status postgresql asterisk ollama

# Test connectivity
curl http://localhost:11434/api/version  # Ollama
curl http://localhost:8088/ari/asterisk/info  # ARI
```

---

## ⚙️ Configuration

### Fichier .env Principal
L'installation génère automatiquement `.env`. Principales variables :

```bash
# Mode (streaming uniquement)
STREAMING_MODE=true

# Database
DATABASE_URL=postgresql://robot:PASSWORD@localhost/minibot_db

# Asterisk ARI  
ARI_URL=http://localhost:8088
ARI_USERNAME=robot
ARI_PASSWORD=GENERATED_PASSWORD

# Vosk ASR
VOSK_MODEL_PATH=/opt/minibot/models/vosk-fr
VOSK_SAMPLE_RATE=16000

# Ollama NLP
OLLAMA_URL=http://localhost:11434
OLLAMA_MODEL=phi3:mini
OLLAMA_TIMEOUT=10

# AudioFork WebSocket
AUDIOFORK_HOST=127.0.0.1
AUDIOFORK_PORT=8765

# Barge-in & Latences (ms)
BARGE_IN_ENABLED=true
TARGET_BARGE_IN_LATENCY=150
TARGET_ASR_LATENCY=400
TARGET_INTENT_LATENCY=600
TARGET_TOTAL_LATENCY=1000

# AMD Hybride
AMD_ENABLED=true
AMD_PYTHON_ENABLED=true
AMD_MACHINE_SPEECH_THRESHOLD=2.8
AMD_HUMAN_SPEECH_THRESHOLD=1.2
```

### Configuration Avancée

#### Optimisation Performance
```bash
# Dans .env - pour serveurs puissants
VAD_MODE=3  # VAD plus strict (0=loose, 3=very tight)
OLLAMA_MODEL=mistral:7b-instruct  # Modèle plus puissant
TARGET_BARGE_IN_LATENCY=100  # Latence plus agressive
```

#### Mode Debug
```bash
# Logs détaillés
LOG_LEVEL=DEBUG
STREAMING_LOG_FILE=logs/streaming_debug.log
AMD_LOG_FILE=logs/amd_debug.log
```

---

## 🎵 Setup Audio

### 1. Préparation des Fichiers Audio

Les 9 fichiers audio doivent être au format **WAV 8kHz mono** :

```bash
audio/
├── hello.wav          # Introduction/présentation
├── retry.wav          # Relance si refus initial  
├── q1.wav             # Question qualification 1
├── q2.wav             # Question qualification 2
├── q3.wav             # Question qualification 3
├── is_leads.wav       # Question finale leads
├── confirm.wav        # Confirmation rappel
├── bye_success.wav    # Au revoir succès
├── bye_failed.wav     # Au revoir échec
└── test_audio.wav     # Test technique
```

### 2. Script de Conversion Automatique
```bash
# Conversion depuis n'importe quel format
sudo ./system/setup_audio.sh

# Le script :
# - Convertit automatiquement au bon format
# - Optimise pour téléphonie
# - Copie vers Asterisk
# - Valide la qualité
```

### 3. Validation Audio
```bash
# Test des fichiers
python3 -c "
from services.audio_assembly_service import audio_assembly_service
print('Audio files validation:', audio_assembly_service.validate_audio_files())
"
```

### 4. Qualité Audio Optimale

#### Recommandations Enregistrement
- **Débit**: 128 kbps minimum
- **Silence**: 0.5s début/fin
- **Volume**: Normalisé (-12dB peak)
- **Durée**: 10-30 secondes max par fichier

#### Script Test Qualité
```bash
# Test qualité et timing
ffprobe audio/hello.wav  # Vérifier format
play audio/hello.wav     # Test écoute
```

---

## 📊 Gestion des Contacts

### 1. Import Contacts CSV

#### Format CSV Requis
```csv
nom,prenom,telephone,email,statut
Dupont,Jean,0123456789,jean@email.com,pending
Martin,Marie,0987654321,marie@email.com,pending
```

#### Import via Script
```bash
# Import standard
python3 system/import_contacts.py contacts.csv

# Import avec validation avancée
python3 system/import_contacts.py contacts.csv --validate --dedupe

# Import par batch (gros volumes)
python3 system/import_contacts.py contacts.csv --batch-size 1000
```

#### Options Avancées
```bash
# Mapping colonnes personnalisé
python3 system/import_contacts.py data.csv \
  --phone-col "telephone" \
  --name-col "nom_complet" \
  --email-col "mail"

# Filtrage géographique
python3 system/import_contacts.py contacts.csv \
  --region-filter "01,02,03"  # Départements
```

### 2. Gestion via API

#### Endpoints Contacts
```bash
# Lister contacts
curl http://localhost:8000/contacts?status=pending&limit=100

# Ajouter contact
curl -X POST http://localhost:8000/contacts \
  -H "Content-Type: application/json" \
  -d '{"name":"Test","phone":"0123456789","email":"test@test.com"}'

# Modifier statut
curl -X PUT http://localhost:8000/contacts/123 \
  -d '{"status":"qualified"}'
```

### 3. Validation et Nettoyage

#### Script de Validation
```bash
# Validation téléphones français
python3 system/validate_contacts.py --format-french

# Détection doublons
python3 system/validate_contacts.py --dedupe

# Nettoyage base
python3 system/validate_contacts.py --clean-invalid
```

---

## 🚀 Lancement de Campagnes

### 1. Démarrage du Système

#### Services Requis
```bash
# Démarrer tous les services
./start_system.sh

# Le script démarre :
# - PostgreSQL
# - Asterisk avec AudioFork  
# - Ollama
# - Robot ARI Streaming
# - API FastAPI
```

#### Vérification Système
```bash
# Health check complet
curl http://localhost:8000/health

# Réponse attendue :
{
  "status": "healthy",
  "mode": "streaming", 
  "database": "healthy",
  "streaming": "enabled",
  "ollama": "running"
}
```

### 2. Création de Campagne

#### Via Script CLI
```bash
# Campagne production
python3 system/launch_campaign.py \
  --name "Campagne Q4 2024" \
  --scenario production \
  --limit 100 \
  --concurrent 3 \
  --start-time "14:00" \
  --end-time "18:00"

# Campagne test streaming
python3 system/launch_campaign.py \
  --name "Test Streaming" \
  --scenario test \
  --limit 10 \
  --concurrent 1
```

#### Via API REST
```bash
# Créer campagne
curl -X POST http://localhost:8000/campaigns \
  -H "Content-Type: application/json" \
  -d '{
    "name": "Test Campaign",
    "scenario": "production", 
    "max_concurrent_calls": 3,
    "contact_limit": 50,
    "schedule": {
      "start_time": "09:00",
      "end_time": "17:00"
    }
  }'
```

### 3. Scénarios Disponibles

#### Scénario Production (production)
1. **hello.wav** → Présentation 
2. **Analyse intent** → Affirm/Deny/Unsure
3. **Si intéressé** → Questions qualification (q1,q2,q3)
4. **is_leads.wav** → Question finale
5. **Si lead** → confirm.wav + bye_success.wav
6. **Si refus** → bye_failed.wav

#### Scénario Test (test)  
- **test_audio.wav** uniquement
- Validation technique streaming
- Mesure latences temps réel

### 4. Monitoring en Temps Réel

#### Dashboard API
```bash
# Stats campagne live
curl http://localhost:8000/campaigns/123/stats

# Calls actifs
curl http://localhost:8000/calls/active

# Performances streaming
curl http://localhost:8000/stats/performance
```

---

## 📈 Monitoring et Analytics

### 1. Dashboard Web

#### Endpoints Monitoring
```bash
# API Documentation complète
http://localhost:8000/docs

# Métriques temps réel
http://localhost:8000/stats/realtime

# Analytics campagne
http://localhost:8000/campaigns/123/analytics
```

### 2. Métriques Streaming

#### Performance Temps Réel
```bash
# Latences moyennes
curl http://localhost:8000/stats/latency

{
  "asr_avg_ms": 320,
  "intent_avg_ms": 480, 
  "barge_in_avg_ms": 120,
  "total_avg_ms": 850
}

# Qualité ASR
curl http://localhost:8000/stats/asr-quality

{
  "confidence_avg": 0.87,
  "transcription_accuracy": 0.93,
  "voice_activity_precision": 0.95
}
```

#### Analytics Intent
```bash
# Distribution des intentions
curl http://localhost:8000/stats/intent-distribution

{
  "affirm": 45,
  "deny": 32, 
  "interested": 28,
  "unsure": 15
}
```

### 3. Logs et Debug

#### Fichiers de Logs
```bash
# Logs principaux
tail -f logs/robot.log              # Robot principal
tail -f logs/streaming.log          # Services streaming  
tail -f logs/amd.log               # AMD hybride

# Logs Asterisk
tail -f /var/log/asterisk/full     # Asterisk complet
tail -f /var/log/asterisk/debug    # Debug ARI
```

#### Debug Streaming
```bash
# Debug VAD en temps réel
export LOG_LEVEL=DEBUG
python3 -c "
from services.live_asr_vad import live_asr_vad_service
live_asr_vad_service.test_vad()
"

# Test intent engine
python3 -c "
from services.nlp_intent import intent_engine  
result = intent_engine.analyze_intent('oui je suis intéressé', 'hello')
print(result)
"
```

### 4. Alertes et Maintenance

#### Monitoring Santé Système
```bash
# Script monitoring automatique
#!/bin/bash
# check_health.sh

# API Health
if ! curl -s http://localhost:8000/health | grep -q "healthy"; then
    echo "⚠️ API unhealthy"
    exit 1
fi

# Ollama disponible  
if ! curl -s http://localhost:11434/api/version > /dev/null; then
    echo "⚠️ Ollama down"
    exit 1
fi

# Asterisk ARI
if ! curl -s http://localhost:8088/ari/asterisk/info > /dev/null; then
    echo "⚠️ Asterisk ARI down" 
    exit 1
fi

echo "✅ All systems healthy"
```

#### Maintenance Préventive
```bash
# Nettoyage logs (crontab)
0 2 * * * find /path/to/logs -name "*.log" -mtime +7 -delete

# Backup DB quotidien
0 1 * * * pg_dump minibot_db > backup_$(date +%Y%m%d).sql

# Redémarrage hebdomadaire services
0 3 * * 0 systemctl restart ollama asterisk
```

---

## 🔧 Troubleshooting

### 1. Problèmes Fréquents

#### ❌ Latence Élevée ASR
```bash
# Symptômes : Latence > 600ms
# Diagnostic
curl http://localhost:8000/stats/latency

# Solutions :
1. Vérifier charge CPU : htop
2. Optimiser VAD : VAD_MODE=3 dans .env
3. Modèle Vosk plus petit : vosk-fr-small
4. Réduire VOSK_SAMPLE_RATE=8000
```

#### ❌ Ollama Lent/Indisponible  
```bash
# Diagnostic
curl http://localhost:11434/api/version
ollama list

# Solutions :
1. Redémarrer : sudo systemctl restart ollama
2. Modèle plus léger : OLLAMA_MODEL=phi3:mini
3. Timeout plus long : OLLAMA_TIMEOUT=15
4. Vérifier RAM disponible : free -h
```

#### ❌ Barge-in Ne Fonctionne Pas
```bash
# Diagnostic
grep "barge" logs/streaming.log

# Solutions :
1. Vérifier AudioFork : netstat -ln | grep 8765  
2. VAD sensibilité : VAD_MODE=1 (moins strict)
3. Frame duration : VAD_FRAME_DURATION=20
4. Test manuel VAD :
python3 -c "
from services.live_asr_vad import live_asr_vad_service
live_asr_vad_service.test_microphone()
"
```

#### ❌ AMD Faux Positifs
```bash
# Trop de détections "machine"
# Dans .env :
AMD_MACHINE_SPEECH_THRESHOLD=3.5  # Plus strict
AMD_SILENCE_THRESHOLD=1.2
AMD_BEEP_DETECTION_ENABLED=false  # Si problématique
```

### 2. Diagnostic Avancé

#### Performance Analysis
```bash
# Profiling latences détaillé
python3 system/benchmark_streaming.py

# Test charge
python3 system/load_test.py --concurrent 5 --duration 300

# Monitoring système
iostat -x 1    # I/O
iftop         # Réseau  
htop          # CPU/RAM
```

#### Debug Services Individuels

##### Test Vosk ASR
```bash
python3 -c "
import vosk
import json
import wave

model = vosk.Model('/opt/minibot/models/vosk-fr')
rec = vosk.KaldiRecognizer(model, 16000)

# Test avec fichier
wf = wave.open('test.wav', 'rb')
while True:
    data = wf.readframes(4000)
    if len(data) == 0:
        break
    if rec.AcceptWaveform(data):
        result = json.loads(rec.Result())
        print('Transcription:', result)
"
```

##### Test Ollama Intent
```bash
python3 -c "
import ollama

response = ollama.chat(model='phi3:mini', messages=[{
  'role': 'user',
  'content': 'Analyze sentiment: oui je suis très intéressé'
}])
print(response['message']['content'])
"
```

### 3. Solutions par Composant

#### Base de Données
```bash
# Connexion échoue
sudo systemctl status postgresql
sudo -u postgres psql -c '\l'  # Liste DBs

# Performance lente  
sudo -u postgres psql minibot_db -c 'VACUUM ANALYZE;'

# Reset complet
dropdb minibot_db
createdb minibot_db
python3 system/migrate_streaming_db.py
```

#### Asterisk/ARI
```bash
# ARI inaccessible
sudo systemctl status asterisk
sudo asterisk -r  # Console

# AudioFork problème
sudo asterisk -r
> core show applications | grep AudioFork

# Reset config
sudo systemctl stop asterisk
sudo cp asterisk-configs/* /etc/asterisk/
sudo systemctl start asterisk
```

### 4. Optimisation Production

#### Tunning Performances
```bash
# Dans .env - Production optimisée
TARGET_BARGE_IN_LATENCY=100
VAD_MODE=3
VOSK_SAMPLE_RATE=16000
OLLAMA_MODEL=phi3:mini

# Système
echo 'vm.swappiness=10' >> /etc/sysctl.conf
echo 'net.core.rmem_max=134217728' >> /etc/sysctl.conf
```

#### Monitoring Production
```bash
# Prometheus metrics (optionnel)
pip install prometheus-client
# Dans main.py : ajouter /metrics endpoint

# Log rotation
logrotate -f /etc/logrotate.d/minibot

# Backup stratégique
# Full backup : pg_dump + fichiers audio
# Incremental : rsync logs et recordings
```

---

## 🏗️ Architecture Technique

### 1. Vue d'ensemble Streaming

```
┌─────────────────┐    ┌──────────────────┐    ┌─────────────────┐
│   Asterisk 22   │◄──►│  AudioFork WS    │◄──►│  Live ASR/VAD   │
│   + AudioFork   │    │  (Port 8765)     │    │  (Vosk French)  │
└─────────────────┘    └──────────────────┘    └─────────────────┘
         │                       │                       │
         ▼                       ▼                       ▼
┌─────────────────┐    ┌──────────────────┐    ┌─────────────────┐
│  ARI WebSocket  │    │  VAD Detection   │    │ Intent Analysis │  
│  (Port 8088)    │    │  (WebRTC VAD)    │    │ (Ollama Local)  │
└─────────────────┘    └──────────────────┘    └─────────────────┘
         │                       │                       │
         └───────────────────────┼───────────────────────┘
                                 ▼
                    ┌─────────────────────────┐
                    │   Robot ARI Streaming   │
                    │   (Main Controller)     │
                    └─────────────────────────┘
                                 │
                                 ▼  
                    ┌─────────────────────────┐
                    │     FastAPI + DB        │
                    │   (Analytics & API)     │
                    └─────────────────────────┘
```

### 2. Flow de Traitement Temps Réel

#### 1. Appel Initié
```
ARI Event → Robot Controller → Answer Channel → Start AudioFork
```

#### 2. Audio Streaming  
```
Audio Stream → VAD Detection → Voice Activity → ASR Transcription  
     ↓              ↓              ↓               ↓
   16kHz         Frames 30ms   Activity True    Text Result
```

#### 3. Intent Analysis
```
Transcription → Ollama NLP → Intent Classification → Scenario Action
     ↓             ↓              ↓                    ↓
   "oui ok"     phi3:mini      "affirm" (0.87)     Play Next Audio
```

#### 4. Barge-in Logic
```
Voice Activity → Stop Playback → Process Interruption → Resume Flow
```

### 3. Services Architecture

#### Core Services
- **live_asr_vad.py**: WebSocket server + VAD + ASR temps réel
- **nlp_intent.py**: Moteur d'intention local avec Ollama
- **amd_service.py**: AMD hybride Asterisk + IA Python  
- **robot_ari_hybrid.py**: Contrôleur principal streaming

#### Support Services  
- **audio_assembly_service.py**: Assembly final conversations
- **transcript_service.py**: Génération transcripts complets
- **streaming_stats_service.py**: Analytics temps réel
- **call_launcher.py**: Lanceur campagnes

### 4. Database Schema Extensions

#### Nouvelles Colonnes Streaming
```sql
-- call_interactions
ALTER TABLE call_interactions ADD COLUMN intent VARCHAR(50);
ALTER TABLE call_interactions ADD COLUMN intent_confidence FLOAT;
ALTER TABLE call_interactions ADD COLUMN asr_latency_ms FLOAT;
ALTER TABLE call_interactions ADD COLUMN intent_latency_ms FLOAT;
ALTER TABLE call_interactions ADD COLUMN barge_in_detected BOOLEAN;
ALTER TABLE call_interactions ADD COLUMN processing_method VARCHAR(20);
ALTER TABLE call_interactions ADD COLUMN streaming_metadata JSONB;
```

### 5. Performance Benchmarks

#### Latences Mesurées (serveur moyen)
- **VAD Detection**: 10-20ms
- **ASR Vosk**: 200-400ms
- **Intent Ollama**: 300-600ms  
- **Total Pipeline**: 500-1000ms
- **Barge-in Response**: 50-150ms

#### Throughput
- **Appels Concurrent**: 3-5 (selon CPU)
- **Précision ASR**: 90-95% (français téléphonie)
- **Précision Intent**: 85-90% (contexte business)

---

## 📞 Support et Ressources

### Documentation API
- **Swagger UI**: http://localhost:8000/docs
- **ReDoc**: http://localhost:8000/redoc

### Logs et Debug
- **Logs Robot**: logs/robot.log
- **Logs Streaming**: logs/streaming.log  
- **Logs AMD**: logs/amd.log

### Architecture
- **Code Source**: Entièrement open source
- **Modularité**: Services découplés et testables
- **Évolutivité**: Architecture streaming native

### Performance
- **Monitoring**: Métriques temps réel via API
- **Optimisation**: Tunning selon environnement
- **Scalabilité**: Horizontal scaling possible

---

**MiniBotPanel v2 - Streaming Architecture**  
*Temps réel • Performance • Intelligence locale*

Version 2.0.0 - Mode Streaming Uniquement