# 🤖 MiniBotPanel v2 - Robot d'Appels Automatique avec IA

> Système avancé de robot d'appels automatique basé sur **Asterisk ARI** avec transcription **Whisper**, analyse de sentiment IA, et gestion de campagnes intelligentes.

[![Python](https://img.shields.io/badge/Python-3.10+-blue.svg)](https://www.python.org/)
[![Asterisk](https://img.shields.io/badge/Asterisk-20_LTS-orange.svg)](https://www.asterisk.org/)
[![PostgreSQL](https://img.shields.io/badge/PostgreSQL-14+-blue.svg)](https://www.postgresql.org/)
[![FastAPI](https://img.shields.io/badge/FastAPI-Latest-green.svg)](https://fastapi.tiangolo.com/)

---

## 📑 Documentation

| Document | Description |
|----------|-------------|
| **[README.md](README.md)** (ce fichier) | Vue d'ensemble, installation rapide, utilisation |
| **[ARCHITECTURE.md](ARCHITECTURE.md)** | Architecture technique détaillée |
| **[read/GUIDE_COMPLET.md](read/GUIDE_COMPLET.md)** | Guide complet installation → production (500+ lignes) |
| **[index.csv](index.csv)** | Index de tous les fichiers du projet |

---

## ✨ Fonctionnalités Principales

### 🎯 Core Features
- ✅ **Appels automatisés** via Asterisk ARI (8 simultanés)
- ✅ **AMD (Answering Machine Detection)** matériel + logiciel optimisé
- ✅ **Transcription temps réel** avec faster-whisper (GPU CUDA ou CPU)
- ✅ **Analyse de sentiment IA** en français (positif/négatif/neutre/interrogatif)
- ✅ **Dialogue adaptatif** selon les réponses clients
- ✅ **Scénarios universels** - Change 9 audios = nouvelle campagne !
- ✅ **Base de données PostgreSQL** avec ORM SQLAlchemy
- ✅ **Batch Caller intelligent** avec throttling et retry automatique

### 🚀 Advanced Features
- ✅ **Audio complet assemblé** (bot + client en un seul fichier WAV)
- ✅ **Transcriptions complètes** (JSON + TXT lisible)
- ✅ **API REST complète** avec FastAPI (Swagger docs)
- ✅ **Export CSV** avec transcriptions inline
- ✅ **Gestion de campagnes** multi-milliers de contacts
- ✅ **Système de queue** avec priorités et monitoring temps réel
- ✅ **Auto-cleanup** des enregistrements anciens
- ✅ **Configuration centralisée** des temps d'écoute par étape

---

## 🏗️ Architecture Système

```
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│   FastAPI       │    │   Asterisk      │    │   PostgreSQL    │
│   (port 8000)   │◄──►│   ARI           │    │   Database      │
│                 │    │   (port 8088)   │    │                 │
└─────────────────┘    └─────────────────┘    └─────────────────┘
         │                       │                       │
         ▼                       ▼                       ▼
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│  Batch Caller   │    │  Robot ARI      │    │    Models       │
│  (Throttling)   │    │  Multi-Thread   │    │   (ORM)         │
└─────────────────┘    └─────────────────┘    └─────────────────┘
         │                       │                       │
         ▼                       ▼                       ▼
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│   Whisper       │    │   Sentiment     │    │   Audio         │
│   Service       │    │   Analysis      │    │   Assembly      │
│   (GPU/CPU)     │    │   (French)      │    │   (sox)         │
└─────────────────┘    └─────────────────┘    └─────────────────┘
```

**Voir [ARCHITECTURE.md](ARCHITECTURE.md) pour détails complets**

---

## 📦 Installation Rapide

### Prérequis
- **OS**: Ubuntu 20.04 LTS ou supérieur
- **RAM**: 8 GB minimum (16 GB recommandé)
- **CPU**: 4 cores minimum
- **GPU**: Optionnel (accélère Whisper 5x)
- **Accès**: sudo/root

### Installation Automatique (30-45 min)

```bash
# 1. Cloner/uploader le projet
cd /home/jokyjokeai/Desktop/MiniBotPanlev2

# 2. Lancer l'installation complète
sudo python3 system/install.py
```

**Le script installe:**
- ✅ Asterisk 20 LTS (compilation source)
- ✅ PostgreSQL 14+ (base minibot_db)
- ✅ Python 3.10+ + dépendances
- ✅ Whisper (GPU ou CPU auto-détecté)
- ✅ Configuration complète Asterisk (ARI, AMD, SIP)
- ✅ Tous les répertoires nécessaires

### Configuration Audio

```bash
# 1. Mettre vos 9 fichiers WAV dans audio/
cp mes_audios/*.wav audio/

# 2. Lancer setup (conversion + amplification + transcription Whisper)
sudo ./system/setup_audio.sh

# Choisir amplification (recommandé: +3 dB)
```

### Démarrage

```bash
./start_system.sh
```

**Vérification:**
```bash
# API
curl http://localhost:8000/health

# Logs
tail -f logs/robot_ari_console.log
```

---

## 🎬 Utilisation

### Scénario Production (Universel)

Le système utilise un **scénario universel** - il suffit de changer **9 fichiers audio** pour créer une nouvelle campagne !

**Flow du scénario:**
1. **hello.wav** - Introduction + "ça vous va ?"
   - Positive/Neutre → Q1
   - Négatif/Interrogatif → Retry
   - Silence/Répondeur → Raccroche (No_answer)

2. **retry.wav** - Relance (1x max)
   - Positive/Neutre → Q1
   - Négatif → Bye_Failed (Not_interested)

3. **q1.wav, q2.wav, q3.wav** - Questions qualifiantes
   - Toujours continue (peu importe Oui/Non)

4. **is_leads.wav** - **Question FINALE de qualification**
   - Positive/Neutre → **LEAD** ✅
   - Négatif → Not_interested ❌

5. **confirm.wav** - Demande créneau (si Lead)

6. **bye_success.wav** ou **bye_failed.wav** - Fin

**Temps d'écoute configurables** par étape dans `scenarios.py` (lignes 38-67).

### Import de Contacts

```bash
# Format CSV requis: phone,first_name,last_name,email,company,notes
python3 system/import_contacts.py contacts.csv
```

### Lancer une Campagne

**Via CLI (recommandé):**
```bash
# Campagne complète
python3 system/launch_campaign.py --name "Janvier 2025"

# Test sur 100 contacts
python3 system/launch_campaign.py --name "Test" --limit 100

# Avec monitoring en direct
python3 system/launch_campaign.py --name "Prod" --monitor

# Retry sur No_answer
python3 system/launch_campaign.py --name "Retry" --status No_answer --limit 500

# Simulation (dry-run - aucun appel réel)
python3 system/launch_campaign.py --name "Simu" --limit 10 --dry-run
```

**Via API:**
```bash
curl -X POST http://localhost:8000/campaigns/create \
  -H 'Content-Type: application/json' \
  -d '{
    "name": "Campagne Test",
    "phone_numbers": ["0612345678", "0698765432"],
    "scenario": "production"
  }'
```

### Export de Résultats

```bash
# Export tous les contacts
python3 system/export_contacts.py

# Export seulement les leads
python3 system/export_contacts.py --status Leads --output leads.csv

# Export avec limite
python3 system/export_contacts.py --limit 500
```

### Télécharger Audio/Transcriptions

```bash
# Audio assemblé complet (bot + client)
curl http://localhost:8000/calls/assembled/full_call_assembled_{call_id}.wav -o audio.wav

# Transcription JSON
curl http://localhost:8000/calls/transcripts/{call_id}.json

# Transcription TXT (lisible)
curl http://localhost:8000/calls/transcripts/{call_id}.txt
```

---

## ⚙️ Configuration

### Batch Caller (Throttling)

**Fichier:** `system/batch_caller.py` (lignes 30-42)

```python
MAX_CONCURRENT_CALLS = 8      # Appels simultanés max
DELAY_BETWEEN_CALLS = 2       # Délai entre lancements (secondes)
QUEUE_CHECK_INTERVAL = 5      # Vérification queue (secondes)
CALL_TIMEOUT = 120            # Timeout appel bloqué (secondes)
RETRY_DELAY = 300             # Délai avant retry (5 min) [NON UTILISÉ]
```

**Capacité estimée:** ~10,000 contacts en 16-20 heures (8 threads)

### Temps d'Écoute par Étape

**Fichier:** `scenarios.py` (lignes 38-67)

```python
LISTEN_TIMEOUTS = {
    "hello": {
        "max_silence_seconds": 2,  # Silence = fin réponse
        "wait_before_stop": 8      # Temps max d'écoute
    },
    "q1": {
        "max_silence_seconds": 2,
        "wait_before_stop": 10     # Questions = réponses longues
    },
    # ... q2, q3, retry, is_leads, confirm
}
```

**Astuce:**
- Réponses coupées → Augmente `wait_before_stop`
- Robot attend trop → Réduis `max_silence_seconds`

### Caller ID

**3 méthodes disponibles:**

1. **Statique** (pjsip.conf) - Même numéro toujours
2. **Dynamique** (extensions.conf) - Randomisation automatique
3. **Via API** (call_launcher.py) - Contrôle total Python

Voir documentation pour détails.

---

## 📊 Base de Données

### Tables Principales

**contacts** - Base de contacts
```sql
phone         VARCHAR PRIMARY KEY
first_name    VARCHAR
last_name     VARCHAR
email         VARCHAR
company       VARCHAR
status        VARCHAR (New, No_answer, Leads, Not_interested, Queued)
attempts      INTEGER
last_attempt  TIMESTAMP
```

**calls** - Enregistrements d'appels
```sql
call_id                VARCHAR PRIMARY KEY
phone_number           VARCHAR
campaign_id            VARCHAR
status                 VARCHAR
amd_result             VARCHAR (human/machine)
final_sentiment        VARCHAR (positive/negative/neutre)
is_interested          BOOLEAN
duration               INTEGER
assembled_audio_path   VARCHAR (audio complet bot+client)
started_at             TIMESTAMP
ended_at               TIMESTAMP
```

**campaigns** - Campagnes d'appels
```sql
campaign_id           VARCHAR PRIMARY KEY
name                  VARCHAR
total_calls           INTEGER
successful_calls      INTEGER
positive_responses    INTEGER
negative_responses    INTEGER
status                VARCHAR (active/paused/completed)
```

**call_queue** - File d'attente intelligente
```sql
id                    INTEGER PRIMARY KEY
campaign_id           VARCHAR
phone_number          VARCHAR
scenario              VARCHAR
status                VARCHAR (pending/calling/completed/failed)
priority              INTEGER
attempts              INTEGER
max_attempts          INTEGER (default: 1)
last_attempt_at       TIMESTAMP
```

**call_interactions** - Interactions détaillées
```sql
call_id               VARCHAR
question_number       INTEGER
question_played       VARCHAR
transcription         TEXT (Whisper)
sentiment             VARCHAR
confidence            FLOAT
response_duration     FLOAT
```

---

## 🚀 API REST

### Documentation Interactive
- **Swagger UI**: http://localhost:8000/docs
- **ReDoc**: http://localhost:8000/redoc

### Endpoints Principaux

**Appels**
- `POST /calls/launch` - Lancer appel unique
- `GET /calls` - Liste appels (pagination)
- `GET /calls/{call_id}` - Détails appel
- `GET /calls/recordings/{filename}` - Télécharger enregistrement
- `GET /calls/assembled/{filename}` - Télécharger audio assemblé
- `GET /calls/transcripts/{call_id}.json` - Transcription JSON
- `GET /calls/transcripts/{call_id}.txt` - Transcription TXT

**Campagnes**
- `POST /campaigns/create` - Créer campagne
- `GET /campaigns` - Liste campagnes
- `GET /campaigns/{campaign_id}` - Détails campagne
- `PATCH /campaigns/{campaign_id}/status` - Pause/Reprise

**Stats**
- `GET /stats/summary` - Stats globales

**Health**
- `GET /health` - Health check (DB + ARI)

---

## 📂 Structure du Projet

```
MiniBotPanlev2/
├── README.md                  # Ce fichier
├── ARCHITECTURE.md            # Architecture technique
├── index.csv                  # Index de tous les fichiers
│
├── main.py                    # API FastAPI
├── robot_ari.py              # Robot principal (multi-threading)
├── scenarios.py              # Scénarios d'appel
├── scenario_cache.py         # Pré-chargement scénarios
├── config.py                 # Configuration centralisée
├── database.py               # Connexion DB SQLAlchemy
├── models.py                 # Modèles ORM
├── logger_config.py          # Configuration logging
├── audio_texts.json          # Transcriptions des audios bot
├── requirements.txt          # Dépendances Python
│
├── api/                      # Routes API REST
│   ├── calls.py             # Endpoints appels
│   ├── campaigns.py         # Endpoints campagnes
│   └── stats.py             # Endpoints stats
│
├── services/                 # Services métier
│   ├── whisper_service.py           # Transcription Whisper
│   ├── sentiment_service.py         # Analyse sentiment
│   ├── call_launcher.py             # Lancement appels ARI
│   ├── audio_assembly_service.py    # Assemblage audio (sox)
│   └── transcript_service.py        # Génération transcriptions
│
├── system/                   # Scripts système
│   ├── install.py           # Installation complète
│   ├── setup_audio.sh       # Conversion + amplification audio
│   ├── import_contacts.py   # Import CSV
│   ├── export_contacts.py   # Export CSV
│   ├── launch_campaign.py   # CLI lancement campagnes
│   ├── batch_caller.py      # Gestionnaire queue
│   ├── cleanup_recordings.sh# Cleanup automatique
│   └── uninstall.py         # Désinstallation
│
├── asterisk-configs/         # Configs Asterisk (backup)
│   ├── pjsip.conf
│   ├── extensions.conf
│   ├── ari.conf
│   ├── http.conf
│   └── amd.conf
│
├── read/                     # Documentation
│   └── GUIDE_COMPLET.md     # Guide ultra-complet (500+ lignes)
│
├── audio/                    # Fichiers audio source
├── contacts/                 # CSV import/export
├── logs/                     # Logs système
├── recordings/               # Enregistrements individuels
├── assembled_audio/          # Audios complets assemblés
├── transcripts/              # Transcriptions (JSON + TXT)
│
├── start_system.sh          # Démarrage complet
├── stop_system.sh           # Arrêt complet
└── monitor_logs.sh          # Monitoring logs temps réel
```

---

## 🛠️ Scripts Utiles

### Gestion Système

```bash
# Démarrer
./start_system.sh

# Arrêter
./stop_system.sh

# Monitoring temps réel
./monitor_logs.sh

# Vérifier services
ps aux | grep -E "robot_ari|main|batch_caller"
```

### Logs

```bash
# Logs robot (appels en cours)
tail -f logs/robot_ari_console.log

# Logs batch caller
tail -f logs/batch_caller.log

# Logs API
tail -f logs/minibot_*.log

# Logs Asterisk
sudo tail -f /var/log/asterisk/full
```

### Nettoyage

```bash
# Nettoyage automatique (>30 jours)
sudo ./system/cleanup_recordings.sh

# Nettoyage manuel
find recordings/ -mtime +7 -delete
find assembled_audio/ -mtime +30 -delete
find transcripts/ -mtime +30 -delete
```

### Base de Données

```bash
# Connexion
PGPASSWORD=robotpass psql -h localhost -U robot -d minibot_db

# Stats contacts par statut
PGPASSWORD=robotpass psql -h localhost -U robot -d minibot_db -c "
SELECT status, COUNT(*) FROM contacts GROUP BY status;
"

# Vider la queue
PGPASSWORD=robotpass psql -h localhost -U robot -d minibot_db -c "
DELETE FROM call_queue WHERE status = 'pending';
"

# Backup
PGPASSWORD=robotpass pg_dump -h localhost -U robot minibot_db > backup_$(date +%Y%m%d).sql
```

---

## 🚨 Troubleshooting

### Appels raccrochent pendant enregistrement

**Cause:** transmit_silence désactivé

**Solution:**
```bash
sudo nano /etc/asterisk/asterisk.conf
# Ajouter dans [options]:
transmit_silence = yes

sudo systemctl restart asterisk
```

### ARI Connection Failed

```bash
# Vérifier Asterisk
sudo systemctl status asterisk
sudo systemctl restart asterisk

# Tester ARI
curl -u robot:password http://localhost:8088/ari/asterisk/info
```

### Whisper GPU non détecté

```bash
# Vérifier CUDA
nvidia-smi
python3 -c "import torch; print(torch.cuda.is_available())"

# Fallback CPU dans config.py ou .env
WHISPER_DEVICE=cpu
WHISPER_COMPUTE_TYPE=int8
```

### Audio non lu par Asterisk

```bash
# Vérifier fichiers
ls -lh /var/lib/asterisk/sounds/minibot/

# Reconvertir
sudo ./system/setup_audio.sh
```

### Database connection failed

```bash
sudo systemctl status postgresql
sudo systemctl restart postgresql

# Tester connexion
PGPASSWORD=robotpass psql -h localhost -U robot -d minibot_db
```

**Voir [read/GUIDE_COMPLET.md](read/GUIDE_COMPLET.md) section 10 pour troubleshooting complet**

---

## 📈 Performance

### Métriques (machine i9-13900KF, 125GB RAM, GPU RTX)
- **Appels simultanés**: 8 (configurable)
- **Transcription Whisper**: < 2s par appel (GPU base model)
- **Latence API**: < 100ms
- **Assemblage audio**: < 1s (sox)
- **Capacité**: ~10,000 contacts en 16-20 heures

### Métriques (VPS 4 vCPU, 8GB RAM, CPU)
- **Appels simultanés**: 3-4 recommandés
- **Transcription Whisper**: 3-5s par appel (CPU base model)
- **Capacité**: ~5,000 contacts en 24 heures

---

## 🔒 Sécurité

### Checklist

- ✅ Mots de passe forts ARI et DB (auto-générés)
- ✅ ARI accessible uniquement localhost (127.0.0.1:8088)
- ✅ Variables d'environnement (.env jamais committé)
- ✅ Validation des numéros de téléphone
- ✅ Logs sécurisés (pas de passwords)
- ✅ Firewall configuré (UFW)

### Firewall

```bash
sudo ufw allow 8000/tcp        # API (si exposition externe)
sudo ufw deny 8088/tcp          # ARI (localhost UNIQUEMENT!)
sudo ufw allow 5060/udp         # SIP
sudo ufw allow 10000:20000/udp  # RTP
```

---

## 🎓 Bonnes Pratiques

### Avant Production

1. ✅ Tester avec numéro test
2. ✅ Vérifier transmit_silence activé
3. ✅ Configurer cleanup automatique
4. ✅ Mettre en place monitoring
5. ✅ Backup base de données quotidien
6. ✅ Limiter appels simultanés selon ressources
7. ✅ Configurer firewall correctement
8. ✅ Créer vos 9 fichiers audio WAV
9. ✅ Tester scénario sur 10-20 appels
10. ✅ Modifier `audio_texts.json` avec vos vrais textes

### Gestion Campagnes

1. ✅ Toujours tester sur échantillon (--limit 100)
2. ✅ Utiliser --monitor pour surveillance temps réel
3. ✅ Exporter résultats régulièrement
4. ✅ Ne pas relancer "Not_interested" (loi RGPD)
5. ✅ Retry "No_answer" seulement

---

## 📞 Support & Documentation

### Documentation Complète

- **[README.md](README.md)** (ce fichier) - Vue d'ensemble
- **[ARCHITECTURE.md](ARCHITECTURE.md)** - Architecture technique
- **[read/GUIDE_COMPLET.md](read/GUIDE_COMPLET.md)** - Guide complet 500+ lignes
  - Installation détaillée pas-à-pas
  - Configuration complète
  - Setup audio avec amplification
  - Import/Export contacts
  - Lancement campagnes (CLI + API)
  - Monitoring & supervision
  - Export de données
  - Commandes utiles & subtilités
  - Troubleshooting complet

### Vérifications

```bash
# Vérifier installation
grep "✅" read/VERIFICATION_INSTALL.md

# Vérifier configurations Asterisk
diff -r asterisk-configs/ /etc/asterisk/
```

---

## 📄 Licence

MIT License

---

## 🎉 Démarrage Rapide

```bash
# 1. Installation
sudo python3 system/install.py

# 2. Mettre vos 9 fichiers audio dans audio/
cp mes_audios/*.wav audio/

# 3. Setup audio (conversion + amplification + transcription)
sudo ./system/setup_audio.sh

# 4. Import contacts
python3 system/import_contacts.py contacts.csv

# 5. Démarrer le système
./start_system.sh

# 6. Lancer une campagne de test
python3 system/launch_campaign.py --name "Test" --limit 10 --monitor

# 7. Vérifier résultats
curl http://localhost:8000/stats/summary
python3 system/export_contacts.py --status Leads --output leads.csv
```

**🚀 C'est parti !**

---

**Développé avec ❤️ par l'équipe MiniBotPanel**

**Dernière mise à jour:** 2025-01-17
