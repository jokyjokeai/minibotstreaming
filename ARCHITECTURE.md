# Architecture Technique - MiniBotPanel v2

## Vue d'Ensemble

MiniBotPanel v2 est un système distribué de télécommunications intelligentes basé sur Asterisk ARI, PostgreSQL, FastAPI et des services d'IA (Whisper + analyse de sentiment).

```
┌─────────────────────────────────────────────────────────────────┐
│                   MINIBOT PANEL v2 ARCHITECTURE                  │
└─────────────────────────────────────────────────────────────────┘

┌──────────────┐      WebSocket/ARI      ┌──────────────────┐
│   Asterisk   │◄────────────────────────┤   Robot ARI      │
│   PBX/ARI    │                         │ (robot_ari.py)   │
└──────┬───────┘                         └────────┬─────────┘
       │                                          │
       │ SIP/Trunk                                │
       ▼                                          │
┌──────────────┐                                 │
│  VoIP Trunk  │                                 │
│  (Provider)  │                                 │
└──────────────┘                                 │
                                                 │
       ┌─────────────────────────────────────────┤
       │                                         │
       ▼                                         ▼
┌──────────────┐                         ┌──────────────────┐
│  PostgreSQL  │◄────────────────────────┤  Batch Caller    │
│   Database   │                         │(batch_caller.py) │
└──────┬───────┘                         └──────────────────┘
       │                                         ▲
       │                                         │
       ▼                                         │
┌──────────────┐      REST API           ┌──────────────────┐
│   FastAPI    │◄────────────────────────┤  External Users  │
│  (main.py)   │                         │   (HTTP/JSON)    │
└──────────────┘                         └──────────────────┘
       │
       ▼
┌──────────────────────────────────────────────────────────────┐
│              AI Services (In-Process)                         │
├───────────────────────┬──────────────────────────────────────┤
│ Whisper Service       │ Sentiment Analysis Service           │
│ (faster-whisper GPU)  │ (keyword-based French)               │
└───────────────────────┴──────────────────────────────────────┘
```

---

## Composants Principaux

### 1. Robot ARI (robot_ari.py)

**Rôle**: Contrôleur principal des appels via Asterisk ARI

**Technologies**:
- WebSocket natif (websocket-client)
- Connexion persistante à Asterisk ARI
- Threading pour multi-appels simultanés

**Responsabilités**:
- Réception des événements Asterisk (StasisStart, StasisEnd)
- Gestion du cycle de vie des appels
- Orchestration des scénarios (scenarios.py)
- Enregistrement audio avec détection de silence
- Transcription temps réel avec Whisper
- Analyse de sentiment
- Tracking automatique des audio (AUTO-TRACKING)
- Sauvegarde des interactions en base

**Configuration**:
```python
ARI_URL = "http://localhost:8088"
ARI_USER = "robot"
ARI_PASS = "tyxiyy6KTdGbIbUT"
RECORDINGS_PATH = "/var/spool/asterisk/recording"
MAX_CONCURRENT_CALLS = 8  # Contrôlé par threading
```

**Architecture interne**:
```
RobotARI
├── WebSocket Handler (on_message, on_open, on_close)
├── Call Thread Manager (active_calls dict)
├── Audio Tracker (call_sequences dict)
├── Playback Manager (play_audio_file, wait_for_playback_finished)
├── Recording Manager (record_with_silence_detection)
└── AI Integration (whisper_service, sentiment_service)
```

### 2. FastAPI Web Service (main.py)

**Rôle**: API REST pour contrôle externe du système

**Port**: 8000

