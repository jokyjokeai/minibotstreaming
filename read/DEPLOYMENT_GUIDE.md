# 🚀 Guide de Déploiement MiniBotPanel v2

## Vue d'Ensemble

Ce guide détaille l'installation, la configuration et le déploiement production de MiniBotPanel v2 avec TTS Voice Cloning et streaming temps réel optimisé.

## 📋 Prérequis Système

### Configuration Minimale
```bash
OS: Ubuntu 20.04+ / Debian 11+ / CentOS 8+
CPU: 4 vCPU (Intel/AMD x64)
RAM: 8GB minimum
Storage: 50GB SSD
Network: 100Mbps minimum
```

### Configuration Recommandée (Production)
```bash
OS: Ubuntu 22.04 LTS
CPU: 8 vCPU (Intel Xeon ou AMD EPYC)
RAM: 16GB+ 
Storage: 100GB+ NVMe SSD
Network: 1Gbps dédié
GPU: NVIDIA RTX 4060+ (optionnel pour TTS)
```

### Ports Réseau Requis
```bash
8000    # FastAPI Web Server
5432    # PostgreSQL Database
8088    # Asterisk ARI HTTP
5060    # SIP Protocol
10000-20000/udp  # RTP Media (configurable)
11235   # Ollama API
```

## 🔧 Installation Automatique

### Méthode Recommandée (Zero-Gap)
```bash
# 1. Cloner le repository
git clone https://github.com/jokyjokeai/minibotstreaming.git
cd minibotstreaming

# 2. Installation complète automatique (15-20 minutes)
sudo python3 system/install_hybrid.py

# 3. Vérification optionnelle des prérequis
python3 system/check_requirements.py

# 4. Démarrage immédiat
./start_system.sh
```

### Résultat Garanti
```json
{
  "status": "healthy",
  "mode": "streaming", 
  "tts_voice_cloning": "enabled",
  "ollama": "running",
  "performance": {
    "nlp_latency": "<600ms",
    "json_validity": "100%", 
    "voice_generation": "<2s"
  }
}
```

### Processus d'Installation Détaillé

L'installation automatique effectue les opérations suivantes :

#### Phase 1: Dépendances Système
```bash
# Mise à jour système
apt update && apt upgrade -y

# Installation packages essentiels
apt install -y python3 python3-pip postgresql asterisk sox ffmpeg espeak git curl

# Configuration PostgreSQL
systemctl enable postgresql
systemctl start postgresql
```

#### Phase 2: Dépendances Python
```bash
# Installation packages Python core
pip3 install fastapi uvicorn sqlalchemy psycopg2-binary

# Installation ASR et NLP
pip3 install vosk numpy scipy librosa websockets

# Installation TTS avec détection GPU/CPU automatique
if nvidia-smi; then
    pip3 install torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cu118
else
    pip3 install torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cpu
fi

pip3 install TTS transformers
```

#### Phase 3: Configuration Asterisk
```bash
# Configuration ARI et HTTP
echo "enabled=yes" > /etc/asterisk/http.conf
echo "bindaddr=127.0.0.1" >> /etc/asterisk/http.conf
echo "bindport=8088" >> /etc/asterisk/http.conf

# Configuration ARI
echo "[minibotpanel]" > /etc/asterisk/ari.conf
echo "type=user" >> /etc/asterisk/ari.conf
echo "password=password" >> /etc/asterisk/ari.conf
echo "read_only=no" >> /etc/asterisk/ari.conf
```

#### Phase 4: Installation Ollama et Modèles
```bash
# Installation Ollama
curl -fsSL https://ollama.ai/install.sh | sh

# Démarrage service
systemctl enable ollama
systemctl start ollama

# Téléchargement modèle optimisé
ollama pull llama3.2:1b

# Vérification modèle
ollama list | grep llama3.2:1b
```

#### Phase 5: Configuration Base de Données
```bash
# Création utilisateur et base
sudo -u postgres createuser minibotpanel
sudo -u postgres createdb minibotpanel_db -O minibotpanel
sudo -u postgres psql -c "ALTER USER minibotpanel PASSWORD 'minibotpanel_password';"

# Initialisation schéma
python3 -c "from database.models import create_tables; create_tables()"
```

