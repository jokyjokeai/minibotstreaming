# 🚀 Guide de Déploiement MiniBotPanel v2 - Streaming Only

## Prérequis Serveur

- Ubuntu/Debian 20.04+ (VPS recommandé: OVH, Hetzner, AWS)
- Minimum 4 CPU, 8GB RAM (streaming + NLP requis)
- IP publique fixe
- Accès SSH root
- Compte SIP trunk configuré (provider téléphonie)

---

## 📋 Checklist Déploiement Streaming

### 1. Préparer le Git (LOCAL)

```bash
# Vérifier que .env n'est PAS dans Git
git status | grep .env
# Si .env apparaît, le retirer:
git rm --cached .env
git add .gitignore
git commit -m "Add .gitignore and remove .env from tracking"

# Vérifier que les fichiers audio SONT dans Git (nécessaires!)
git status | grep audio/
# Les 10 fichiers .wav doivent être tracked

# Push vers GitHub/GitLab
git push origin main
```

### 2. Sur le Serveur (VPS)

```bash
# Se connecter en SSH
ssh root@VOTRE_IP_VPS

# Cloner le repo
cd /root
git clone https://github.com/VOTRE_USERNAME/MiniBotPanelv2.git
cd MiniBotPanelv2

# Vérifier que les fichiers audio sont bien présents
ls -lh audio/*.wav
# Vous devez voir 10 fichiers: hello.wav, retry.wav, q1.wav, q2.wav, q3.wav,
# is_leads.wav, confirm.wav, bye_success.wav, bye_failed.wav, test_audio.wav

# Lancer l'installation streaming
sudo python3 system/install_hybrid.py
```

### 3. Questions Interactive Install Streaming

L'installation va vous poser des questions spécifiques au streaming:

**a) Installation Asterisk 22:**
- Si première installation: `[ENTER]` (installation AudioFork automatique)
- Si déjà installé: `n` (conserve l'existant) ou `o` (réinstalle avec AudioFork)

**b) Configuration SIP:**
```
Serveur SIP: votre_provider.net
Username SIP: votre_username
Password SIP: votre_password
Caller ID: 33XXXXXXXXX (votre numéro principal)
```

**c) Modèles Vosk français:**
```
Installation automatique: vosk-model-fr-0.22 (160MB)
```

**d) Modèles Ollama NLP:**
```
Installation automatique: llama3.2:1b (streaming optimisé)
```

**e) Test streaming complet:**
```
Voulez-vous tester? y
Numéro à appeler: 33XXXXXXXXX (votre mobile)
```

### 4. Vérifications Post-Installation Streaming

```bash
# Vérifier Asterisk 22 + AudioFork
systemctl status asterisk
asterisk -rx 'pjsip show registrations'
asterisk -rx 'module show like audiofork'

# Vérifier Vosk ASR
python3 -c "import vosk; print('Vosk OK')"

# Vérifier Ollama NLP
curl http://localhost:11434/api/tags

# Vérifier base de données streaming
sudo -u postgres psql -d minibot_db -c "\dt"

# Vérifier fichiers audio 16kHz
ls -lh /var/lib/asterisk/sounds/minibot/*.wav

# Tester API streaming
curl http://localhost:8000/health
```

### 5. Configuration Audio Streaming

```bash
# Configuration audio 16kHz optimisée
sudo ./system/setup_audio.sh
# Choisir option 1 (+3dB recommandé)

# Vérifier génération audio_texts.json
cat audio_texts.json

# Démarrer les services streaming
./start_system.sh
```

---

## ⚠️ Points Critiques Streaming

### 🔐 Secrets (.env)

Le fichier `.env` streaming est généré AUTOMATIQUEMENT par `install_hybrid.py`.

Vérifier les variables spécifiques streaming:
```bash
nano .env
```

Variables critiques:
- `ARI_PASSWORD` (généré automatiquement)
- `SIP_USERNAME`, `SIP_PASSWORD`, `SIP_SERVER` 
- `DATABASE_URL=postgresql://robot:robotpass@localhost/minibot_db`
- `VOSK_MODEL_PATH=/var/lib/vosk-models/fr`
- `OLLAMA_HOST=http://localhost:11434`

### 🎵 Fichiers Audio 16kHz

