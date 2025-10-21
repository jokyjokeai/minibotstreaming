# Architecture MiniBotPanel v2 - Streaming Only

## Vue d'ensemble

MiniBotPanel v2 est une plateforme d'IA conversationnelle 100% streaming conçue pour les campagnes d'appels automatisées avec une qualité téléphonique professionnelle et des capacités de barge-in naturelles.

## Architecture Streaming Temps Réel

```
┌─────────────────────────────────────────────────────────────────┐
│                    ARCHITECTURE STREAMING                       │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  📞 APPEL ──► AudioFork ──► Vosk ASR ──► Ollama NLP ──► Actions │
│      │            │            │            │                   │
│      │            │            │            └─► Intent Analysis │
│      │            │            └─► Real-time transcription      │
│      │            └─► 16kHz SLIN16 streaming                   │
│      └─► Asterisk 22 + Hybrid AMD                              │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

## Composants Principaux

### 1. Asterisk 22 + AudioFork
- **Rôle** : Gestionnaire d'appels avec streaming audio temps réel
- **Format** : SLIN16 16kHz mono optimisé pour le streaming
- **Fonctionnalités** :
  - Hybrid AMD (Answering Machine Detection)
  - AudioFork pour streaming bidirectionnel
  - Barge-in naturel (interruption conversationnelle)
  - Gestion des silences et pauses

### 2. Vosk ASR (Speech-to-Text)
- **Rôle** : Reconnaissance vocale française temps réel
- **Modèle** : `vosk-model-fr-0.22` (160MB optimisé)
- **Performance** : <100ms latence, 95%+ précision
- **Intégration** : Via WebSocket avec AudioFork

### 3. Ollama NLP (Natural Language Processing)
- **Rôle** : Analyse d'intention et génération de réponses
- **Modèles** : Llama 3.2 local (3B/1B parameters)
- **Capacités** :
  - Intent classification temps réel
  - Détection sentiment/émotion
  - Analyse qualification leads
  - Fallback keywords si indisponible

### 4. Robot ARI Hybrid
- **Fichier** : `robot_ari_hybrid.py`
- **Rôle** : Orchestrateur principal des conversations
- **Fonctionnalités** :
  - Gestion état conversationnel
  - Routage intelligent des intentions
  - Logique de qualification automatique
  - Streaming bidirectionnel coordonné

## Architecture Technique

### Base de Données (PostgreSQL)
```sql
-- Tables principales streaming
contacts         # Prospects et leads
campaigns        # Campagnes d'appels
call_queue       # File d'attente streaming
calls            # Historique appels avec transcriptions
conversations    # Logs conversationnels détaillés
```

### Services Core

#### AudioFork Integration
```python
# services/audiofork_service.py
class AudioForkService:
    def start_streaming(self, call_id):
        # Initialise streaming bidirectionnel
        # Format: SLIN16 16kHz
        # Latence: <50ms
```

#### Vosk Transcription Service
```python
# services/vosk_service.py
class VoskTranscriptionService:
    def process_audio_stream(self, audio_chunk):
        # Transcription temps réel
        # Détection silence/parole
        # Gestion barge-in
```

#### Ollama NLP Service
```python
# services/nlp_intent.py
class NLPIntentService:
    def analyze_intent_realtime(self, text, context):
        # Classification intention instantanée
        # Analyse sentiment contextuelle
        # Qualification automatique leads
```

## Flux de Données Streaming

### 1. Initialisation Appel
```
Asterisk ──► AudioFork ──► WebSocket ──► Vosk ──► Robot ARI
    │                                        │
    └─► AMD Hybrid ─────────────────────────►┘
```

### 2. Conversation Streaming
```
Audio Input ──► Vosk ──► Text ──► Ollama ──► Intent ──► Action
     │                                          │
     └─► VAD ──► Silence Detection ─────────────┘