## ⚙️ Configuration Détaillée

### Variables d'Environnement Production
```bash
# Créer fichier .env
cat > .env << EOF
# Base de données
DATABASE_URL=postgresql://minibotpanel:minibotpanel_password@localhost/minibotpanel_db

# Asterisk ARI
ARI_HOST=localhost
ARI_PORT=8088
ARI_USERNAME=minibotpanel
ARI_PASSWORD=password

# Ollama NLP
OLLAMA_HOST=localhost
OLLAMA_PORT=11235
OLLAMA_MODEL=llama3.2:1b

# TTS Configuration
TTS_CACHE_SIZE=50
TTS_GPU_ENABLED=auto

# Performance
MAX_CONCURRENT_CALLS=8
DB_POOL_SIZE=20
LOG_LEVEL=INFO
EOF
```

### Configuration Asterisk Avancée

#### extensions.conf
```bash
cat > /etc/asterisk/extensions.conf << 'EOF'
[general]
static=yes
writeprotect=no

[default]
exten => _X.,1,Answer()
same => n,Stasis(minibotpanel,${EXTEN})
same => n,Hangup()

[outbound]
exten => _X.,1,Set(CALLERID(num)=0123456789)
same => n,Dial(SIP/provider/${EXTEN})
same => n,Hangup()
EOF
```

#### sip.conf (si utilisation SIP)
```bash
cat > /etc/asterisk/sip.conf << 'EOF'
[general]
context=default
allowoverlap=no
bindport=5060
bindaddr=0.0.0.0
srvlookup=yes
disallow=all
allow=ulaw
allow=alaw
allow=g729

[provider]
type=peer
host=your.sip.provider.com
username=your_username
secret=your_password
fromuser=your_username
fromdomain=your.sip.provider.com
insecure=port,invite
canreinvite=no
context=outbound
EOF
```

### Configuration TTS Voice Cloning

#### Calibration Embeddings Initiaux
```bash
# Créer répertoire voice embeddings
mkdir -p voices/embeddings

# Génération embeddings de base (exemples audio requis)
python3 services/tts_voice_clone.py --calibrate --voice-samples audio/samples/
```

#### Configuration Profils Personnalité
```json
{
  "personality_profiles": {
    "Sympathique et décontracté": {
      "speed_adjustment": 0.95,
      "pitch_adjustment": "medium-low",
      "emotion_level": "friendly",
      "professionalism_level": 7,
      "voice_characteristics": {
        "warmth": "high",
        "energy": "medium",
        "authority": "low"
      }
    },
    "Professionnel et rassurant": {
      "speed_adjustment": 1.0,
      "pitch_adjustment": "medium",
      "emotion_level": "confident",
      "professionalism_level": 9,
      "voice_characteristics": {
        "warmth": "medium",
        "energy": "medium",
        "authority": "high"
      }
    },
    "Énergique et enthousiaste": {
      "speed_adjustment": 1.15,
      "pitch_adjustment": "medium-high",
      "emotion_level": "enthusiastic",
      "professionalism_level": 8,
      "voice_characteristics": {
        "warmth": "high",
        "energy": "high",
        "authority": "medium"
      }
    }
  }
}
```

## 🎭 Création de Scénarios

### Générateur Interactif Complet
```bash
# Lancement du générateur
python3 system/scenario_generator.py

# Le générateur pose les questions suivantes:
# 1. Informations entreprise complètes
# 2. Profil commercial et personnalité TTS
# 3. Détails produit/service
# 4. Génération objections automatique
# 5. Configuration variables dynamiques
```