**Endpoints**:
```
/                    → Root endpoint (status)
/health              → Health check (DB, Whisper, services)

/calls/launch        → POST: Lancer un appel individuel
/calls/{call_id}     → GET: Détails d'un appel
/calls/              → GET: Liste des appels (filtres disponibles)

/campaigns/create    → POST: Créer une campagne
/campaigns/{id}      → GET: Détails campagne
/campaigns/          → GET: Liste des campagnes
/campaigns/{id}/pause   → POST: Mettre en pause
/campaigns/{id}/resume  → POST: Reprendre
/campaigns/{id}/stop    → POST: Arrêter

/stats/overview      → GET: Statistiques globales
/stats/campaign/{id} → GET: Stats par campagne
/stats/daily         → GET: Stats quotidiennes
```

**Architecture**:
```
main.py
├── FastAPI App (CORS enabled)
├── Router: calls.py (api/calls.py)
├── Router: campaigns.py (api/campaigns.py)
└── Router: stats.py (api/stats.py)
```

### 3. Batch Caller (system/batch_caller.py)

**Rôle**: Service de lancement d'appels en batch avec throttling intelligent

**Configuration**:
```python
MAX_CONCURRENT_CALLS = 8      # Limite provider
DELAY_BETWEEN_CALLS = 2       # 2s entre chaque lancement
QUEUE_CHECK_INTERVAL = 5      # Vérification toutes les 5s
CALL_TIMEOUT = 120            # Timeout après 2min
```

**Algorithme**:
```
while running:
    1. cleanup_stuck_calls()        # Nettoyer les appels bloqués
    2. update_completed_calls()     # MAJ appels terminés
    3. count_active_calls()         # Compter actifs
    4. slots = MAX - actifs         # Calculer slots libres
    5. launch_next_calls(slots)     # Lancer nouveaux appels
    6. sleep(QUEUE_CHECK_INTERVAL)
```

**Gestion des états**:
```
pending → calling → completed
        ↓
      failed (si max_attempts atteint)
```

### 4. Base de Données PostgreSQL

**Configuration**:
```python
DATABASE_URL = "postgresql://robot:robotpass@localhost/robot_calls"
```

**Schéma (models.py)**:

```sql
-- Contacts
contacts
├── contact_id (PK)
├── phone (UNIQUE, INDEXED)
├── first_name
├── last_name
├── email
├── status (New, Leads, Not_interested, No_answer, Queued)
├── attempts
├── last_attempt
├── audio_recording_path
├── call_duration
└── timestamps (created_at, updated_at)

-- Campagnes
campaigns
├── campaign_id (PK)
├── name
├── description
├── status (pending, active, paused, completed)
├── scenario
├── total_calls
├── successful_calls
├── failed_calls
├── positive_responses
├── negative_responses
└── timestamps (created_at, started_at, ended_at)

-- Appels
calls
├── call_id (PK, VARCHAR - Asterisk channel ID)
├── phone_number (INDEXED)
├── campaign_id (FK)
├── status (answered, completed, failed)
├── amd_result (human, machine)
├── recording_path
├── duration
├── final_sentiment (positif, negatif, neutre)
├── is_interested (BOOLEAN)
└── timestamps (started_at, ended_at)

-- Interactions
call_interactions
├── interaction_id (PK)
├── call_id (FK)
├── question_number (1, 2, 3, etc.)
├── question_played (q1, q2, q3, is_leads, confirm)
├── transcription (TEXT)
├── sentiment (positif, negatif, interrogatif, neutre)
└── played_at

-- Queue d'appels
call_queue
├── queue_id (PK)
├── campaign_id (FK)
├── phone_number
├── contact_id (FK)
├── scenario
├── status (pending, calling, completed, failed)
├── priority (INT, default 0)
├── attempts
├── max_attempts (default 1)
├── call_id (Asterisk channel)
├── last_attempt_at
├── error_message
└── timestamps (created_at)

INDEX:
- contacts.phone
- calls.phone_number
- calls.campaign_id
- call_queue.status
- call_queue.campaign_id
```

---

## Flux de Données

### 1. Flux de Campagne (du lancement à la fin)

