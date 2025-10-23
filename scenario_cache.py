#!/usr/bin/env python3
"""
Cache et pré-validation des scénarios avec TTS Voice Cloning
"""

import os
import json
import importlib.util
from pathlib import Path
from logger_config import get_logger

logger = get_logger(__name__)

class ScenarioManager:
    """Gère le pré-chargement et la validation des scénarios avec TTS"""

    def __init__(self):
        self.scenarios_loaded = {}
        self.tts_embeddings_cache = {}
        self.scenario_configs = {}
        self.audio_dependencies = {
            "production": ["hello.wav", "retry.wav", "q1.wav", "q2.wav", "q3.wav", "is_leads.wav", "confirm.wav", "bye_success.wav", "bye_failed.wav"],
            "test": ["test_audio.wav"]
        }

    def preload_single_scenario(self):
        """Pré-charge LE scénario unique (optimisé pour un seul scénario)"""
        logger.info("=" * 60)
        logger.info("🎭 PRÉ-CHARGEMENT SCÉNARIO UNIQUE")
        logger.info("=" * 60)

        try:
            # 1. Auto-détection du scénario actif (priorité : généré > streaming > fallback)
            active_scenario_func, scenario_name, tts_config = self._detect_active_scenario()
            
            if not active_scenario_func:
                logger.error("❌ Aucun scénario détecté")
                return False
            
            # 2. Chargement en mémoire (UN SEUL)
            self.active_scenario = active_scenario_func
            self.scenario_name = scenario_name
            self.tts_config = tts_config
            
            # 3. Préchargement TTS embeddings si disponibles
            self._preload_tts_embeddings()
            
            logger.info(f"✅ Scénario unique '{scenario_name}' préchargé en cache")
            logger.info(f"   Fonction: {active_scenario_func.__name__}")
            if self.tts_config:
                logger.info(f"   TTS Config: {self.tts_config.get('personality_type', 'default')}")
            
            return True

        except Exception as e:
            logger.error(f"❌ Erreur préchargement scénario: {e}")
            return self._fallback_scenario()

    def _detect_active_scenario(self):
        """Détecte automatiquement LE scénario à utiliser (priorité logique)"""

        # PRIORITÉ 1: Scénario généré le plus récent (scenarios/*/scenario.py)
        scenarios_dir = Path(__file__).parent / "scenarios"
        if scenarios_dir.exists():
            generated_scenarios = []
            for scenario_path in scenarios_dir.iterdir():
                if scenario_path.is_dir():
                    scenario_file = scenario_path / f"{scenario_path.name}_scenario.py"
                    config_file = scenario_path / f"{scenario_path.name}_config.json"
                    if scenario_file.exists():
                        generated_scenarios.append((scenario_path, scenario_file, config_file))
            
            if generated_scenarios:
                # Prendre le plus récent
                latest_scenario = max(generated_scenarios, key=lambda x: x[1].stat().st_mtime)
                scenario_path, scenario_file, config_file = latest_scenario
                
                logger.info(f"🎯 Scénario généré détecté: {scenario_path.name}")
                
                # Charger dynamiquement
                scenario_func = self._load_generated_scenario(scenario_file)
                tts_config = self._load_tts_config(config_file) if config_file.exists() else None
                
                return scenario_func, scenario_path.name, tts_config
        
        # PRIORITÉ 2: Scénario streaming classique
        try:
            from scenarios_streaming import scenario_production_streaming
            logger.info("🌊 Utilisation scénario streaming classique")
            return scenario_production_streaming, "streaming_production", None
        except ImportError:
            pass
        
        # PRIORITÉ 3: Fallback scénario de base (supprimé - scenarios.py n'existe plus)
        # Ancien code supprimé car scenarios.py n'existe plus depuis refactoring
        
        return None, None, None

    def _load_generated_scenario(self, scenario_file):
        """Charge dynamiquement un scénario généré"""
        import importlib.util
        
        spec = importlib.util.spec_from_file_location("generated_scenario", scenario_file)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        
        # Trouver la fonction scénario principal
        for attr_name in dir(module):
            attr = getattr(module, attr_name)
            if callable(attr) and attr_name.startswith('scenario_'):
                return attr
        
        raise Exception(f"Aucune fonction scenario_ trouvée dans {scenario_file}")

    def _load_tts_config(self, config_file):
        """Charge la configuration TTS depuis le fichier config.json"""
        try:
            with open(config_file, 'r', encoding='utf-8') as f:
                config = json.load(f)
            return config.get('tts_voice_config', {})
        except Exception as e:
            logger.warning(f"⚠️ Config TTS non chargée: {e}")
            return {}

    def _preload_tts_embeddings(self):
        """Précharge les embeddings TTS pour le scénario actif"""
        if not self.tts_config:
            self.voice_embedding = None
            return
        
        try:
            # Importer le service TTS
            from services.tts_voice_clone import VoiceCloneService
            
            voice_service = VoiceCloneService()
            personality = self.tts_config.get('personality_type', 'Professionnel et rassurant')
            
            # Précharger l'embedding pour cette personnalité
            self.voice_embedding = voice_service.get_voice_embedding(personality)
            logger.info(f"✅ Voice embedding préchargé: {personality}")
            
        except Exception as e:
            logger.warning(f"⚠️ Embeddings TTS non préchargés: {e}")
            self.voice_embedding = None

    def _fallback_scenario(self):
        """Scénario de fallback minimal"""
        logger.warning("🆘 Utilisation fallback scenario minimal")
        
        def fallback_scenario_func():
            return {
                "message": "Bonjour, je suis un assistant vocal en mode fallback.",
                "next_step": "end"
            }
        
        self.active_scenario = fallback_scenario_func
        self.scenario_name = "fallback"
        self.tts_config = {}
        self.voice_embedding = None
        
        return True

    # ========== API LOOKUP ULTRA-RAPIDE ==========
    
    def get_scenario(self, name=None):
        """Retourne LE scénario unique (lookup instantané, ignore name)"""
        return self.active_scenario

    def get_scenario_name(self):
        """Retourne le nom du scénario actif (lookup instantané)"""
        return getattr(self, 'scenario_name', 'unknown')

    def get_tts_config(self):
        """Retourne la config TTS (lookup instantané)"""
        return getattr(self, 'tts_config', {})

    def get_voice_embedding(self):
        """Retourne l'embedding voix préchargé (lookup instantané)"""
        return getattr(self, 'voice_embedding', None)

    def is_ready(self):
        """Vérifie si le cache est prêt (lookup instantané)"""
        return hasattr(self, 'active_scenario') and self.active_scenario is not None

    def get_cache_info(self):
        """Retourne les infos du cache pour debug (lookup instantané)"""
        return {
            'scenario_name': getattr(self, 'scenario_name', None),
            'has_tts_config': bool(getattr(self, 'tts_config', {})),
            'has_voice_embedding': getattr(self, 'voice_embedding', None) is not None,
            'is_ready': self.is_ready()
        }

# Instance globale
scenario_manager = ScenarioManager()

if __name__ == "__main__":
    # Test standalone
    scenario_manager.preload_single_scenario()