### Exemple de Session de Génération
```
🏢 INFORMATIONS ENTREPRISE
Nom de votre entreprise : France Patrimoine Expert
Adresse complète : 15 rue de la Paix, 75001 Paris
Numéro de téléphone : 01.23.45.67.89
Site web : https://france-patrimoine-expert.fr
Secteur d'activité : Finance/Patrimoine

👤 PROFIL COMMERCIAL
Prénom du commercial : Thierry
Nom du commercial : Dubois
Titre/Fonction : Conseiller Patrimoine Senior

🎭 PERSONNALITÉ TTS (choisir 1-6):
1. Sympathique et décontracté
2. Professionnel et rassurant ← SÉLECTIONNÉ
3. Énergique et enthousiaste
4. Discret et consultative
5. Chaleureux et familial
6. Autorité et expertise

💼 PRODUIT/SERVICE
Description : Optimisation patrimoniale et défiscalisation
Prix moyen : 15000€ de droits d'entrée
Avantage principal : Rendement 8% net garanti
Différenciateur : Expert fiscal agréé depuis 15 ans

🚫 OBJECTIONS AUTOMATIQUES (secteur Finance/Patrimoine):
- "C'est trop cher / Je n'ai pas les moyens"
- "Je ne fais pas confiance aux conseillers financiers"
- "J'ai déjà un conseiller"
- "Je dois en parler à mon conjoint"
- "Je n'ai pas le temps maintenant"

📝 GÉNÉRATION COMPLÈTE...
✅ Scénario 'patrimoine_expert' créé avec succès!
```

### Structure Générée
```
scenarios/patrimoine_expert/
├── patrimoine_expert_scenario.py      # Code scénario complet
├── patrimoine_expert_config.json      # Configuration streaming
├── patrimoine_expert_prompts.json     # Prompts IA dynamiques
├── patrimoine_expert_audio_texts.json # Mapping fichiers audio
└── test_patrimoine_expert.py         # Script de test
```

## 🚀 Démarrage et Gestion des Services

### Démarrage Complet Automatique
```bash
# Démarrage avec auto-healing
./start_system.sh

# Le script effectue automatiquement:
# 1. Vérification configuration Ollama
# 2. Contrôle ARI Asterisk
# 3. Test base de données
# 4. Validation TTS
# 5. Démarrage tous services
```

### Gestion Services Individuels
```bash
# PostgreSQL
sudo systemctl start postgresql
sudo systemctl status postgresql

# Asterisk
sudo systemctl start asterisk
sudo asterisk -rvvv  # Console debug

# Ollama
sudo systemctl start ollama
ollama list  # Vérifier modèles

# FastAPI (manuel)
cd /path/to/minibotpanel
python3 -m uvicorn main:app --host 0.0.0.0 --port 8000 --reload
```

### Vérification Santé Système
```bash
# Health check global
curl http://localhost:8000/health

# Réponse attendue:
{
  "status": "healthy",
  "timestamp": "2024-10-22T15:30:00Z",
  "services": {
    "database": "healthy",
    "asterisk": "healthy", 
    "ollama": "healthy",
    "tts": "healthy"
  },
  "performance": {
    "nlp_latency": "450ms",
    "tts_latency": "1.8s",
    "concurrent_calls": 0
  }
}
```

## 📊 Monitoring et Observabilité

### Logs Détaillés
```bash
# Logs principaux
tail -f logs/minibotpanel.log

# Logs erreurs uniquement
tail -f logs/minibotpanel_errors.log

# Logs debug ultra-détaillés
tail -f logs/minibotpanel_debug.log

# Statistiques performance temps réel
curl http://localhost:8000/stats/performance
```

### Métriques de Performance
```bash
# Endpoints de monitoring
curl http://localhost:8000/stats/campaigns    # Statistiques campagnes
curl http://localhost:8000/stats/tts         # Performance TTS
curl http://localhost:8000/stats/nlp         # Métriques Ollama
curl http://localhost:8000/stats/system      # Ressources système
```

### Dashboard Monitoring (Optionnel)
```bash
# Installation Grafana + Prometheus
sudo apt install -y prometheus grafana-server

# Configuration metrics endpoint
echo "
- job_name: 'minibotpanel'
  static_configs:
    - targets: ['localhost:8000']
" >> /etc/prometheus/prometheus.yml

sudo systemctl restart prometheus grafana-server
```

## 🧪 Tests et Validation

### Test Complet du Système
```bash
# Vérification prérequis
python3 system/check_requirements.py

# Test TTS voice cloning
python3 services/tts_voice_clone.py

# Test scénario généré
python3 scenarios/patrimoine_expert/test_patrimoine_expert.py

# Test appel complet (simulation)
curl -X POST http://localhost:8000/calls/launch \
  -H 'Content-Type: application/json' \
  -d '{
    "phone_number": "33612345678",
    "scenario": "patrimoine_expert",
    "test_mode": true
  }'
```