```
┌─────────────────────────────────────────────────────────────────┐
│                    CAMPAIGN FLOW                                 │
└─────────────────────────────────────────────────────────────────┘

1. CLI/API: launch_campaign.py ou POST /campaigns/create
   ├── Créer Campaign (status=active)
   ├── Charger contacts (status=New or No_answer)
   └── Insérer dans call_queue (status=pending)

2. Batch Caller (boucle infinie)
   ├── Vérifie call_queue (status=pending)
   ├── Calcule slots disponibles
   ├── Lance appels via launch_call() → Asterisk
   └── MAJ call_queue.status = calling

3. Asterisk
   ├── Dial vers numéro cible
   ├── AMD (Answering Machine Detection)
   └── Route vers Stasis(robot-app)

4. Robot ARI (WebSocket)
   ├── StasisStart → Nouveau thread
   ├── Répondre au canal (answer)
   ├── Créer enregistrement Call (status=answered)
   ├── Exécuter scenario_production()
   └── StasisEnd → MAJ Call (status=completed)

5. Scenario Production (scenarios.py)
   ├── Jouer audio → record → transcribe → sentiment
   ├── Sauvegarder call_interactions
   ├── Déterminer is_interested
   ├── Mettre à jour Contact.status
   └── Assembler audio (audio_assembly_service)

6. Batch Caller (prochain cycle)
   ├── Détecte Call.ended_at
   ├── MAJ call_queue.status = completed
   ├── MAJ Campaign stats
   └── Passe au contact suivant
```

### 2. Flux d'Appel (détaillé)

```
┌─────────────────────────────────────────────────────────────────┐
│                      CALL FLOW                                   │
└─────────────────────────────────────────────────────────────────┘

A. Initiation
   ┌─────────────────────────────────────────────┐
   │ launch_call(phone, scenario, campaign_id)   │
   └───────────────────┬─────────────────────────┘
                       │
                       ▼
   ┌─────────────────────────────────────────────┐
   │ ARI POST /channels                          │
   │ endpoint=PJSIP/xxxx@trunk                   │
   │ app=robot-app                               │
   │ appArgs=[phone,scenario,campaign_id,rec]    │
   └───────────────────┬─────────────────────────┘
                       │
                       ▼
   ┌─────────────────────────────────────────────┐
   │ Asterisk: Dial via Trunk                    │
   │ AMD() detection (machine/human)             │
   └───────────────────┬─────────────────────────┘
                       │
                       ▼
   ┌─────────────────────────────────────────────┐
   │ Stasis(robot-app, args)                     │
   └───────────────────┬─────────────────────────┘
                       │
                       ▼
B. Gestion par Robot ARI
   ┌─────────────────────────────────────────────┐
   │ StasisStart event (WebSocket)               │
   └───────────────────┬─────────────────────────┘
                       │
                       ▼
   ┌─────────────────────────────────────────────┐
   │ Launch call_thread (threading)              │
   │ ├── Answer channel                          │
   │ ├── Create Call record (DB)                 │
   │ ├── Check AMD (if MACHINE → hangup)         │
   │ ├── Initialize AUTO-TRACKING                │
   │ └── Execute scenario_production()           │
   └───────────────────┬─────────────────────────┘
                       │
                       ▼
C. Scenario Execution (scenario_production)
   ┌─────────────────────────────────────────────┐
   │ Step 1: play hello.wav                      │
   │ Step 2: record response                     │
   │         ├── Silence detection (2s)          │
   │         ├── Whisper transcription           │
   │         └── Sentiment analysis              │
   │ Step 3: Save interaction (DB)               │
   │ Step 4: Decision logic                      │
   │         ├── "oui" → continue                │
   │         └── "non" → retry or goodbye        │
   │ Step 5-8: Questions q1/q2/q3                │
   │ Step 9: is_leads check                      │
   │ Step 10: confirm + thank you                │
   └───────────────────┬─────────────────────────┘
                       │
                       ▼
D. Post-Call Processing
   ┌─────────────────────────────────────────────┐
   │ Audio Assembly Service                      │
   │ ├── Get tracked audio sequence              │
   │ ├── Concatenate bot + client WAV            │
   │ └── Save to assembled_audio/                │
   └───────────────────┬─────────────────────────┘
                       │
                       ▼
   ┌─────────────────────────────────────────────┐
   │ Transcript Service                          │
   │ ├── Generate JSON transcript                │
   │ └── Generate TXT transcript                 │
   └───────────────────┬─────────────────────────┘
                       │
                       ▼
   ┌─────────────────────────────────────────────┐
   │ Update Contact status                       │
   │ ├── Leads (if interested)                   │
   │ ├── Not_interested (if negative)            │
   │ └── No_answer (if silence/hangup)           │
   └───────────────────┬─────────────────────────┘
                       │
                       ▼
   ┌─────────────────────────────────────────────┐
   │ StasisEnd event → Hangup                    │
   │ ├── Update Call (ended_at, duration)        │
   │ └── Remove from active_calls                │
   └─────────────────────────────────────────────┘
```