Les fichiers **DOIVENT** être optimisés 16kHz streaming:
```
hello.wav          - Introduction + présentation (16kHz SLIN16)
retry.wav          - Relance si négatif/interrogatif
q1.wav             - Question patrimoine
q2.wav             - Question inflation  
q3.wav             - Question conseiller bancaire
is_leads.wav       - Qualification finale
confirm.wav        - Demande créneau préféré
bye_success.wav    - Lead confirmé
bye_failed.wav     - Non intéressé
test_audio.wav     - Test initialisation
```

**Format requis:** 16kHz mono SLIN16 (optimisé streaming)

### 🌐 Pare-feu Streaming

`install_hybrid.py` configure automatiquement ufw:

```bash
sudo ufw status

# Ports requis streaming:
22/tcp       - SSH (CRITIQUE!)
5060/udp     - SIP
10000-20000/udp - RTP (audio streaming)
8088/tcp     - ARI + AudioFork
8000/tcp     - FastAPI API
11434/tcp    - Ollama NLP (local only)
```

### 🤖 Services Streaming

Vérifier tous les services streaming:

```bash
# Asterisk 22 + AudioFork
systemctl status asterisk

# Ollama NLP local
systemctl status ollama

# PostgreSQL streaming DB
systemctl status postgresql

# Vosk ASR (intégré au robot)
ps aux | grep robot_ari_hybrid
```

---

## 🚀 Démarrage Production Streaming

### Méthode 1: Scripts streaming (recommandé)

```bash
# Démarrer architecture streaming complète
./start_system.sh

# Services lancés:
# - robot_ari_hybrid.py (streaming principal)
# - main.py (API FastAPI)
# - system/batch_caller.py (gestionnaire campagnes)

# Vérifier logs streaming
tail -f logs/robot_ari_console.log
tail -f logs/batch_caller_console.log
tail -f logs/main.log

# Arrêter streaming
./stop_system.sh
```

### Méthode 2: systemd streaming (production)

Créer `/etc/systemd/system/minibot-streaming.service`:

```ini
[Unit]
Description=MiniBotPanel v2 - Streaming Engine
After=network.target asterisk.service postgresql.service ollama.service

[Service]
Type=simple
User=root
WorkingDirectory=/root/MiniBotPanelv2
ExecStart=/usr/bin/python3 robot_ari_hybrid.py
Restart=always
RestartSec=10
Environment=PYTHONPATH=/root/MiniBotPanelv2

[Install]
WantedBy=multi-user.target
```

Créer `/etc/systemd/system/minibot-batch.service`:

```ini
[Unit]
Description=MiniBotPanel v2 - Batch Caller
After=network.target minibot-streaming.service

[Service]
Type=simple
User=root
WorkingDirectory=/root/MiniBotPanelv2
ExecStart=/usr/bin/python3 system/batch_caller.py
Restart=always
RestartSec=15
Environment=PYTHONPATH=/root/MiniBotPanelv2

[Install]
WantedBy=multi-user.target
```

Activer streaming:
```bash
systemctl daemon-reload
systemctl enable minibot-streaming minibot-batch minibot-api
systemctl start minibot-streaming minibot-batch minibot-api
systemctl status minibot-streaming minibot-batch minibot-api
```

---

## 🧪 Test Complet Streaming

```bash
# 1. Vérifier santé streaming API
curl http://VOTRE_IP_VPS:8000/health

# Réponse attendue:
{
  "status": "healthy",
  "vosk_status": "ready",
  "ollama_status": "ready", 
  "asterisk_status": "ready",
  "database_status": "connected"
}

# 2. Lancer appel streaming test
curl -X POST http://localhost:8000/calls/launch \
  -H 'Content-Type: application/json' \
  -d '{"phone_number":"33XXXXXXXXX","scenario":"production"}'

# 3. Monitoring streaming temps réel
tail -f logs/robot_ari_console.log

# 4. Test campagne streaming
python3 system/launch_campaign.py --limit 5 --monitor
```

---

## 🐛 Problèmes Streaming Spécifiques

### Vosk ASR ne transcrit pas

**Cause:** Modèle français manquant ou corrompus
**Solution:**
```bash
# Retélécharger modèle Vosk
rm -rf /var/lib/vosk-models/fr
python3 -c "
import vosk
vosk.Model.download('fr')
"
systemctl restart minibot-streaming
```

### Ollama NLP indisponible

**Cause:** Service Ollama down ou modèle manquant
**Solution:**
```bash
# Redémarrer Ollama
systemctl restart ollama

# Vérifier modèles
ollama list

# Retélécharger si nécessaire
ollama pull llama3.2:1b

# Test rapide
curl -X POST http://localhost:11434/api/generate \
  -d '{"model":"llama3.2:1b","prompt":"test"}'
```