### Validation Performance
```bash
# Test latence NLP
time curl -X POST http://localhost:8000/nlp/analyze \
  -H 'Content-Type: application/json' \
  -d '{"text": "Je suis intéressé par votre produit"}'

# Test génération TTS
time curl -X POST http://localhost:8000/tts/generate \
  -H 'Content-Type: application/json' \
  -d '{
    "text": "Bonjour, je suis Thierry de France Patrimoine",
    "personality": "Professionnel et rassurant"
  }'
```

## 🎯 Campagnes et Utilisation

### Import Contacts
```bash
# Format CSV requis: phone,first_name,last_name,email,company,notes
cat > contacts_example.csv << EOF
phone,first_name,last_name,email,company,notes
33612345678,Jean,Dupont,jean.dupont@email.com,SARL Dupont,Prospect chaud
33687654321,Marie,Martin,marie.martin@email.com,SAS Martin,Rendez-vous à rappeler
EOF

# Import en base
python3 system/import_contacts.py contacts_example.csv
```

### Lancement Campagne
```bash
# Campagne avec scénario personnalisé
python3 system/launch_campaign.py \
  --name "Campagne Patrimoine Q4 2024" \
  --scenario "patrimoine_expert" \
  --limit 1000 \
  --parallel 4 \
  --monitor

# Monitoring temps réel
curl http://localhost:8000/campaigns/active
```

### Analyse Résultats
```bash
# Statistiques campagne
curl http://localhost:8000/campaigns/123/stats

# Export résultats CSV
curl http://localhost:8000/campaigns/123/export > resultats_campagne.csv

# Logs conversationnels détaillés
curl http://localhost:8000/campaigns/123/conversations
```

## 🔧 Troubleshooting Production

### Problèmes Courants et Solutions

#### 1. Erreur "Invalid JSON response from Ollama"
```bash
# Diagnostic
curl http://localhost:11235/api/tags
ollama list

# Solution
ollama pull llama3.2:1b
sudo systemctl restart ollama

# Vérification paramètres optimisés
grep -A 10 "options=" services/nlp_intent.py
```

#### 2. TTS Latence Élevée (>5 secondes)
```bash
# Vérifier embeddings
ls -la voices/embeddings/

# Régénérer si nécessaire
python3 services/tts_voice_clone.py --regenerate-embeddings

# Vérifier GPU
nvidia-smi  # Si disponible
python3 -c "import torch; print(torch.cuda.is_available())"
```

#### 3. Erreurs ARI "404 Not Found"
```bash
# Vérifier configuration HTTP Asterisk
sudo asterisk -rx "http show status"

# Redémarrer Asterisk si nécessaire
sudo systemctl restart asterisk

# Test manuel ARI
curl http://localhost:8088/ari/asterisk/info \
  -u minibotpanel:password
```

#### 4. Base de Données "Connection Refused"
```bash
# Vérifier statut PostgreSQL
sudo systemctl status postgresql

# Vérifier connexions
sudo -u postgres psql -l

# Recréer si nécessaire
sudo -u postgres dropdb minibotpanel_db
sudo -u postgres createdb minibotpanel_db -O minibotpanel
```

### Commandes de Debug Avancées
```bash
# Logs système complets
journalctl -u asterisk -f
journalctl -u postgresql -f
journalctl -u ollama -f

# Monitoring ressources temps réel
htop
iotop
nethogs

# Traces réseau (appels SIP)
sudo tcpdump -i any port 5060 -w sip_debug.pcap
```

## 🔒 Sécurité Production

### Hardening Système
```bash
# Firewall configuration
sudo ufw enable
sudo ufw allow 22/tcp     # SSH
sudo ufw allow 8000/tcp   # FastAPI
sudo ufw allow 5060/udp   # SIP
sudo ufw allow 10000:20000/udp  # RTP

# Fail2ban pour protection SSH
sudo apt install fail2ban
sudo systemctl enable fail2ban
```