---

## Architecture Audio

### 1. Auto-Tracking System

**Principe**: Tracking automatique en mémoire de tous les audio joués/enregistrés pendant un appel.

**Implémentation**:
```python
# Dans RobotARI
self.call_sequences = {}  # {channel_id: [audio_items]}

# À chaque play_audio_file()
self._track_audio(channel_id, "bot", "hello.wav")

# À chaque record_with_silence_detection()
self._track_audio(channel_id, "client", "rec_123.wav", transcription, sentiment)

# À la fin du scénario
sequence = self.get_call_sequence(channel_id)
# → [{type: "bot", file: "hello.wav", timestamp: ...},
#    {type: "client", file: "rec_123.wav", transcription: "...", sentiment: "positif"}]
```

### 2. Pipeline Audio

```
┌────────────────────────────────────────────────────────────────┐
│                   AUDIO PROCESSING PIPELINE                     │
└────────────────────────────────────────────────────────────────┘

1. Setup (system/setup_audio.sh)
   ├── Convert all audio/ files to proper format
   │   sox input.wav output.wav -r 8000 -c 1 -b 16
   ├── Normalize volume (+10dB amplification)
   ├── Copy to /var/lib/asterisk/sounds/minibot/
   └── Transcribe all with Whisper → audio_texts.json

2. During Call (Robot ARI)
   ├── play_audio_file("hello")
   │   ├── ARI: POST /channels/{id}/play
   │   │   media: "sound:minibot/hello"
   │   ├── Wait for PlaybackFinished event
   │   └── AUTO-TRACK: add to call_sequences
   │
   └── record_with_silence_detection("rec_123")
       ├── ARI: POST /channels/{id}/record
       │   format: wav
       │   maxDuration: 30s
       │   terminateOn: #
       ├── Python silence detection (2s timeout)
       ├── Stop recording via ARI
       ├── Transcribe with Whisper
       ├── Analyze sentiment
       └── AUTO-TRACK: add to call_sequences

3. Post-Call Assembly (audio_assembly_service.py)
   ├── get_call_sequence(channel_id)
   │   → [bot1, client1, bot2, client2, ...]
   ├── Build sox command:
   │   sox bot1.wav client1.wav bot2.wav client2.wav output.wav
   └── Save to assembled_audio/{phone}_{timestamp}_full.wav

4. Transcription Service (transcript_service.py)
   ├── Load call_interactions from DB
   ├── Generate JSON:
   │   [{"step": "hello", "bot": "...", "client": "..."}]
   ├── Generate TXT:
   │   BOT: Bonjour...
   │   CLIENT: Oui...
   └── Save to transcripts/{phone}_{timestamp}.{json,txt}
```

---

## Intégration Asterisk

