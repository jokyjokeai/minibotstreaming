# 📚 GUIDE COMPLET - MiniBotPanel v2

Guide complet d'installation, configuration et utilisation du système de robot d'appels automatisé.

---

## 📑 Table des Matières

1. [Installation & Déploiement](#1-installation--déploiement)
2. [Configuration du Système](#2-configuration-du-système)
3. [Setup Audio](#3-setup-audio)
4. [Import/Export de Contacts](#4-importexport-de-contacts)
5. [Lancement de Campagnes](#5-lancement-de-campagnes)
6. [Monitoring & Supervision](#6-monitoring--supervision)
7. [Gestion du Système](#7-gestion-du-système)
8. [Export de Données](#8-export-de-données)
9. [Commandes Utiles & Subtilités](#9-commandes-utiles--subtilités)
10. [Troubleshooting](#10-troubleshooting)

---

## 1. Installation & Déploiement

### 1.1. Prérequis Système

- **OS**: Ubuntu 20.04 LTS ou supérieur
- **RAM**: 8 GB minimum (16 GB recommandé)
- **CPU**: 4 cores minimum
- **Disque**: 50 GB minimum
- **GPU**: Optionnel (accélère Whisper)
- **Accès**: sudo/root

### 1.2. Installation Complète

```bash
cd /home/jokyjokeai/Desktop/MiniBotPanlev2
sudo python3 system/install.py
```

**Ce script installe automatiquement:**

1. **Asterisk 20** (serveur VoIP)
   - Configuration ARI (Asterisk REST Interface)
   - Configuration AMD (Answering Machine Detection)
   - Configuration extensions et routes

2. **PostgreSQL 14** (base de données)
   - Création de la base `minibot_db`
   - Utilisateur `robot` avec mot de passe `robotpass`
   - Tables: contacts, calls, campaigns, call_interactions, call_queue

3. **Python 3.10+** avec dépendances
   - FastAPI (API web)
   - SQLAlchemy (ORM)
   - faster-whisper (transcription)
   - asyncari (client ARI)
   - requests, aiohttp, etc.

4. **Outils système**
   - sox (traitement audio)
   - ffmpeg (conversion audio)
   - curl, wget

**Durée d'installation**: ~30-45 minutes

### 1.3. Vérification Post-Installation

```bash
# Vérifier Asterisk
sudo systemctl status asterisk

# Vérifier PostgreSQL
sudo systemctl status postgresql

# Vérifier la connectivité ARI
curl -u robot:j1B2MMrloXdddx60 http://localhost:8088/ari/asterisk/info

# Vérifier la base de données
PGPASSWORD=robotpass psql -h localhost -U robot -d minibot_db -c "\dt"
```

**Voir aussi**: `read/VERIFICATION_INSTALL.md` pour la vérification détaillée.

---

## 2. Configuration du Système

### 2.1. Configuration Générale (`config.py`)

Fichier principal de configuration situé à la racine du projet.

```python
# Base de données PostgreSQL
DATABASE_URL = "postgresql://robot:robotpass@localhost/minibot_db"

# Asterisk ARI
ARI_URL = "http://localhost:8088"
ARI_USERNAME = "robot"
ARI_PASSWORD = "j1B2MMrloXdddx60"
ARI_APP = "robot"

# Trunk SIP pour émission d'appels
TRUNK = "voip-trunk"  # ← À adapter selon ton opérateur
```

**⚠️ Important**: Modifie `TRUNK` selon ton opérateur VoIP.

### 2.2. Configuration du Caller ID

Le Caller ID (numéro affiché chez le destinataire) se configure dans:

```bash
/etc/asterisk/extensions.conf
```

**Exemple**:
```
exten => _X.,1,NoOp(Outgoing call to ${EXTEN})
    same => n,Set(CALLERID(num)=0123456789)  ; ← Ton numéro
    same => n,Dial(PJSIP/${EXTEN}@voip-trunk)
```

**Voir**: `read/CONFIGURATION_CALLER_ID.md` pour le guide détaillé.

### 2.3. Configuration du Batch Caller

Le batch caller gère l'émission des appels en campagne avec throttling.

**Fichier**: `system/batch_caller.py`

**Paramètres clés** (lignes 22-30):

```python
# Nombre maximum d'appels simultanés
MAX_CONCURRENT_CALLS = 8  # ← Change ici

# Délai entre chaque lancement d'appel (secondes)
CALL_INTERVAL = 5  # ← Change ici

# Temps d'attente entre chaque vérification de la queue (secondes)
QUEUE_CHECK_INTERVAL = 10

# Nombre maximum de tentatives par contact
MAX_RETRY_ATTEMPTS = 3
```

**Capacité estimée avec 8 appels simultanés:**
- ~10,000 contacts en 16-20 heures
- Dépend du taux de réponse (répondeurs ~3s, conversations ~180s)

### 2.4. Configuration des Temps d'Écoute

Les temps d'écoute par étape du scénario se configurent dans:

**Fichier**: `scenarios.py` (lignes 38-67)

```python
LISTEN_TIMEOUTS = {
    "hello": {
        "max_silence_seconds": 2,  # Silence = fin de réponse
        "wait_before_stop": 8      # Temps max d'écoute
    },
    "retry": {
        "max_silence_seconds": 2,
        "wait_before_stop": 6
    },
    "q1": {
        "max_silence_seconds": 2,
        "wait_before_stop": 10     # Questions = réponses longues
    },
    "q2": {
        "max_silence_seconds": 2,
        "wait_before_stop": 10
    },
    "q3": {
        "max_silence_seconds": 2,
        "wait_before_stop": 10
    },
    "is_leads": {
        "max_silence_seconds": 2,
        "wait_before_stop": 8      # Question de qualification
    },
    "confirm": {
        "max_silence_seconds": 2,
        "wait_before_stop": 6      # Choix simple (matin/midi/soir)
    }
}
```

**Astuces**:
- Réponses coupées trop tôt → Augmente `wait_before_stop`
- Robot attend trop longtemps → Réduis `max_silence_seconds`

---

## 3. Setup Audio

### 3.1. Préparation des Fichiers Audio

Le scénario production nécessite **9 fichiers WAV**:

1. **hello.wav** - Introduction + "ça vous va ?"
2. **retry.wav** - Relance si négatif/interrogatif
3. **q1.wav** - Question 1 (qualifiante)
4. **q2.wav** - Question 2 (qualifiante)
5. **q3.wav** - Question 3 (qualifiante)
6. **is_leads.wav** - Question FINALE de qualification (détermine Lead/Not_interested)
7. **confirm.wav** - Demande créneau (matin/après-midi/soir)
8. **bye_success.wav** - Fin positive (Lead confirmé)
9. **bye_failed.wav** - Fin négative (Not_interested)

**Format source**: N'importe quel format audio (WAV, MP3, etc.)

**Emplacement**: `/home/jokyjokeai/Desktop/MiniBotPanlev2/audio/`

### 3.2. Lancement du Setup Audio

```bash
sudo ./system/setup_audio.sh
```

**Le script effectue automatiquement:**

1. **Menu interactif d'amplification** (recommandé: +3 dB)
   ```
   🔊 AMPLIFICATION AUDIO
   ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

   Choisissez le niveau d'amplification :

     0) Aucune amplification (volume original)
     1) +3 dB  (👍 Recommandé - augmentation légère et sûre)
     2) +6 dB  (augmentation notable)
     3) +8 dB  (augmentation forte)
     4) +10 dB (augmentation très forte, risque de saturation)
     5) Normalisation automatique (volume max sans saturation)

   Votre choix [0-5] (défaut: 1):
   ```

2. **Conversion automatique** (8000 Hz mono + amplification)
3. **Copie vers Asterisk** (`/var/lib/asterisk/sounds/minibot/`)
4. **Transcription Whisper** automatique
5. **Génération de `audio_texts.json`** (transcriptions des fichiers bot)

### 3.3. Ré-amplification Rapide

Si tu veux changer l'amplification sans tout recommencer:

```bash
sudo ./system/setup_audio.sh -f
```

Le flag `-f` (force) supprime les fichiers existants et retraite tout.

### 3.4. Vérification des Fichiers

```bash
# Lister les fichiers installés
ls -lh /var/lib/asterisk/sounds/minibot/

# Vérifier la durée des fichiers
for f in /var/lib/asterisk/sounds/minibot/*.wav; do
    echo -n "$(basename $f): "
    soxi -D $f
done

# Vérifier audio_texts.json
cat audio_texts.json
```

---

## 4. Import/Export de Contacts

### 4.1. Format CSV des Contacts

**Format requis** (avec en-tête):

```csv
phone,first_name,last_name,email,company,notes
0612345678,Jean,Dupont,jean@example.com,ACME Corp,Client prioritaire
0698765432,Marie,Martin,marie@example.com,,
```

**Champs**:
- `phone` (obligatoire) - Format: 06/07/01-05/09 + 8 chiffres
- `first_name` (optionnel)
- `last_name` (optionnel)
- `email` (optionnel)
- `company` (optionnel)
- `notes` (optionnel)

### 4.2. Import de Contacts

**Syntaxe**:
```bash
python3 system/import_contacts.py <fichier.csv>
```

**Exemple**:
```bash
python3 system/import_contacts.py contacts_campagne_janvier.csv
```

**Options**:
- `--update` - Met à jour les contacts existants (par défaut: skip)
- `--clean` - Nettoie les numéros (supprime espaces, tirets, etc.)

**Exemple avec options**:
```bash
python3 system/import_contacts.py contacts.csv --update --clean
```

**Que fait l'import?**
1. Validation du format des numéros
2. Dédoublonnage automatique
3. Création en base avec status = "New"
4. Affichage du résumé (importés, doublons, erreurs)

**Sortie**:
```
========================================
  IMPORT DE CONTACTS
========================================
Fichier: contacts.csv

✅ 1250 contacts importés
⚠️  45 doublons ignorés
❌ 5 erreurs (format invalide)

📊 Résumé:
   Total en base: 1250 contacts
   Status New: 1250
```

### 4.3. Export de Contacts

**Syntaxe**:
```bash
python3 system/export_contacts.py [options]
```

**Options de filtrage**:
- `--status <status>` - Filtrer par statut
- `--campaign <campaign_id>` - Filtrer par campagne
- `--limit <N>` - Limiter à N contacts
- `--output <fichier.csv>` - Nom du fichier de sortie

**Exemples**:

```bash
# Exporter tous les contacts
python3 system/export_contacts.py

# Exporter seulement les leads
python3 system/export_contacts.py --status Leads --output leads_janvier.csv

# Exporter 500 contacts "New" (pour test)
python3 system/export_contacts.py --status New --limit 500

# Exporter les contacts d'une campagne
python3 system/export_contacts.py --campaign camp_abc12345
```

**Sortie**:
```
========================================
  EXPORT DE CONTACTS
========================================
Filtres:
   Status: Leads
   Limite: Aucune

✅ 350 contacts exportés
📄 Fichier: contacts/export_leads_2025-01-17_14h30.csv
```

**Fichier généré**:
```csv
phone,first_name,last_name,email,company,status,attempts,last_attempt,notes
0612345678,Jean,Dupont,jean@example.com,ACME,Leads,1,2025-01-15 10:30:00,Lead qualifié
```

---

## 5. Lancement de Campagnes

### 5.1. Via CLI (Recommandé pour Contrôle)

**Syntaxe**:
```bash
python3 system/launch_campaign.py [options]
```

**Options principales**:

| Option | Description | Défaut |
|--------|-------------|--------|
| `--name <nom>` | Nom de la campagne | Obligatoire |
| `--status <status>` | Filtrer contacts par statut | `New` |
| `--limit <N>` | Limiter à N contacts | Tous |
| `--campaign-id <id>` | Réutiliser une campagne existante | Nouveau |
| `--monitor` | Mode monitoring (affiche les appels en temps réel) | Désactivé |
| `--dry-run` | Simulation sans appels réels | Désactivé |

**Exemples pratiques**:

```bash
# 1. Lancer une campagne complète (tous les contacts New)
python3 system/launch_campaign.py --name "Campagne Janvier 2025"

# 2. Lancer une campagne TEST (100 contacts seulement)
python3 system/launch_campaign.py --name "Test Q1" --limit 100

# 3. Relancer les No_answer (retry)
python3 system/launch_campaign.py --name "Retry No Answer" --status No_answer --limit 500

# 4. Mode MONITORING (affiche les appels en direct)
python3 system/launch_campaign.py --name "Prod Live" --monitor

# 5. SIMULATION (dry-run - aucun appel réel)
python3 system/launch_campaign.py --name "Test Flow" --limit 10 --dry-run
```

**Sortie avec --monitor**:
```
========================================
  LANCEMENT CAMPAGNE
========================================
Nom: Campagne Janvier 2025
Statut filtre: New
Limite: Aucune

📊 Contacts trouvés: 1250
📡 Ajout à la queue...

✅ 1250 appels ajoutés à la queue
📊 Le batch_caller va les traiter automatiquement

🔴 MODE MONITORING ACTIVÉ
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Appuyez sur Ctrl+C pour arrêter le monitoring

[10:30:15] 📞 0612345678 → In Progress
[10:30:18] ✅ 0612345678 → Completed (Lead qualified)
[10:30:20] 📞 0698765432 → In Progress
[10:30:25] ❌ 0698765432 → Not Interested
...
```

### 5.2. Via API (Pour Intégrations)

**Endpoint**: `POST /campaigns/create`

**Exemple avec curl**:
```bash
curl -X POST http://localhost:8000/campaigns/create \
  -H 'Content-Type: application/json' \
  -d '{
    "name": "Campagne API Test",
    "description": "Test via API",
    "phone_numbers": ["0612345678", "0698765432"],
    "scenario": "production"
  }'
```

**Réponse**:
```json
{
  "success": true,
  "campaign_id": "camp_abc12345",
  "name": "Campagne API Test",
  "total_calls": 2,
  "queued": 2,
  "failed": 0,
  "message": "2 appels ajoutés à la queue. Le batch_caller va les traiter automatiquement."
}
```

### 5.3. Gestion de la Queue

**Voir la queue en temps réel**:
```bash
PGPASSWORD=robotpass psql -h localhost -U robot -d minibot_db -c "
SELECT id, phone_number, status, attempts, priority, created_at
FROM call_queue
WHERE status = 'pending'
ORDER BY priority DESC, created_at ASC
LIMIT 20;
"
```

**Mettre en pause une campagne**:
```bash
curl -X PATCH http://localhost:8000/campaigns/camp_abc12345/status \
  -H 'Content-Type: application/json' \
  -d '{"status": "paused"}'
```

**Reprendre une campagne**:
```bash
curl -X PATCH http://localhost:8000/campaigns/camp_abc12345/status \
  -H 'Content-Type: application/json' \
  -d '{"status": "active"}'
```

---

## 6. Monitoring & Supervision

### 6.1. Monitoring en Temps Réel

**Logs du robot (appels en cours)**:
```bash
tail -f logs/robot_ari_console.log
```

**Logs du batch caller**:
```bash
tail -f logs/batch_caller.log
```

**Script de monitoring tout-en-un**:
```bash
./monitor_logs.sh
```

Affiche en direct:
- Appels en cours
- Statuts finaux (Lead/Not_interested/No_answer)
- Erreurs éventuelles
- Statistiques en temps réel

### 6.2. Dashboard API

**URL**: `http://localhost:8000/docs`

Interface Swagger interactive pour:
- Lancer des appels individuels
- Créer des campagnes
- Consulter les statistiques
- Télécharger enregistrements/transcriptions

### 6.3. Statistiques via API

**Stats globales**:
```bash
curl http://localhost:8000/stats/summary
```

**Réponse**:
```json
{
  "total_calls": 1250,
  "completed": 1100,
  "in_progress": 5,
  "pending": 145,
  "leads": 180,
  "not_interested": 650,
  "no_answer": 270,
  "success_rate": 14.4,
  "average_duration": 125.3
}
```

**Détails d'une campagne**:
```bash
curl http://localhost:8000/campaigns/camp_abc12345
```

**Liste des appels récents**:
```bash
curl "http://localhost:8000/calls/?limit=20"
```

### 6.4. Monitoring Base de Données

**Voir les contacts par statut**:
```bash
PGPASSWORD=robotpass psql -h localhost -U robot -d minibot_db -c "
SELECT status, COUNT(*)
FROM contacts
GROUP BY status;
"
```

**Sortie**:
```
  status       | count
---------------+-------
 New           |  5420
 Leads         |   180
 Not_interested|   650
 No_answer     |   270
```

**Voir les appels du jour**:
```bash
PGPASSWORD=robotpass psql -h localhost -U robot -d minibot_db -c "
SELECT
    COUNT(*) as total,
    COUNT(CASE WHEN is_interested THEN 1 END) as leads,
    AVG(duration) as avg_duration
FROM calls
WHERE DATE(started_at) = CURRENT_DATE;
"
```

---

## 7. Gestion du Système

### 7.1. Démarrage du Système

**Script unique** (démarre tous les services):
```bash
./start_system.sh
```

**Que démarre-t-il?**
1. **robot_ari.py** - Robot principal (gère les appels ARI)
2. **main.py** - API FastAPI (port 8000)
3. **batch_caller.py** - Gestionnaire de queue

**Vérification**:
```bash
ps aux | grep -E "robot_ari|main.py|batch_caller"
```

**Logs de démarrage**:
```bash
tail -f logs/robot_ari_console.log
tail -f logs/minibot_*.log
```

### 7.2. Arrêt du Système

**Script unique** (arrête tous les services):
```bash
./stop_system.sh
```

**Que fait-il?**
1. Arrête gracieusement tous les processus
2. Attend la fin des appels en cours
3. Confirme l'arrêt complet

**Arrêt forcé** (en cas de blocage):
```bash
pkill -9 -f "robot_ari.py|main.py|batch_caller.py"
```

### 7.3. Redémarrage

```bash
./stop_system.sh && sleep 2 && ./start_system.sh
```

### 7.4. Statut des Services

```bash
# Asterisk
sudo systemctl status asterisk

# PostgreSQL
sudo systemctl status postgresql

# Processus Python
ps aux | grep -E "robot_ari|main|batch_caller"

# Ports en écoute
netstat -tlnp | grep -E "8000|8088|5432"
```

### 7.5. Désinstallation

**⚠️ ATTENTION: Supprime TOUT (Asterisk, PostgreSQL, données)**

```bash
sudo python3 system/uninstall.py
```

**Le script supprime:**
1. Asterisk et sa configuration
2. PostgreSQL et la base de données
3. Dépendances Python
4. Logs et enregistrements

**Confirmation requise** avant suppression.

---

## 8. Export de Données

### 8.1. Enregistrements Audio

**Emplacement des fichiers**:
- **Enregistrements clients**: `/var/spool/asterisk/recording/`
- **Audio assemblés (bot + client)**: `/home/jokyjokeai/Desktop/MiniBotPanlev2/assembled_audio/`

**Téléchargement via API**:
```bash
# Audio assemblé complet
curl -O http://localhost:8000/calls/assembled/full_call_assembled_1760631996.128.wav

# Enregistrement brut
curl -O http://localhost:8000/calls/recordings/prod_hello_1760631996.128.wav
```

**Export en masse**:
```bash
# Copier tous les audios assemblés
rsync -av assembled_audio/ /backup/audios_janvier_2025/
```

### 8.2. Transcriptions

**Emplacement**: `/home/jokyjokeai/Desktop/MiniBotPanlev2/transcripts/`

**Formats disponibles**:
- `transcript_{call_id}.json` - Format structuré
- `transcript_{call_id}.txt` - Format lisible

**Téléchargement via API**:
```bash
# JSON (structuré)
curl -O http://localhost:8000/calls/transcripts/1760631996.128.json

# TXT (lisible)
curl -O http://localhost:8000/calls/transcripts/1760631996.128.txt
```

**Exemple de transcript.txt**:
```
================================================================================
TRANSCRIPTION COMPLÈTE DE L'APPEL
================================================================================
Call ID: 1760631996.128
Téléphone: 0612345678
Durée: 125s
AMD: human
Sentiment final: positive
Intéressé: Oui
Date: 2025-01-17T10:30:00
================================================================================

🤖 BOT (Tour 1):
   Audio: hello.wav
   Texte: Bonjour, je suis Loïc de France Patrimoine...

👤 CLIENT (Tour 2):
   Audio: prod_hello_1760631996_128_1.wav
   Transcription: Oui, je vous écoute
   Sentiment: positive

🤖 BOT (Tour 3):
   Audio: q1.wav
   Texte: Avez-vous actuellement un livret A...

...
```

### 8.3. Export SQL des Résultats

**Export complet d'une campagne**:
```bash
PGPASSWORD=robotpass psql -h localhost -U robot -d minibot_db -c "
COPY (
    SELECT
        c.call_id,
        c.phone_number,
        c.status,
        c.amd_result,
        c.final_sentiment,
        c.is_interested,
        c.duration,
        c.started_at,
        c.ended_at,
        c.assembled_audio_path
    FROM calls c
    WHERE c.campaign_id = 'camp_abc12345'
    ORDER BY c.started_at
) TO STDOUT WITH CSV HEADER
" > campagne_abc12345_resultats.csv
```

**Export des leads uniquement**:
```bash
PGPASSWORD=robotpass psql -h localhost -U robot -d minibot_db -c "
COPY (
    SELECT
        phone,
        first_name,
        last_name,
        email,
        company,
        notes,
        last_attempt
    FROM contacts
    WHERE status = 'Leads'
    ORDER BY last_attempt DESC
) TO STDOUT WITH CSV HEADER
" > leads_qualifies.csv
```

---

## 9. Commandes Utiles & Subtilités

### 9.1. Options Subtiles de launch_campaign.py

**--monitor** : Mode monitoring en temps réel
```bash
python3 system/launch_campaign.py --name "Live Prod" --monitor
```
- Affiche les appels au fur et à mesure
- Utile pour surveiller le déroulement
- Appuyer sur Ctrl+C pour arrêter le monitoring (n'arrête PAS les appels)

**--limit** : Limiter le nombre de contacts
```bash
python3 system/launch_campaign.py --name "Test 100" --limit 100
```
- Idéal pour tests avant grosse campagne
- Prend les N premiers contacts du filtre

**--dry-run** : Simulation sans appels
```bash
python3 system/launch_campaign.py --name "Simulation" --dry-run --limit 10
```
- Ne lance AUCUN appel réel
- Affiche juste ce qui serait fait
- Parfait pour vérifier la sélection de contacts

**--status** : Filtrer par statut de contact
```bash
# Retry sur les No_answer
python3 system/launch_campaign.py --name "Retry" --status No_answer

# Relancer les Not_interested (attention!)
python3 system/launch_campaign.py --name "Retry NI" --status Not_interested --limit 50
```

**Combinaisons utiles**:
```bash
# Test sur 50 nouveaux contacts en monitoring
python3 system/launch_campaign.py \
  --name "Test Monitoring" \
  --status New \
  --limit 50 \
  --monitor

# Simulation de retry sur 100 No_answer
python3 system/launch_campaign.py \
  --name "Simulation Retry" \
  --status No_answer \
  --limit 100 \
  --dry-run
```

### 9.2. Nettoyage des Enregistrements

**Script automatique** (supprime enregistrements > 30 jours):
```bash
sudo ./system/cleanup_recordings.sh
```

**Nettoyage manuel**:
```bash
# Supprimer enregistrements > 7 jours
find /var/spool/asterisk/recording/ -type f -mtime +7 -delete

# Supprimer audios assemblés > 30 jours
find assembled_audio/ -type f -mtime +30 -delete
```

### 9.3. Backup Base de Données

**Backup complet**:
```bash
PGPASSWORD=robotpass pg_dump -h localhost -U robot minibot_db > backup_$(date +%Y%m%d).sql
```

**Backup sélectif (seulement contacts et calls)**:
```bash
PGPASSWORD=robotpass pg_dump -h localhost -U robot -t contacts -t calls minibot_db > backup_contacts_calls.sql
```

**Restauration**:
```bash
PGPASSWORD=robotpass psql -h localhost -U robot minibot_db < backup_20250117.sql
```

### 9.4. Vider la Queue d'Appels

**Supprimer tous les appels en attente**:
```bash
PGPASSWORD=robotpass psql -h localhost -U robot -d minibot_db -c "
DELETE FROM call_queue WHERE status = 'pending';
"
```

**Supprimer appels d'une campagne spécifique**:
```bash
PGPASSWORD=robotpass psql -h localhost -U robot -d minibot_db -c "
DELETE FROM call_queue
WHERE campaign_id = 'camp_abc12345' AND status = 'pending';
"
```

### 9.5. Réinitialiser Statut des Contacts

**Remettre tous les contacts en "New"** (⚠️ ATTENTION):
```bash
PGPASSWORD=robotpass psql -h localhost -U robot -d minibot_db -c "
UPDATE contacts SET status = 'New', attempts = 0, last_attempt = NULL;
"
```

**Remettre seulement les "No_answer" en "New"**:
```bash
PGPASSWORD=robotpass psql -h localhost -U robot -d minibot_db -c "
UPDATE contacts
SET status = 'New', attempts = 0, last_attempt = NULL
WHERE status = 'No_answer';
"
```

### 9.6. Test d'Appel Unique

**Via API**:
```bash
curl -X POST http://localhost:8000/calls/launch \
  -H 'Content-Type: application/json' \
  -d '{"phone_number":"0612345678","scenario":"production"}'
```

**Réponse**:
```json
{
  "success": true,
  "call_id": "1760631996.128",
  "phone_number": "0612345678",
  "scenario": "production"
}
```

**Suivre l'appel en temps réel**:
```bash
tail -f logs/robot_ari_console.log | grep "1760631996.128"
```

---

## 10. Troubleshooting

### 10.1. Problèmes Courants

#### ❌ "Failed to connect to ARI"

**Causes**:
- Asterisk non démarré
- Mauvais identifiants ARI

**Solutions**:
```bash
# Vérifier Asterisk
sudo systemctl status asterisk

# Redémarrer Asterisk
sudo systemctl restart asterisk

# Tester connexion ARI
curl -u robot:j1B2MMrloXdddx60 http://localhost:8088/ari/asterisk/info
```

#### ❌ "Database connection failed"

**Causes**:
- PostgreSQL non démarré
- Mauvais credentials

**Solutions**:
```bash
# Vérifier PostgreSQL
sudo systemctl status postgresql

# Tester connexion
PGPASSWORD=robotpass psql -h localhost -U robot -d minibot_db -c "SELECT 1;"

# Vérifier config.py
grep DATABASE_URL config.py
```

#### ❌ "No audio files found"

**Cause**: Fichiers audio non configurés

**Solution**:
```bash
# Vérifier présence des fichiers
ls -lh /var/lib/asterisk/sounds/minibot/

# Si vides, relancer setup_audio.sh
sudo ./system/setup_audio.sh
```

#### ❌ Appels ne se lancent pas

**Causes possibles**:
1. Batch caller non démarré
2. Queue vide
3. Campagne en pause

**Diagnostic**:
```bash
# Vérifier batch_caller
ps aux | grep batch_caller

# Vérifier queue
PGPASSWORD=robotpass psql -h localhost -U robot -d minibot_db -c "
SELECT status, COUNT(*) FROM call_queue GROUP BY status;
"

# Vérifier campagnes
curl http://localhost:8000/campaigns/
```

#### ❌ Audio coupé trop tôt

**Cause**: Temps d'écoute trop court

**Solution**: Modifier `LISTEN_TIMEOUTS` dans `scenarios.py`
```python
"hello": {
    "wait_before_stop": 12  # Augmente de 8 à 12 secondes
},
```

### 10.2. Logs Importants

| Fichier | Contenu |
|---------|---------|
| `logs/robot_ari_console.log` | Appels en temps réel, erreurs ARI |
| `logs/batch_caller.log` | Queue, throttling, erreurs batch |
| `logs/minibot_YYYYMMDD.log` | Logs généraux datés |
| `/var/log/asterisk/full` | Logs Asterisk détaillés |
| `/var/log/postgresql/*.log` | Logs PostgreSQL |

### 10.3. Commandes de Debug

**Verbose Asterisk** (logs détaillés):
```bash
sudo asterisk -rvvvv
```

**Tester scénario manuellement**:
```bash
python3 << EOF
from robot_ari import RobotARI
from scenarios import scenario_production

# Code de test...
EOF
```

**Vérifier Whisper**:
```bash
python3 -c "from services.whisper_service import whisper_service; print('OK')"
```

**Vérifier dépendances**:
```bash
pip3 list | grep -E "fastapi|sqlalchemy|asyncari|faster-whisper"
```

---

## 📞 Support

Pour toute question ou problème:

1. Consulter les logs (section 10.2)
2. Vérifier `read/VERIFICATION_INSTALL.md`
3. Consulter `read/SYSTEME_QUEUE.md` pour la gestion de queue
4. Consulter `read/CONFIGURATION_CALLER_ID.md` pour le caller ID

---

**Dernière mise à jour**: 2025-01-17
**Version du système**: MiniBotPanel v2
**Auteur**: Équipe MiniBotPanel