### Backup Automatique
```bash
# Script backup quotidien
cat > /etc/cron.daily/minibotpanel-backup << 'EOF'
#!/bin/bash
DATE=$(date +%Y%m%d_%H%M%S)
BACKUP_DIR="/backup/minibotpanel"

# Backup base données
sudo -u postgres pg_dump minibotpanel_db > $BACKUP_DIR/db_$DATE.sql

# Backup configuration
tar -czf $BACKUP_DIR/config_$DATE.tar.gz /path/to/minibotpanel/

# Cleanup anciens backups (>30 jours)
find $BACKUP_DIR -name "*.sql" -mtime +30 -delete
find $BACKUP_DIR -name "*.tar.gz" -mtime +30 -delete
EOF

chmod +x /etc/cron.daily/minibotpanel-backup
```

### SSL/TLS Configuration
```bash
# Installation Certbot pour Let's Encrypt
sudo apt install certbot

# Génération certificat (remplacer example.com)
sudo certbot certonly --standalone -d api.example.com

# Configuration NGINX reverse proxy
sudo apt install nginx
cat > /etc/nginx/sites-available/minibotpanel << 'EOF'
server {
    listen 80;
    server_name api.example.com;
    return 301 https://$server_name$request_uri;
}

server {
    listen 443 ssl http2;
    server_name api.example.com;
    
    ssl_certificate /etc/letsencrypt/live/api.example.com/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/api.example.com/privkey.pem;
    
    location / {
        proxy_pass http://localhost:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
    }
}
EOF

sudo ln -s /etc/nginx/sites-available/minibotpanel /etc/nginx/sites-enabled/
sudo systemctl restart nginx
```

## 📈 Optimisation Performance

### Configuration GPU (si disponible)
```bash
# Installation drivers NVIDIA
sudo apt install nvidia-driver-525

# Vérification
nvidia-smi

# Configuration TTS GPU
export CUDA_VISIBLE_DEVICES=0
export TTS_DEVICE=cuda
```

### Optimisation Base de Données
```sql
-- Connexion PostgreSQL
sudo -u postgres psql minibotpanel_db

-- Index de performance
CREATE INDEX CONCURRENTLY idx_calls_campaign_id ON calls(campaign_id);
CREATE INDEX CONCURRENTLY idx_calls_status ON calls(status);
CREATE INDEX CONCURRENTLY idx_calls_created_at ON calls(created_at);

-- Configuration performance
ALTER SYSTEM SET shared_buffers = '256MB';
ALTER SYSTEM SET effective_cache_size = '1GB';
ALTER SYSTEM SET work_mem = '4MB';
SELECT pg_reload_conf();
```

### Tuning Asterisk
```bash
# Configuration asterisk.conf
cat >> /etc/asterisk/asterisk.conf << 'EOF'
[options]
maxcalls=100
maxload=1.0
runuser=asterisk
rungroup=asterisk

[compat]
res_agi_legacy_mode = no
EOF

sudo systemctl restart asterisk
```

## 🎯 Mise en Production

### Checklist Pré-Production
- [ ] Tous les tests système passent
- [ ] Configuration TLS/SSL activée
- [ ] Monitoring et alertes configurés
- [ ] Backup automatique configuré
- [ ] Firewall et sécurité activés
- [ ] Performance validée avec charge nominale
- [ ] Documentation équipe complète

### Procédure de Déploiement
```bash
# 1. Backup système complet
sudo -u postgres pg_dump minibotpanel_db > backup_pre_prod.sql

# 2. Test final complet
python3 system/check_requirements.py
curl http://localhost:8000/health

# 3. Configuration production
export ENVIRONMENT=production
export LOG_LEVEL=WARNING

# 4. Démarrage services production
./start_system.sh

# 5. Validation post-déploiement
curl https://api.votre-domaine.com/health
```

### Monitoring Post-Déploiement
```bash
# Surveillance 24/7 recommandée
watch -n 30 'curl -s http://localhost:8000/health | jq'

# Alertes automatiques (exemple avec webhook Slack)
curl -X POST -H 'Content-Type: application/json' \
  -d '{"text":"MiniBotPanel v2 déployé avec succès!"}' \
  YOUR_SLACK_WEBHOOK_URL
```

---

**🎉 MiniBotPanel v2 est maintenant déployé et prêt pour vos campagnes d'appel commercial intelligentes !**