### 1. Configuration ARI (asterisk-configs/ari.conf)

```ini
[general]
enabled = yes
pretty = yes

[robot]
type = user
read_only = no
password = tyxiyy6KTdGbIbUT
```

### 2. Dialplan (asterisk-configs/extensions.conf)

```ini
[robot-call]
exten => _X.,1,NoOp(Robot call to ${EXTEN})
same => n,Set(PHONE_NUMBER=${EXTEN})
same => n,Set(SCENARIO=${ARG1})
same => n,Set(CAMPAIGN_ID=${ARG2})
same => n,Set(REC_FILE=${ARG3})
same => n,Set(CHANNEL(hangup_handler_push)=hangup-handler,s,1)
same => n,AMD()
same => n,Set(AMD_STATUS=${AMDSTATUS})
same => n,Stasis(robot-app,${PHONE_NUMBER},${AMD_STATUS},${SCENARIO},${CAMPAIGN_ID},${REC_FILE})
same => n,Hangup()
```

### 3. AMD Configuration (asterisk-configs/amd.conf)

```ini
[amd]
initial_silence = 2500
greeting = 1500
after_greeting_silence = 800
total_analysis_time = 5000
min_word_length = 100
between_words_silence = 50
maximum_number_of_words = 3
silence_threshold = 256
maximum_word_length = 5000
```

### 4. HTTP/WebSocket (asterisk-configs/http.conf)

```ini
[general]
enabled=yes
bindaddr=0.0.0.0
bindport=8088
```

---

## Stack Technologique

### Backend
- **Python 3.10+**
- **FastAPI** - Web framework (async ASGI)
- **SQLAlchemy 2.0** - ORM
- **PostgreSQL 14+** - Base de données
- **Asterisk 18+** - PBX/ARI
- **websocket-client** - WebSocket natif pour ARI

### IA/ML
- **faster-whisper** - Transcription speech-to-text
  - Modèle: small (244MB)
  - Device: GPU (CUDA) ou CPU
  - Compute type: float16 (GPU) / int8 (CPU)
  - Language: French (fr)
- **Custom Sentiment Analysis** - Analyse de sentiment par mots-clés français

### Audio
- **sox** - Swiss Army Knife of sound processing
  - Conversion format (8kHz, mono, 16-bit)
  - Normalisation volume
  - Concaténation

### Infrastructure
- **systemd** - Gestion des services
- **bash** - Scripts système
- **PostgreSQL** - Persistence
- **PJSIP** - SIP Stack (Asterisk)

---

## Patterns de Conception

### 1. Multi-Threading pour Appels Simultanés

```python
# Robot ARI: Un thread par appel
call_thread = threading.Thread(
    target=self._handle_call_thread,
    args=(channel_id, phone_number, ...),
    daemon=True,
    name=f"Call-{channel_id}"
)
call_thread.start()
```

**Avantages**:
- 8 appels simultanés supportés
- Isolation des erreurs
- Pas de blocage mutuel

### 2. Service Pattern pour IA

```python
# Services importés et pré-chargés au démarrage
from services.whisper_service import whisper_service
from services.sentiment_service import sentiment_service

# Utilisation dans le code
result = whisper_service.transcribe(audio_path, language="fr")
sentiment, confidence = sentiment_service.analyze_sentiment(text)
```

**Avantages**:
- Chargement unique (pas de latence pendant appels)
- Singleton pattern
- Réutilisable

### 3. Queue Pattern pour Batch Processing

```python
# call_queue table comme queue de messages
pending = db.query(CallQueue).filter(status="pending").all()

for item in pending:
    launch_call(item.phone_number, ...)
    item.status = "calling"
```

**Avantages**:
- Découplage production/consommation
- Retry automatique
- Throttling facile

### 4. Auto-Tracking Pattern