```

### 3. Barge-in Management
```
User Speech ──► VAD ──► Interrupt Signal ──► Stop Bot ──► Listen
```

## Scénarios Conversationnels

### Scénario Production (Unique)
```python
# scenarios_streaming.py
SCENARIO_STEPS = {
    "hello": "Présentation + demande permission",
    "q1": "Question patrimoine (livret A, PEL, assurance-vie)",
    "q2": "Question inflation vs rendement",
    "q3": "Question satisfaction conseiller bancaire",
    "qualify": "Analyse automatique qualification",
    "closing": "Prise RDV ou fin courtoise"
}
```

### États Conversationnels
- `hello` → Accueil et présentation
- `listening` → Écoute active utilisateur
- `processing` → Analyse NLP intention
- `responding` → Génération réponse appropriée
- `qualifying` → Évaluation automatique lead
- `closing` → Finalisation conversation

## Optimisations Performance

### Audio Streaming
- **Format** : SLIN16 16kHz (optimal streaming/qualité)
- **Chunks** : 160ms pour réactivité
- **VAD** : WebRTC VAD pour détection parole
- **Latence totale** : <200ms (inaudible)

### NLP Streaming
- **Cache** : Intentions fréquentes en mémoire
- **Fallback** : Keywords si Ollama indisponible
- **Batch** : Traitement par chunks 50-100 tokens

### Base de Données
- **Index** : Colonnes critiques (phone, campaign_id, status)
- **Connexions** : Pool optimisé (max 20 connexions)
- **Logs** : Rotation automatique (max 100MB)

## Monitoring et Observabilité

### Métriques Temps Réel
- Latence transcription (target: <100ms)
- Précision ASR (target: >95%)
- Taux qualification leads
- Concurrence appels actifs
- Taux succès/échec appels

### Logs Structurés
```python
# Logs par appel avec contexte complet
{
    "call_id": "unique_id",
    "timestamp": "2024-10-21T10:30:00Z",
    "event": "intent_detected",
    "intent": "interested",
    "confidence": 0.92,
    "latency_ms": 85
}
```

### Health Checks
- `/health` → Status général système
- `/health/vosk` → Status ASR
- `/health/ollama` → Status NLP
- `/health/asterisk` → Status téléphonie

## Sécurité et Compliance

### Données Personnelles
- Chiffrement au repos (PostgreSQL + SSL)
- Logs anonymisés (pas de numéros complets)
- Rétention configurable (RGPD compliant)
- Purge automatique anciens enregistrements

### Accès et Authentification
- API JWT tokens
- Rate limiting par IP
- Logs accès détaillés
- Permissions granulaires

## Déploiement et Scalabilité

### Requirements Système
- **CPU** : 4+ cores (Ollama + Vosk parallèles)
- **RAM** : 8GB+ (modèles NLP en mémoire)
- **Stockage** : 50GB+ SSD (performances I/O)
- **Réseau** : 100Mbps+ (streaming qualité)

### Architecture Multi-Instance
```
Load Balancer ──► Instance 1 (Vosk + Ollama + Asterisk)
              ├─► Instance 2 (Vosk + Ollama + Asterisk)
              └─► Instance N (Vosk + Ollama + Asterisk)
                      │
                PostgreSQL Cluster (Master/Slave)
```

### Monitoring Production
- Prometheus + Grafana metrics
- ELK Stack pour logs centralisés
- Alertes temps réel (PagerDuty/Slack)
- Backup automatique BDD (daily)

## Évolutions Futures

### Améliorations Prévues
- Modèles Vosk multilingues
- Ollama modèles spécialisés métier
- Interface admin temps réel
- Analytics predictives qualification

### Intégrations Possibles
- CRM externes (Salesforce, HubSpot)
- Systèmes téléphonie cloud (Twilio)
- Solutions callback automatiques
- Reporting avancé (PowerBI, Tableau)

---

**Architecture 100% streaming - Latence minimale - Qualification intelligente**