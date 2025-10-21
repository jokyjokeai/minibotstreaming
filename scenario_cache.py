#!/usr/bin/env python3
"""
Cache et pré-validation des scénarios
"""

from logger_config import get_logger

logger = get_logger(__name__)

class ScenarioManager:
    """Gère le pré-chargement et la validation des scénarios"""

    def __init__(self):
        self.scenarios_loaded = {}
        self.audio_dependencies = {
            "production": ["hello.wav", "retry.wav", "q1.wav", "q2.wav", "q3.wav", "is_leads.wav", "confirm.wav", "bye_success.wav", "bye_failed.wav"],
            "test": ["test_audio.wav"]
        }

    def preload_scenarios(self):
        """Pré-charge les scénarios STREAMING (architecture 100% streaming)"""
        logger.info("=" * 60)
        logger.info("🌊 PRÉ-CHARGEMENT DES SCÉNARIOS STREAMING")
        logger.info("=" * 60)

        try:
            # Importer scénarios streaming
            from scenarios_streaming import scenario_production_streaming, scenario_test_streaming

            # Stocker scénarios streaming
            self.scenarios_loaded = {
                "production": scenario_production_streaming,
                "test": scenario_test_streaming
            }

            for name, func in self.scenarios_loaded.items():
                logger.info(f"✅ Scénario streaming '{name}' chargé: {func.__name__}")

                # Vérifier les dépendances audio
                required_audio = self.audio_dependencies.get(name, [])
                if required_audio:
                    logger.info(f"   Audio requis: {', '.join(required_audio)}")

            logger.info(f"📊 Scénarios STREAMING prêts (architecture temps réel)")
            return True

        except Exception as e:
            logger.error(f"❌ Erreur chargement scénarios streaming: {e}")
            # Fallback sur anciens scénarios si disponibles
            try:
                from scenarios import scenario_production
                self.scenarios_loaded = {"production": scenario_production}
                logger.warning("⚠️ Fallback sur scénarios classiques")
                return True
            except:
                logger.error("❌ Aucun scénario disponible")
                return False

    def get_scenario(self, name):
        """Retourne la fonction scénario depuis le cache"""
        scenario = self.scenarios_loaded.get(name)
        if not scenario:
            logger.warning(f"⚠️  Scénario '{name}' non trouvé, utilisation de 'production'")
            return self.scenarios_loaded.get("production")
        return scenario

    # Plus besoin de validation - les fichiers sont gérés par setup_audio.sh

# Instance globale
scenario_manager = ScenarioManager()

if __name__ == "__main__":
    # Test standalone
    scenario_manager.preload_scenarios()