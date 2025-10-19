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
            "production": ["hello.wav", "retry.wav", "q1.wav", "q2.wav", "q3.wav", "is_leads.wav", "confirm.wav", "bye_success.wav", "bye_failed.wav"]
        }

    def preload_scenarios(self):
        """Pré-charge le scénario PRODUCTION (unique scénario actif)"""
        logger.info("=" * 60)
        logger.info("📝 PRÉ-CHARGEMENT DU SCÉNARIO PRODUCTION")
        logger.info("=" * 60)

        try:
            from scenarios import scenario_production

            # Stocker uniquement scenario_production
            self.scenarios_loaded = {
                "production": scenario_production
            }

            for name, func in self.scenarios_loaded.items():
                logger.info(f"✅ Scénario '{name}' chargé: {func.__name__}")

                # Vérifier les dépendances audio
                required_audio = self.audio_dependencies.get(name, [])
                logger.info(f"   Audio requis: {', '.join(required_audio)}")

            logger.info(f"📊 Scénario PRODUCTION prêt à l'emploi")
            return True

        except Exception as e:
            logger.error(f"❌ Erreur chargement scénario: {e}")
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