# 🚀 Guide de Déploiement MiniBotPanel v2

## Prérequis Serveur

- Ubuntu/Debian 20.04+ (VPS recommandé: OVH, Hetzner, AWS)
- Minimum 2 CPU, 4GB RAM
- IP publique fixe
- Accès SSH root
- Compte SIP trunk configuré (Bitcall, Twilio, etc.)

---

## 📋 Checklist Déploiement

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
git clone https://github.com/VOTRE_USERNAME/MiniBotPanlev2.git
cd MiniBotPanlev2

# Vérifier que les fichiers audio sont bien présents
ls -lh audio/*.wav
# Vous devez voir 10 fichiers: hello.wav, retry.wav, q1.wav, q2.wav, q3.wav,
# is_leads.wav, confirm.wav, bye_success.wav, bye_failed.wav, + autres

# Lancer l'installation
sudo python3 system/install.py
```

### 3. Questions Interactive Install

L'installation va vous poser des questions:

**a) Asterisk déjà installé?**
- Si première installation: `[ENTER]` (installation automatique)
- Si déjà installé: `n` (conserve l'existant) ou `o` (réinstalle)

**b) Configuration SIP:**
```
Serveur SIP: bitcall.kkucc.net (ou votre provider)
Username SIP: votre_username
Password SIP: votre_password
Caller ID: 33XXXXXXXXX (votre numéro principal)
```

**c) Modèle Whisper:**
```
Choisissez: 2 (base - recommandé pour VPS)
```

**d) Test d'appel réel:**
```
Voulez-vous tester? y
Numéro à appeler: 33XXXXXXXXX (votre mobile)
```

**e) Test API FastAPI:**
```
Voulez-vous tester? y
Numéro à appeler: 33XXXXXXXXX
```

### 4. Vérifications Post-Installation

```bash
# Vérifier Asterisk
systemctl status asterisk
asterisk -rx 'pjsip show registrations'

# Vérifier base de données
sudo -u postgres psql -d robot_calls -c "\dt"

# Vérifier fichiers audio dans Asterisk
ls -lh /var/lib/asterisk/sounds/minibot/*.wav

# Tester API
curl http://localhost:8000/health
```

### 5. Configuration Finale

```bash
# Copier les fichiers audio vers Asterisk (si pas fait par install.py)
sudo ./system/setup_audio.sh

# Démarrer les services
./start_system.sh
```

---

## ⚠️ Points Critiques à NE PAS OUBLIER

### 🔐 Secrets (.env)

**IMPORTANT:** Le fichier `.env` est généré AUTOMATIQUEMENT par `install.py`.

Si vous voulez utiliser vos propres credentials:

```bash
# Éditer .env APRÈS l'installation
nano .env
```

Vérifier:
- `ARI_PASSWORD` (généré automatiquement)
- `SIP_USERNAME`, `SIP_PASSWORD`, `SIP_SERVER` (vos credentials SIP)
- `DATABASE_URL` (devrait être: `postgresql://robot:robotpass@localhost/robot_calls`)

### 🎵 Fichiers Audio

Les fichiers suivants **DOIVENT** être présents dans `audio/`:
```
hello.wav          - Introduction + présentation
retry.wav          - Relance si négatif/interrogatif
q1.wav             - Question 1
q2.wav             - Question 2
q3.wav             - Question 3
is_leads.wav       - Question finale de qualification
confirm.wav        - Demande créneau
bye_success.wav    - Conclusion positive (Lead)
bye_failed.wav     - Conclusion négative (Not interested)
```

**Si absents:** Le système plantera lors du premier appel!

### 🌐 Pare-feu

`install.py` configure automatiquement ufw, mais vérifier:

```bash
sudo ufw status

# Ports requis:
22/tcp       - SSH (CRITIQUE!)
5060/udp     - SIP
10000-20000/udp - RTP (audio)
8088/tcp     - ARI
8000/tcp     - FastAPI API
```

### 📞 Trunk SIP

Vérifier que votre compte SIP est actif et a du crédit:

```bash
# Tester enregistrement
asterisk -rx 'pjsip show registrations'

# Vous devez voir: "Registered"
```

---

## 🚀 Démarrage Production

### Méthode 1: Scripts fournis (recommandé)

```bash
# Démarrer tout
./start_system.sh

# Vérifier logs
tail -f logs/robot_ari_console.log
tail -f logs/fastapi_console.log

# Arrêter tout
./stop_system.sh
```

### Méthode 2: systemd (production)

Créer `/etc/systemd/system/minibot-ari.service`:

```ini
[Unit]
Description=MiniBotPanel v2 - Robot ARI
After=network.target asterisk.service postgresql.service

[Service]
Type=simple
User=root
WorkingDirectory=/root/MiniBotPanlev2
ExecStart=/usr/bin/python3 robot_ari.py
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
```

Créer `/etc/systemd/system/minibot-api.service`:

```ini
[Unit]
Description=MiniBotPanel v2 - FastAPI
After=network.target

[Service]
Type=simple
User=root
WorkingDirectory=/root/MiniBotPanlev2
ExecStart=/usr/bin/python3 -m uvicorn main:app --host 0.0.0.0 --port 8000
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
```

Activer:
```bash
systemctl daemon-reload
systemctl enable minibot-ari minibot-api
systemctl start minibot-ari minibot-api
systemctl status minibot-ari minibot-api
```

---

## 🧪 Test Complet

```bash
# 1. Vérifier santé API
curl http://VOTRE_IP_VPS:8000/health

# 2. Lancer un appel test
curl -X POST http://localhost:8000/calls/launch \
  -H 'Content-Type: application/json' \
  -d '{"phone_number":"33XXXXXXXXX","scenario":"production"}'

# 3. Vérifier logs en temps réel
tail -f logs/robot_ari_console.log
```

---

## 🐛 Problèmes Fréquents

### "Channel not found" pendant appel

**Cause:** La personne a raccroché pendant l'intro
**Solution:** Normal, le système gère ça automatiquement

### "SIP Registration: Aucun compte enregistré"

**Cause:** Mauvais credentials SIP ou provider down
**Solution:** Vérifier `.env` et contacter votre provider SIP

### Whisper très lent (>20s par transcription)

**Cause:** Pas de GPU, modèle trop gros
**Solution:**
```bash
# Réinstaller avec modèle "tiny" ou "base"
nano .env
# Changer: WHISPER_MODEL=tiny
systemctl restart minibot-ari
```

### Pas d'audio assemblé généré

**Cause:** Sox manquant
**Solution:**
```bash
sudo apt install -y sox
```

### Base de données ne démarre pas

**Cause:** PostgreSQL pas installé correctement
**Solution:**
```bash
sudo systemctl restart postgresql
sudo -u postgres psql -d robot_calls -c "SELECT 1"
```

---

## 📊 Monitoring Production

```bash
# Logs robot ARI
tail -f logs/robot_ari_console.log

# Logs FastAPI
tail -f logs/fastapi_console.log

# Logs Asterisk
tail -f /var/log/asterisk/full

# Appels actifs
asterisk -rx 'core show channels'

# Stats base de données
sudo -u postgres psql -d robot_calls -c "
  SELECT status, COUNT(*)
  FROM contacts
  GROUP BY status;
"
```

---

## ✅ Checklist Finale

Avant de lancer en production:

- [ ] Asterisk tourne et enregistré SIP
- [ ] PostgreSQL accessible
- [ ] Whisper fonctionne (test transcription)
- [ ] Fichiers audio présents dans `/var/lib/asterisk/sounds/minibot/`
- [ ] `audio_texts.json` à jour avec vrais textes
- [ ] `.env` configuré avec bons credentials
- [ ] Pare-feu configuré (ports ouverts)
- [ ] Test d'appel réel réussi
- [ ] API FastAPI accessible
- [ ] Services systemd activés (optionnel)
- [ ] Monitoring configuré

---

## 🎯 Commande Résumé Ultra-Rapide

```bash
# Sur le VPS (installation complète en 1 commande)
ssh root@VOTRE_IP_VPS
git clone https://github.com/VOTRE_USERNAME/MiniBotPanlev2.git
cd MiniBotPanlev2
sudo python3 system/install.py
# Répondre aux questions interactives
./start_system.sh
```

**Durée totale:** 15-25 minutes (selon vitesse serveur et téléchargement Whisper)

---

🎉 **Voilà! Votre système est déployé et prêt pour la production!**
