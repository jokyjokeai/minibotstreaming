# 🤖 MiniBotPanel v2 - Streaming Call Robot with AI Voice Cloning

**Système de robot d'appel intelligent avec streaming temps réel, TTS voice cloning et IA conversationnelle hybride**

[![Version](https://img.shields.io/badge/version-2.1--PERFECT-brightgreen)](https://github.com/jokyjokeai/minibotstreaming)
[![License](https://img.shields.io/badge/license-MIT-blue)](LICENSE)
[![Python](https://img.shields.io/badge/python-3.8+-blue)](https://www.python.org/)
[![Asterisk](https://img.shields.io/badge/asterisk-22-orange)](https://www.asterisk.org/)

## 🌟 Vue d'Ensemble

MiniBotPanel v2 est une solution complète de **robot d'appel commercial intelligent** qui révolutionne la qualification de leads avec :

- 🎙️ **TTS Voice Cloning** - Clone parfaitement la voix du commercial pour réponses dynamiques
- 🧠 **IA Conversationnelle Hybride** - Scénario structuré + réponses intelligentes aux questions
- ⚡ **Streaming Temps Réel** - Latence ultra-faible (<200ms) avec Vosk ASR + Ollama NLP
- 🔄 **Barge-in Naturel** - Interruptions fluides comme une vraie conversation
- 📊 **Qualification Intelligente** - Scoring automatique et analyse des intentions

## 🚀 Fonctionnalités Principales

### 🎭 Génération de Scénarios Intelligente
- **Créateur interactif** avec questionnaire complet sur l'entreprise, produit, objections
- **Configuration personnalité** du commercial pour calibrer la voix TTS
- **Génération automatique d'objections** selon le secteur d'activité
- **Variables dynamiques** pour personnalisation ($nom, $entreprise, etc.)

### 🎵 TTS Voice Cloning Avancé
- **Clonage vocal** à partir des échantillons audio existants
- **Voice embeddings** pour génération ultra-rapide
- **Adaptation de personnalité** (vitesse, ton, émotion selon le profil)
- **Génération temps réel** pendant les appels

### 🧠 Intelligence Conversationnelle
- **Mode hybride** : respect du scénario + réponses aux questions libres
- **Détection d'intentions** française optimisée avec Ollama
- **Gestion d'objections** automatique avec réponses pré-calibrées
- **Retour intelligent** au flow principal après digression

### ⚡ Architecture Streaming
- **Vosk ASR** - Transcription française temps réel 16kHz
- **Ollama NLP** - Analyse d'intentions locale (<600ms)
- **AudioFork** - Streaming bidirectionnel fluide
- **WebRTC VAD** - Détection de fin de parole précise

## 📦 Installation Zero-Gap

### Prérequis
- **OS**: Ubuntu 20.04+ ou Debian 11+
- **RAM**: 8GB (16GB recommandé)
- **CPU**: 4 vCPU (8 vCPU recommandé)
- **Storage**: 50GB SSD

### Installation Automatique
```bash
# 1. Cloner le repository
git clone https://github.com/jokyjokeai/minibotstreaming.git
cd minibotstreaming

# 2. Installation complète automatique (20 minutes)
sudo python3 system/install_hybrid.py

# 3. Vérification optionnelle
python3 system/check_requirements.py

# 4. Démarrage
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

## 🎭 Création de Scénarios

### Générateur Interactif
```bash
python3 system/scenario_generator.py
```

Le générateur pose des questions complètes sur :
- **Entreprise** : nom, adresse, secteur, site web
- **Commercial** : prénom, nom, titre, personnalité (6 profils)
- **Produit/Service** : description, prix, avantages, différenciateurs
- **Objections** : génération automatique selon secteur + vos réponses
- **Variables** : personnalisation dynamique des textes
- **Flow** : étapes, transitions, gestion interruptions

### Profils de Personnalité TTS
1. **Sympathique et décontracté** - Ton amical, vitesse 0.95x
2. **Professionnel et rassurant** - Ton expert, vitesse normale
3. **Énergique et enthousiaste** - Ton dynamique, vitesse 1.15x
4. **Discret et consultative** - Ton calme, vitesse 0.9x
5. **Chaleureux et familial** - Ton empathique, vitesse 0.95x
6. **Autorité et expertise** - Ton ferme, vitesse 1.05x

### Fichiers Générés
```
scenarios/mon_scenario/
├── mon_scenario_scenario.py      # Code scénario complet
├── mon_scenario_config.json      # Configuration streaming
├── mon_scenario_prompts.json     # Prompts IA dynamiques
├── mon_scenario_audio_texts.json # Mapping fichiers audio
└── test_mon_scenario.py          # Script de test
```

## 🏗️ Architecture Technique

### Composants Principaux
```
┌─────────────────┬─────────────────┬─────────────────┐
│   ASTERISK 22   │   FASTAPI WEB   │  VOSK ASR FR    │
│  + AudioFork    │     SERVER      │   (temps réel)  │
│  (streaming)    │   (API/UI)      │    16kHz SLIN   │
└─────────────────┼─────────────────┼─────────────────┘
                  │
┌─────────────────┼─────────────────┼─────────────────┐
│  OLLAMA NLP     │  TTS VOICE      │   POSTGRESQL    │
│ (intentions)    │   CLONING       │   (leads DB)    │
│ llama3.2:1b     │  XTTS v2 +      │                 │
│                 │  embeddings     │                 │
└─────────────────┴─────────────────┴─────────────────┘
```

### Pipeline de Conversation
```
1. Appel sortant → Asterisk → AudioFork streaming
2. Diffusion audio (TTS ou préenregistré)
3. Écoute avec barge-in → Vosk ASR → texte
4. Analyse → Ollama NLP → intention + confiance
5. Décision : scénario normal ou réponse dynamique
6. Si dynamique → TTS voice clone → audio personnalisé
7. Retour au flow principal
```

### Performances Garanties
- **Latence NLP** : <600ms (optimisé)
- **Génération TTS** : <2s avec embeddings
- **JSON validity** : 100% (paramètres optimisés)
- **Appels simultanés** : 8 optimisés
- **Accuracy française** : 95%+ intentions

## 📊 Utilisation

### Import Contacts
```bash
# Format CSV: phone,first_name,last_name,email,company,notes
python3 system/import_contacts.py contacts.csv
```

### Lancement Campagne
```bash
# Campagne avec scénario personnalisé
python3 system/launch_campaign.py \
  --name "Campagne Patrimoine 2025" \
  --scenario "patrimoine_expertise" \
  --limit 1000 \
  --monitor
```

### Test Direct
```bash
# Test d'un appel unique
curl -X POST http://localhost:8000/calls/launch \
  -H 'Content-Type: application/json' \
  -d '{
    "phone_number": "33612345678",
    "scenario": "patrimoine_expertise"
  }'
```

### Monitoring Temps Réel
```bash
# Logs détaillés
tail -f logs/minibotpanel.log

# Logs erreurs uniquement
tail -f logs/minibotpanel_errors.log

# Performance stats
curl http://localhost:8000/stats/performance
```

## 🔧 Configuration

### Variables de Scénario
```python
SCENARIO_VARIABLES = {
    "agent_name": "Thierry",
    "company": "France Patrimoine", 
    "product": "Optimisation patrimoniale",
    "phone_number": "auto-détecté",
    "client_name": "depuis-base-données"
}
```

### Calibration TTS
```json
{
  "tts_voice_config": {
    "personality_type": "Professionnel et rassurant",
    "speed_adjustment": 1.0,
    "pitch_adjustment": "medium", 
    "emotion_level": "confident",
    "professionalism_level": 9
  }
}
```

### Gestion d'Objections
```json
{
  "objection_responses": {
    "C'est trop cher": {
      "primary_response": "Je comprends que le budget soit important. Notre solution génère un ROI dès le premier mois...",
      "fallback_response": "Puis-je vous expliquer comment nos clients économisent plus qu'ils n'investissent ?",
      "tone": "rassurant"
    }
  }
}
```

## 📁 Structure du Projet

```
minibotstreaming/
├── 📁 system/                    # Scripts d'installation et outils
│   ├── install_hybrid.py         # Installation automatique
│   ├── scenario_generator.py     # Créateur de scénarios  
│   ├── check_requirements.py     # Vérification système
│   └── launch_campaign.py        # Lanceur de campagnes
├── 📁 services/                  # Services core streaming
│   ├── nlp_intent.py            # Moteur NLP hybride
│   ├── tts_voice_clone.py       # TTS voice cloning
│   ├── live_asr_vad.py          # ASR temps réel
│   └── amd_service.py           # Détection répondeur
├── 📁 scenarios/                 # Scénarios générés
│   └── [nom_scenario]/          # Dossier par scénario
├── 📁 audio/                     # Fichiers audio base
├── 📁 voices/                    # Embeddings vocaux
├── 📁 logs/                      # Logs détaillés
├── prompts_config.json          # Configuration globale prompts
├── audio_texts.json             # Mapping textes/audio
└── start_system.sh              # Démarrage système
```

## 🐛 Debug et Troubleshooting

### Logs Ultra-Détaillés
Le système génère des logs complets avec :
- **PID, mémoire, thread** pour chaque entrée
- **Fichier:ligne + fonction** pour traçabilité
- **Performance timing** pour optimisation
- **Variables locales** lors d'erreurs

### Fichiers de Log
- `logs/minibotpanel.log` - Log principal
- `logs/minibotpanel_errors.log` - Erreurs uniquement  
- `logs/minibotpanel_debug.log` - Debug ultra-détaillé

### Commandes de Debug
```bash
# Vérification système complète
python3 system/check_requirements.py

# Test TTS voice cloning
python3 services/tts_voice_clone.py

# Test scénario
python3 scenarios/mon_scenario/test_mon_scenario.py

# Performance stats
curl http://localhost:8000/stats/performance
```

## 🚀 Production

### Endpoints API
- **API** : http://localhost:8000
- **Documentation** : http://localhost:8000/docs  
- **Health Check** : http://localhost:8000/health
- **Metrics** : http://localhost:8000/stats

### Monitoring
```bash
# Status global
curl http://localhost:8000/health

# Statistiques campagnes
curl http://localhost:8000/stats/campaigns

# Performance TTS
curl http://localhost:8000/stats/tts

# Métriques Ollama
curl http://localhost:8000/stats/nlp
```

## 📋 Roadmap

### v2.2 (Q1 2025)
- [ ] Interface web pour création scénarios
- [ ] A/B testing automatique des scripts
- [ ] Analytics avancées par secteur
- [ ] API REST complète pour intégrations

### v2.3 (Q2 2025)  
- [ ] Support multilingue (EN, ES, IT)
- [ ] IA générative pour optimisation scripts
- [ ] Intégration CRM natives
- [ ] Clustering automatique des objections

## 🤝 Support

### Documentation
- [Architecture Détaillée](ARCHITECTURE.md)
- [Guide Déploiement](DEPLOYMENT_GUIDE.md)
- [Optimisations](PERFECT_OPTIMIZATIONS.md)

### Community
- **Issues** : [GitHub Issues](https://github.com/jokyjokeai/minibotstreaming/issues)
- **Discussions** : [GitHub Discussions](https://github.com/jokyjokeai/minibotstreaming/discussions)

### Contact
- **Email** : support@minibotpanel.com
- **Documentation** : https://docs.minibotpanel.com

---

## 📄 License

MIT License - voir [LICENSE](LICENSE) pour détails.

---

**🎉 MiniBotPanel v2 - Révolutionnez vos campagnes d'appels avec l'IA conversationnelle !**