### AudioFork streaming non détecté

**Cause:** AudioFork pas compilé dans Asterisk 22
**Solution:**
```bash
# Vérifier AudioFork
asterisk -rx 'module show like audiofork'

# Si absent, réinstaller Asterisk avec AudioFork:
sudo python3 system/install_hybrid.py
# Choisir "o" pour forcer réinstallation
```

### Latence streaming trop élevée

**Cause:** CPU insuffisant ou modèles trop lourds
**Solution:**
```bash
# Optimiser modèles:
nano .env
# OLLAMA_MODEL=llama3.2:1b  (plus léger)

# Monitoring CPU
htop
# CPU utilisation > 80% = upgrade serveur nécessaire
```

### Pas de barge-in (interruption)

**Cause:** VAD (Voice Activity Detection) mal configuré
**Solution:**
```bash
# Vérifier WebRTC VAD
python3 -c "import webrtcvad; print('VAD OK')"

# Ajuster sensibilité dans robot_ari_hybrid.py
# VAD mode: 0=moins sensible, 3=plus sensible
```

---

## 📊 Monitoring Production Streaming

```bash
# Logs streaming principal
tail -f logs/robot_ari_console.log

# Logs NLP intent
tail -f logs/nlp_intent.log

# Logs batch caller
tail -f logs/batch_caller_console.log

# Performance Vosk ASR
grep "transcription_time" logs/robot_ari.log | tail -10

# Performance Ollama NLP  
curl http://localhost:11434/api/ps

# Appels streaming actifs
asterisk -rx 'core show channels verbose'

# Stats qualification streaming
sudo -u postgres psql -d minibot_db -c "
  SELECT status, COUNT(*)
  FROM contacts 
  WHERE updated_at > NOW() - INTERVAL '1 hour'
  GROUP BY status;
"
```

### Dashboard Streaming Temps Réel

```bash
# Monitoring campagne live
python3 system/launch_campaign.py --monitor --name "Test"

# Affichage:
# 📞 APPELS EN COURS: 3
# ⏳ En attente: 47
# ✅ Complétés: 25
# 🌟 Leads: 8
# Progression: [████████░░] 65%
```

---

## ✅ Checklist Finale Streaming

Avant de lancer en production streaming:

- [ ] Asterisk 22 + AudioFork actifs
- [ ] Vosk ASR français opérationnel  
- [ ] Ollama NLP local fonctionnel
- [ ] PostgreSQL minibot_db accessible
- [ ] Fichiers audio 16kHz dans `/var/lib/asterisk/sounds/minibot/`
- [ ] `audio_texts.json` généré avec durées correctes
- [ ] `.env` streaming configuré
- [ ] SIP trunk enregistré et crédité
- [ ] Test appel streaming réussi (transcription + intent)
- [ ] API FastAPI streaming accessible
- [ ] Barge-in fonctionnel (test interruption)
- [ ] Latence totale <200ms (inaudible)
- [ ] Services systemd streaming activés
- [ ] Monitoring streaming configuré

---

## 🎯 Commande Résumé Ultra-Rapide Streaming

```bash
# Installation streaming complète (1 commande)
ssh root@VOTRE_IP_VPS
git clone https://github.com/VOTRE_USERNAME/MiniBotPanelv2.git
cd MiniBotPanelv2
sudo python3 system/install_hybrid.py
# Répondre aux questions (SIP credentials uniquement)
sudo ./system/setup_audio.sh  # Choisir +3dB
./start_system.sh
```

**Durée totale:** 20-35 minutes (téléchargement Vosk + Ollama inclus)

**Test streaming:**
```bash
# Lancer 1 appel test
curl -X POST http://localhost:8000/calls/launch \
  -H 'Content-Type: application/json' \
  -d '{"phone_number":"33XXXXXXXXX","scenario":"production"}'

# Monitoring live
tail -f logs/robot_ari_console.log
```

---

🎉 **Streaming déployé! Architecture 100% temps réel avec Vosk ASR + Ollama NLP!**

**Performances attendues:**
- 🚀 Latence transcription: <100ms  
- 🎯 Précision ASR: 95%+
- 🤖 Temps réponse NLP: <150ms
- 💬 Barge-in naturel: ✅
- 📈 Qualification automatique: ✅