```python
# Tracking transparent des audio
def play_audio_file(self, channel_id, filename):
    # ... play logic ...
    self._track_audio(channel_id, "bot", filename)  # AUTO

def record_with_silence_detection(self, channel_id, name):
    # ... record + transcribe ...
    self._track_audio(channel_id, "client", name, text, sentiment)  # AUTO
```

**Avantages**:
- Pas de gestion manuelle
- Impossible d'oublier un audio
- Séquence garantie correcte

---

## Sécurité

### 1. Credentials
```python
# PostgreSQL
DATABASE_URL = postgresql://robot:robotpass@localhost/robot_calls

# Asterisk ARI
ARI_USER = robot
ARI_PASS = tyxiyy6KTdGbIbUT
```

### 2. API
- Pas d'authentification par défaut (localhost only)
- CORS activé (allow_origins=["*"])
- À sécuriser en production avec JWT/OAuth2

### 3. Asterisk
- ARI user avec read_only=no
- WebSocket sur localhost:8088
- Pas d'exposition externe par défaut

---

## Performance

### Limites
- **8 appels simultanés** (limité par provider)
- **Delay entre appels**: 2 secondes
- **Timeout appel**: 120 secondes
- **Queue check**: 5 secondes

### Optimisations
1. **Whisper pré-chargé** au démarrage (pas de lazy loading)
2. **Scénarios pré-validés** au démarrage (scenario_cache.py)
3. **Threading** pour multi-appels (pas de blocking I/O)
4. **Index DB** sur phone, status, campaign_id
5. **Batch commits** dans batch_caller (commit après chaque lancement)

### Scalabilité
- **Vertical**: Augmenter CPU/RAM pour plus de threads Whisper
- **Horizontal**: Déployer plusieurs instances Robot ARI (load balancer Asterisk)
- **Database**: PostgreSQL connection pooling (SQLAlchemy)

---

## Monitoring & Logs

### Logs centralisés (logger_config.py)
```python
logs/
├── main.log                    # FastAPI
├── robot_ari.log               # Robot principal
├── robot_ari_console.log       # Console output
├── batch_caller.log            # Batch service
└── whisper.log                 # Transcriptions
```

### Niveaux de log
- **INFO**: Événements importants (appels, transcriptions)
- **DEBUG**: Détails techniques (playback, recording)
- **WARNING**: Anomalies (timeout, silence)
- **ERROR**: Erreurs (échecs, exceptions)

### Monitoring en temps réel
```bash
# Logs système
./monitor_logs.sh

# Logs spécifiques
tail -f logs/robot_ari.log
tail -f logs/batch_caller.log

# Asterisk
asterisk -rx "ari show users"
asterisk -rx "core show channels"
```

---

## Déploiement

### 1. Installation complète
```bash
python3 system/install.py
```

### 2. Configuration audio
```bash
sudo ./system/setup_audio.sh
```

### 3. Import contacts
```bash
python3 system/import_contacts.py contacts/export_full.csv
```

### 4. Démarrage système
```bash
./start_system.sh
# Lance:
# - robot_ari.py (WebSocket ARI)
# - main.py (FastAPI port 8000)
# - batch_caller.py (Queue processor)
```

### 5. Lancement campagne
```bash
python3 system/launch_campaign.py --name "Test Campaign" --limit 100
```

### 6. Monitoring
```bash
./monitor_logs.sh
```

### 7. Arrêt
```bash
./stop_system.sh
```

---

## Références

- **Asterisk ARI**: https://docs.asterisk.org/Asterisk_18_Documentation/API_Documentation/Asterisk_REST_Interface/
- **faster-whisper**: https://github.com/guillaumekln/faster-whisper
- **FastAPI**: https://fastapi.tiangolo.com/
- **SQLAlchemy**: https://www.sqlalchemy.org/
- **Sox**: http://sox.sourceforge.net/

---

**Document généré le**: 2025-10-17
**Version système**: MiniBotPanel v2.0
**Architecture par**: Claude Code
