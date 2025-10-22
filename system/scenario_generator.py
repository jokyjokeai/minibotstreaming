#!/usr/bin/env python3
"""
Générateur de Scénarios Interactif - MiniBotPanel v2
Créateur de scénarios d'appel avec flow complet, variables dynamiques et barge-in
"""

import os
import sys
import json
import re
from pathlib import Path
from typing import Dict, List, Any, Optional
from datetime import datetime

# Ajouter le répertoire parent au PYTHONPATH pour les imports
current_dir = Path(__file__).parent
parent_dir = current_dir.parent
sys.path.insert(0, str(parent_dir))

try:
    from logger_config import get_logger, log_function_call
except ImportError:
    # Fallback simple si logger_config n'est pas disponible
    import logging
    def get_logger(name):
        return logging.getLogger(name)
    def log_function_call(func):
        return func

logger = get_logger(__name__)

class Colors:
    GREEN = '\033[92m'
    RED = '\033[91m'
    YELLOW = '\033[93m'
    BLUE = '\033[94m'
    CYAN = '\033[96m'
    PURPLE = '\033[95m'
    NC = '\033[0m'
    BOLD = '\033[1m'

class ScenarioStep:
    """Représente une étape du scénario"""
    
    def __init__(self, step_id: str, step_type: str):
        self.step_id = step_id
        self.step_type = step_type  # intro, question, confirmation, objection, end
        self.audio_file = ""
        self.text_content = ""
        self.variables = []
        self.max_wait_seconds = 10.0
        self.barge_in_enabled = True
        self.intent_mapping = {}
        self.fallback_step = None
        self.tts_enabled = False
        self.interruption_handling = "continue"  # continue, restart, ignore
        
    def to_dict(self) -> Dict[str, Any]:
        return {
            "barge_in_enabled": self.barge_in_enabled,
            "max_wait_seconds": self.max_wait_seconds,
            "intent_mapping": self.intent_mapping,
            "audio_file": self.audio_file,
            "text_content": self.text_content,
            "variables": self.variables,
            "tts_enabled": self.tts_enabled,
            "interruption_handling": self.interruption_handling,
            "fallback_step": self.fallback_step
        }

class ScenarioGenerator:
    """Générateur interactif de scénarios d'appel"""
    
    def __init__(self):
        self.logger = get_logger(f"{__name__}.ScenarioGenerator")
        self.project_dir = Path(__file__).parent.parent
        self.scenarios_dir = self.project_dir / "scenarios"
        self.audio_dir = self.project_dir / "audio"
        self.scenarios_dir.mkdir(exist_ok=True)
        
        self.current_scenario = {
            "name": "",
            "description": "",
            "company": "",
            "agent_name": "",
            "variables": {},
            "steps": {},
            "flow_order": []
        }
        
        # Intent types disponibles
        self.available_intents = [
            "affirm", "deny", "callback", "price", "interested", 
            "not_interested", "unsure", "objection", "question", "sarcastic"
        ]
        
        # Types d'étapes
        self.step_types = {
            "intro": "Introduction/Présentation",
            "question": "Question de qualification", 
            "confirmation": "Confirmation d'accord",
            "objection": "Gestion d'objection",
            "offer": "Proposition commerciale",
            "close": "Fermeture (succès/échec)"
        }

    @log_function_call(include_args=False)
    def start_interactive_creation(self):
        """Lance la création interactive du scénario"""
        print(f"\n{Colors.CYAN}{Colors.BOLD}=" * 70)
        print("🎭 GÉNÉRATEUR DE SCÉNARIOS MINIBOTPANEL V2")
        print("   Création interactive avec variables, barge-in et TTS")
        print("=" * 70 + f"{Colors.NC}\n")
        
        # 1. Informations générales
        self._collect_general_info()
        
        # 2. Variables dynamiques  
        self._setup_variables()
        
        # 3. Création du flow étape par étape
        self._create_scenario_flow()
        
        # 4. Configuration avancée
        self._configure_advanced_settings()
        
        # 5. Génération des fichiers
        self._generate_files()
        
        print(f"\n{Colors.GREEN}🎉 Scénario généré avec succès !{Colors.NC}")

    def _collect_general_info(self):
        """Collecte les informations générales du scénario"""
        print(f"{Colors.BLUE}📋 INFORMATIONS GÉNÉRALES{Colors.NC}")
        print("-" * 30)
        
        self.current_scenario["name"] = input("📝 Nom du scénario: ").strip()
        self.current_scenario["description"] = input("📄 Description courte: ").strip()
        
        # Informations entreprise détaillées
        print(f"\n{Colors.CYAN}🏢 INFORMATIONS ENTREPRISE{Colors.NC}")
        self.current_scenario["company"] = input("🏢 Nom de l'entreprise: ").strip()
        self.current_scenario["company_address"] = input("📍 Adresse complète: ").strip()
        self.current_scenario["company_city"] = input("🏙️  Ville: ").strip()
        self.current_scenario["company_country"] = input("🌍 Pays: ").strip()
        self.current_scenario["company_phone"] = input("📞 Téléphone entreprise: ").strip()
        self.current_scenario["company_website"] = input("🌐 Site web: ").strip()
        
        # Informations commercial
        print(f"\n{Colors.GREEN}👤 INFORMATIONS COMMERCIAL{Colors.NC}")
        self.current_scenario["agent_name"] = input("👤 Prénom du commercial: ").strip()
        self.current_scenario["agent_lastname"] = input("👤 Nom du commercial: ").strip()
        self.current_scenario["agent_title"] = input("🎯 Titre/Fonction (ex: Conseiller, Expert): ").strip()
        
        # Profil de personnalité pour TTS
        print(f"\n{Colors.PURPLE}🎭 PROFIL DE PERSONNALITÉ{Colors.NC}")
        print("Définissez le style du commercial pour adapter le TTS:")
        
        personalities = [
            ("Sympathique et décontracté", "Ton amical, souriant, proche du client"),
            ("Professionnel et rassurant", "Ton expert, confiant, crédible"),
            ("Énergique et enthousiaste", "Ton dynamique, motivé, convaincant"),
            ("Discret et consultative", "Ton calme, analytique, conseil"),
            ("Chaleureux et familial", "Ton humain, empathique, bienveillant"),
            ("Autorité et expertise", "Ton ferme, directif, leadership")
        ]
        
        for i, (style, desc) in enumerate(personalities, 1):
            print(f"   {i}. {style} - {desc}")
        
        personality_choice = input("\nChoisissez le style (1-6): ").strip()
        try:
            self.current_scenario["agent_personality"] = personalities[int(personality_choice) - 1]
        except:
            self.current_scenario["agent_personality"] = personalities[0]
        
        # Secteur d'activité pour contexte
        print(f"\n{Colors.YELLOW}🎯 SECTEUR D'ACTIVITÉ{Colors.NC}")
        sectors = [
            "Finance/Patrimoine", "Immobilier", "Formation", "Services", 
            "E-commerce", "Technologie", "Santé", "Juridique", "Autre"
        ]
        for i, sector in enumerate(sectors, 1):
            print(f"   {i}. {sector}")
        
        sector_choice = input("\nChoisissez (1-9): ").strip()
        try:
            self.current_scenario["sector"] = sectors[int(sector_choice) - 1]
        except:
            self.current_scenario["sector"] = "Services"
        
        # Informations produit/service
        self._collect_product_info()

    def _collect_product_info(self):
        """Collecte les informations sur le produit/service"""
        print(f"\n{Colors.RED}🎯 PRODUIT/SERVICE VENDU{Colors.NC}")
        print("-" * 30)
        
        self.current_scenario["product_name"] = input("📦 Nom du produit/service: ").strip()
        self.current_scenario["product_description"] = input("📄 Description détaillée: ").strip()
        self.current_scenario["product_price"] = input("💰 Prix/Tarification: ").strip()
        
        # Avantages principaux
        print(f"\n{Colors.GREEN}✅ AVANTAGES PRINCIPAUX{Colors.NC}")
        print("Listez les 3-5 avantages clés de votre offre:")
        
        advantages = []
        for i in range(1, 6):
            advantage = input(f"   {i}. Avantage {i} (ou Enter pour terminer): ").strip()
            if not advantage:
                break
            advantages.append(advantage)
        
        self.current_scenario["product_advantages"] = advantages
        
        # Différenciateurs concurrentiels
        print(f"\n{Colors.CYAN}🥇 DIFFÉRENCIATEURS CONCURRENTIELS{Colors.NC}")
        differentiators = []
        for i in range(1, 4):
            diff = input(f"   {i}. Différenciateur {i} (ou Enter pour terminer): ").strip()
            if not diff:
                break
            differentiators.append(diff)
        
        self.current_scenario["product_differentiators"] = differentiators
        
        # Garanties/Preuves sociales
        print(f"\n{Colors.PURPLE}🛡️ GARANTIES & PREUVES SOCIALES{Colors.NC}")
        self.current_scenario["guarantees"] = input("🛡️ Garanties offertes: ").strip()
        self.current_scenario["social_proof"] = input("👥 Preuves sociales (nb clients, témoignages): ").strip()
        self.current_scenario["certifications"] = input("🏆 Certifications/Labels: ").strip()
        
        # Génération automatique d'objections
        self._generate_objections()

    def _generate_objections(self):
        """Génère automatiquement les objections courantes et collecte les réponses"""
        print(f"\n{Colors.YELLOW}🚫 GESTION D'OBJECTIONS AUTOMATIQUE{Colors.NC}")
        print("-" * 40)
        print("Je vais générer les objections courantes. Donnez-moi vos meilleures réponses:")
        
        # Objections automatiques selon le secteur
        sector_objections = {
            "Finance/Patrimoine": [
                "C'est trop cher / Je n'ai pas les moyens",
                "Je ne fais pas confiance aux conseillers financiers",
                "Je suis déjà satisfait de ma banque",
                "C'est trop risqué / Je préfère la sécurité",
                "Je n'ai pas le temps de m'en occuper maintenant"
            ],
            "Immobilier": [
                "Le marché immobilier va s'effondrer",
                "Les taux sont trop élevés actuellement", 
                "Je ne veux pas m'endetter",
                "Ce n'est pas le bon moment pour investir",
                "C'est trop compliqué à gérer"
            ],
            "Formation": [
                "Je n'ai pas le temps de me former",
                "C'est trop cher pour ce que c'est",
                "Je peux apprendre tout seul en ligne",
                "Votre formation n'est pas certifiée/reconnue",
                "Je ne suis pas sûr que ça m'aide dans mon travail"
            ]
        }
        
        # Objections génériques
        generic_objections = [
            "Ça ne m'intéresse pas du tout",
            "Je vais réfléchir et vous rappelle",
            "Envoyez-moi de la documentation par email",
            "Je dois en parler à mon conjoint/associé", 
            "Ce n'est vraiment pas le bon moment",
            "Vous êtes comme tous les commerciaux",
            "J'ai déjà testé un concurrent, ça n'a pas marché",
            "Votre prix n'est pas compétitif"
        ]
        
        # Sélectionner les objections selon le secteur
        sector = self.current_scenario.get("sector", "Services")
        objections = sector_objections.get(sector, []) + generic_objections[:4]
        
        objection_responses = {}
        
        for objection in objections:
            print(f"\n{Colors.RED}🚫 Objection: '{objection}'{Colors.NC}")
            response = input(f"💬 Votre réponse: ").strip()
            
            if response:
                # Demander une alternative si la première réponse ne marche pas
                fallback = input(f"🔄 Réponse alternative (si la 1ère ne fonctionne pas): ").strip()
                
                objection_responses[objection] = {
                    "primary_response": response,
                    "fallback_response": fallback if fallback else response,
                    "tone": self.current_scenario["agent_personality"][0],
                    "context": f"Objection sur {self.current_scenario['product_name']}"
                }
        
        self.current_scenario["objection_responses"] = objection_responses
        
        # Questions fréquentes
        print(f"\n{Colors.BLUE}❓ QUESTIONS FRÉQUENTES{Colors.NC}")
        print("Ajoutez 2-3 questions que vos prospects posent souvent:")
        
        faq = {}
        for i in range(1, 4):
            question = input(f"❓ Question fréquente {i} (ou Enter pour terminer): ").strip()
            if not question:
                break
            answer = input(f"💬 Réponse: ").strip()
            if answer:
                faq[question] = answer
        
        self.current_scenario["faq"] = faq

    def _setup_variables(self):
        """Configuration des variables dynamiques"""
        print(f"\n{Colors.PURPLE}🔧 VARIABLES DYNAMIQUES{Colors.NC}")
        print("-" * 30)
        print("Configurez les variables qui seront remplacées dans les textes")
        print("Exemple: 'Bonjour $nom, je suis $agent de $entreprise'")
        
        variables = {}
        
        while True:
            print(f"\n{Colors.CYAN}Variables actuelles: {list(variables.keys())}{Colors.NC}")
            var_name = input("\n📝 Nom de variable (ou Enter pour terminer): ").strip()
            
            if not var_name:
                break
                
            var_description = input(f"📄 Description de ${var_name}: ").strip()
            var_default = input(f"🔧 Valeur par défaut: ").strip()
            
            variables[var_name] = {
                "description": var_description,
                "default": var_default,
                "source": "manual"  # manual, database, api
            }
        
        self.current_scenario["variables"] = variables

    def _create_scenario_flow(self):
        """Création interactive du flow du scénario"""
        print(f"\n{Colors.GREEN}🎭 CRÉATION DU FLOW DU SCÉNARIO{Colors.NC}")
        print("-" * 40)
        
        steps = {}
        flow_order = []
        current_step_id = "start"
        
        while True:
            print(f"\n{Colors.CYAN}📍 Étape actuelle: {current_step_id}{Colors.NC}")
            
            # Créer l'étape
            step = self._create_single_step(current_step_id)
            steps[current_step_id] = step
            flow_order.append(current_step_id)
            
            # Demander les transitions
            next_steps = self._configure_step_transitions(step)
            
            if not next_steps:
                print(f"{Colors.YELLOW}🏁 Fin du scénario{Colors.NC}")
                break
            
            # Choisir la prochaine étape à créer
            if len(next_steps) == 1:
                current_step_id = list(next_steps.keys())[0]
            else:
                print(f"\n{Colors.BLUE}Prochaines étapes possibles: {list(next_steps.keys())}{Colors.NC}")
                next_choice = input("Quelle étape créer ensuite ? ").strip()
                current_step_id = next_choice if next_choice in next_steps else list(next_steps.keys())[0]
            
            # Si l'étape existe déjà, ne pas la recréer
            if current_step_id in steps:
                break
        
        self.current_scenario["steps"] = {k: v.to_dict() for k, v in steps.items()}
        self.current_scenario["flow_order"] = flow_order

    def _create_single_step(self, step_id: str) -> ScenarioStep:
        """Crée une étape individuelle du scénario"""
        print(f"\n{Colors.YELLOW}🔨 Création de l'étape: {step_id}{Colors.NC}")
        
        # Type d'étape
        print("Types d'étapes disponibles:")
        for key, description in self.step_types.items():
            print(f"   {key}: {description}")
        
        step_type = input(f"\nType d'étape pour '{step_id}': ").strip()
        if step_type not in self.step_types:
            step_type = "question"
        
        step = ScenarioStep(step_id, step_type)
        
        # Contenu textuel
        print(f"\n📝 Contenu textuel de l'étape '{step_id}':")
        print("(Utilisez $variable pour les substitutions)")
        step.text_content = input("Texte: ").strip()
        
        # Fichier audio
        audio_choice = input(f"\n🎵 Audio préenregistré (o/n) ? [n]: ").strip().lower()
        if audio_choice in ['o', 'oui', 'y', 'yes']:
            step.audio_file = input("Nom du fichier audio (ex: intro.wav): ").strip()
            step.tts_enabled = False
        else:
            step.tts_enabled = True
            step.audio_file = f"{step_id}.wav"  # Sera généré par TTS
        
        # Configuration timing
        try:
            step.max_wait_seconds = float(input(f"⏱️  Temps d'attente max (secondes) [10]: ").strip() or "10")
        except:
            step.max_wait_seconds = 10.0
        
        # Barge-in
        barge_choice = input(f"🔄 Autoriser interruption client (o/n) ? [o]: ").strip().lower()
        step.barge_in_enabled = barge_choice not in ['n', 'non', 'no']
        
        if step.barge_in_enabled:
            interruption_choice = input("🎯 Gestion interruption (continue/restart/ignore) [continue]: ").strip()
            if interruption_choice in ['continue', 'restart', 'ignore']:
                step.interruption_handling = interruption_choice
        
        return step

    def _configure_step_transitions(self, step: ScenarioStep) -> Dict[str, str]:
        """Configure les transitions selon les réponses du client"""
        print(f"\n{Colors.BLUE}🔀 CONFIGURATION DES TRANSITIONS{Colors.NC}")
        print("Que se passe-t-il selon la réponse du client ?")
        
        transitions = {}
        
        # Réponses possibles
        print("\nIntentions disponibles:")
        for i, intent in enumerate(self.available_intents, 1):
            print(f"   {i:2d}. {intent}")
        
        while True:
            print(f"\n{Colors.CYAN}Transitions actuelles: {step.intent_mapping}{Colors.NC}")
            
            intent = input("\n🎯 Intention client (ou Enter pour terminer): ").strip()
            if not intent:
                break
            
            if intent not in self.available_intents:
                print(f"{Colors.RED}Intention inconnue. Disponibles: {self.available_intents}{Colors.NC}")
                continue
            
            next_step = input(f"➡️  Si '{intent}', aller à l'étape: ").strip()
            
            step.intent_mapping[intent] = next_step
            transitions[next_step] = intent
        
        # Fallback par défaut
        fallback = input(f"\n🔄 Étape de fallback (si intention non reconnue): ").strip()
        if fallback:
            step.fallback_step = fallback
            transitions[fallback] = "fallback"
        
        return transitions

    def _configure_advanced_settings(self):
        """Configuration avancée du scénario"""
        print(f"\n{Colors.PURPLE}⚙️  CONFIGURATION AVANCÉE{Colors.NC}")
        print("-" * 30)
        
        # TTS Voice cloning
        tts_choice = input("🎙️ Utiliser TTS voice cloning pour réponses dynamiques (o/n) ? [o]: ").strip().lower()
        self.current_scenario["tts_voice_cloning"] = tts_choice not in ['n', 'non', 'no']
        
        # Retry strategy
        retry_choice = input("🔄 Stratégie de retry intelligente (o/n) ? [o]: ").strip().lower()
        self.current_scenario["intelligent_retry"] = retry_choice not in ['n', 'non', 'no']
        
        # Hybrid mode
        hybrid_choice = input("🧠 Mode hybride (scénario + réponses libres) (o/n) ? [o]: ").strip().lower()
        self.current_scenario["hybrid_mode"] = hybrid_choice not in ['n', 'non', 'no']
        
        # Performance monitoring
        monitor_choice = input("📊 Monitoring performance détaillé (o/n) ? [o]: ").strip().lower()
        self.current_scenario["performance_monitoring"] = monitor_choice not in ['n', 'non', 'no']

    def _generate_files(self):
        """Génère tous les fichiers nécessaires"""
        print(f"\n{Colors.GREEN}📁 GÉNÉRATION DES FICHIERS{Colors.NC}")
        print("-" * 30)
        
        scenario_name = self.current_scenario["name"].lower().replace(" ", "_")
        
        # 1. Fichier scénario principal
        self._generate_scenario_file(scenario_name)
        
        # 2. Configuration streaming
        self._generate_streaming_config(scenario_name)
        
        # 3. Variables et prompts
        self._generate_prompts_config(scenario_name)
        
        # 4. Audio texts mapping
        self._generate_audio_texts(scenario_name)
        
        # 5. Script de test
        self._generate_test_script(scenario_name)
        
        print(f"\n{Colors.CYAN}📋 Fichiers générés dans scenarios/{scenario_name}/{Colors.NC}")

    def _generate_scenario_file(self, scenario_name: str):
        """Génère le fichier scénario principal"""
        scenario_dir = self.scenarios_dir / scenario_name
        scenario_dir.mkdir(exist_ok=True)
        
        # Template du scénario complet
        scenario_template = f'''#!/usr/bin/env python3
"""
Scénario: {self.current_scenario["name"]}
Description: {self.current_scenario["description"]}
Entreprise: {self.current_scenario["company"]}
Agent: {self.current_scenario["agent_name"]}
Généré le: {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}
"""

from datetime import datetime

# Imports avec gestion d'erreur
try:
    from sqlalchemy.orm import Session
    from database import SessionLocal
    from models import Call, CallInteraction, Contact
    from logger_config import get_logger, log_function_call, log_memory_usage
except ImportError as e:
    print(f"Warning: Some modules not available: {e}")
    def get_logger(name): 
        import logging
        return logging.getLogger(name)
    def log_function_call(func): return func
    def log_memory_usage(): pass
import time
import os
from typing import Dict, Any, Optional, Tuple

logger = get_logger(__name__)

# Variables du scénario
SCENARIO_VARIABLES = {json.dumps(self.current_scenario["variables"], indent=4)}

# Configuration streaming
STREAMING_CONFIG = {json.dumps(self.current_scenario["steps"], indent=4)}

# Configuration avancée
ADVANCED_CONFIG = {{
    "tts_voice_cloning": {self.current_scenario.get("tts_voice_cloning", True)},
    "intelligent_retry": {self.current_scenario.get("intelligent_retry", True)},
    "hybrid_mode": {self.current_scenario.get("hybrid_mode", True)},
    "performance_monitoring": {self.current_scenario.get("performance_monitoring", True)}
}}

class {scenario_name.title()}Scenario:
    """
    Scénario {self.current_scenario["name"]} avec support streaming complet
    """
    
    def __init__(self):
        self.logger = get_logger(f"{{__name__}}.{scenario_name.title()}Scenario")
        self.scenario_name = "{self.current_scenario["name"]}"
        self.variables = SCENARIO_VARIABLES.copy()
        self.streaming_config = STREAMING_CONFIG
        self.advanced_config = ADVANCED_CONFIG
        
        # Services
        self._init_services()
        
        self.logger.info(f"✅ Scénario {{self.scenario_name}} initialisé")
    
    def _init_services(self):
        """Initialise les services nécessaires"""
        try:
            # Import des services streaming
            from services.live_asr_vad import live_asr_vad_service
            from services.nlp_intent import intent_engine
            from services.amd_service import amd_service
            
            self.asr_service = live_asr_vad_service
            self.intent_engine = intent_engine
            self.amd_service = amd_service
            
            # TTS Voice cloning si activé
            if self.advanced_config["tts_voice_cloning"]:
                from services.tts_voice_clone import voice_clone_service
                self.tts_service = voice_clone_service
            
            self.logger.info("🔧 Services streaming initialisés")
            
        except Exception as e:
            self.logger.error(f"❌ Erreur initialisation services: {{e}}")
            raise
    
    @log_function_call(include_args=True, log_performance=True)
    @log_memory_usage
    def execute_scenario(self, robot, channel_id: str, phone_number: str, campaign_id: str = None) -> bool:
        """
        Exécute le scénario complet
        
        Args:
            robot: Instance ARI robot
            channel_id: ID du channel Asterisk
            phone_number: Numéro appelé
            campaign_id: ID de campagne (optionnel)
            
        Returns:
            True si succès, False sinon
        """
        self.logger.info(f"🎭 Démarrage scénario {{self.scenario_name}} pour {{phone_number}}")
        
        try:
            # Résoudre les variables dynamiques
            resolved_vars = self._resolve_variables(phone_number)
            
            # Exécuter le flow
            result = self._execute_flow(robot, channel_id, phone_number, resolved_vars)
            
            self.logger.info(f"🎉 Scénario terminé - Résultat: {{result}}")
            return result
            
        except Exception as e:
            self.logger.error(f"❌ Erreur scénario: {{e}}")
            return False
    
    def _resolve_variables(self, phone_number: str) -> Dict[str, str]:
        """Résout les variables dynamiques"""
        resolved = {{}}
        
        for var_name, var_config in self.variables.items():
            if var_config["source"] == "manual":
                resolved[var_name] = var_config["default"]
            elif var_config["source"] == "database":
                # TODO: Récupérer depuis la base
                resolved[var_name] = var_config["default"]
            elif var_config["source"] == "api":
                # TODO: Récupérer depuis API
                resolved[var_name] = var_config["default"]
            else:
                resolved[var_name] = var_config["default"]
        
        # Variables système automatiques
        resolved.update({{
            "phone_number": phone_number,
            "agent_name": "{self.current_scenario["agent_name"]}",
            "company": "{self.current_scenario["company"]}",
            "datetime": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        }})
        
        return resolved
    
    def _execute_flow(self, robot, channel_id: str, phone_number: str, variables: Dict[str, str]) -> bool:
        """Exécute le flow principal du scénario"""
        
        conversation_flow = []
        current_step = "start"
        
        while current_step:
            step_config = self.streaming_config.get(current_step)
            if not step_config:
                self.logger.error(f"❌ Étape inconnue: {{current_step}}")
                break
            
            # Exécuter l'étape
            step_result = self._execute_step(robot, channel_id, current_step, step_config, variables)
            conversation_flow.append(step_result)
            
            # Déterminer la prochaine étape
            next_step = self._get_next_step(step_result, step_config)
            
            if next_step == current_step:  # Éviter boucle infinie
                break
                
            current_step = next_step
        
        # Analyser le résultat final
        return self._analyze_final_result(conversation_flow)
    
    def _execute_step(self, robot, channel_id: str, step_id: str, step_config: Dict, variables: Dict[str, str]) -> Dict[str, Any]:
        """Exécute une étape individuelle"""
        self.logger.debug(f"🔵 Exécution étape: {{step_id}}")
        
        # Résoudre le texte avec variables
        text_content = step_config.get("text_content", "")
        for var_name, var_value in variables.items():
            text_content = text_content.replace(f"${{var_name}}", str(var_value))
        
        # Diffuser audio ou TTS
        if step_config.get("tts_enabled", False) and hasattr(self, 'tts_service'):
            # Générer avec TTS voice cloning
            audio_path = self.tts_service.generate_contextual_response(text_content, step_id)
            if audio_path:
                robot.play_audio_file(channel_id, audio_path)
        else:
            # Audio préenregistré
            audio_file = step_config.get("audio_file", f"{{step_id}}.wav")
            robot.play_audio_file(channel_id, audio_file)
        
        # Écouter réponse avec barge-in
        if step_config.get("barge_in_enabled", True):
            response = self._listen_with_barge_in(
                robot, 
                channel_id, 
                step_config.get("max_wait_seconds", 10.0),
                step_config.get("interruption_handling", "continue")
            )
        else:
            response = self._listen_simple(robot, channel_id, step_config.get("max_wait_seconds", 10.0))
        
        # Analyser l'intention
        intent, confidence, metadata = self.intent_engine.get_intent(
            response, 
            context=step_id,
            step=step_id,
            hybrid_mode=self.advanced_config["hybrid_mode"]
        )
        
        return {{
            "step": step_id,
            "text_sent": text_content,
            "response_received": response,
            "intent": intent,
            "confidence": confidence,
            "metadata": metadata,
            "timestamp": datetime.now().isoformat()
        }}
    
    def _get_next_step(self, step_result: Dict, step_config: Dict) -> Optional[str]:
        """Détermine la prochaine étape selon l'intention"""
        intent = step_result.get("intent", "unsure")
        intent_mapping = step_config.get("intent_mapping", {{}})
        
        # Vérifier mapping direct
        if intent in intent_mapping:
            return intent_mapping[intent]
        
        # Fallback
        fallback = step_config.get("fallback_step")
        if fallback:
            return fallback
        
        # Fin du scénario
        return None
    
    def _listen_with_barge_in(self, robot, channel_id: str, max_wait: float, interruption_handling: str) -> str:
        """Écoute avec support barge-in"""
        # TODO: Implémenter écoute avec interruption
        # Pour l'instant, écoute simple
        return self._listen_simple(robot, channel_id, max_wait)
    
    def _listen_simple(self, robot, channel_id: str, max_wait: float) -> str:
        """Écoute simple sans barge-in"""
        # TODO: Implémenter écoute ASR
        # Pour l'instant, simulation
        return "oui"
    
    def _analyze_final_result(self, conversation_flow: List[Dict]) -> bool:
        """Analyse le résultat final de la conversation"""
        if not conversation_flow:
            return False
        
        # Logique simple: si dernière intention positive
        last_step = conversation_flow[-1]
        last_intent = last_step.get("intent", "")
        
        success_intents = ["affirm", "interested", "callback"]
        return last_intent in success_intents

# Instance du scénario pour utilisation globale
{scenario_name}_scenario = {scenario_name.title()}Scenario()

def execute_{scenario_name}(robot, channel_id: str, phone_number: str, campaign_id: str = None) -> bool:
    """
    Fonction d'entrée pour exécuter le scénario {self.current_scenario["name"]}
    """
    return {scenario_name}_scenario.execute_scenario(robot, channel_id, phone_number, campaign_id)
'''
        
        scenario_file = scenario_dir / f"{scenario_name}_scenario.py"
        scenario_file.write_text(scenario_template, encoding='utf-8')
        
        print(f"✅ Scénario généré: {scenario_file}")

    def _generate_streaming_config(self, scenario_name: str):
        """Génère la configuration streaming"""
        scenario_dir = self.scenarios_dir / scenario_name
        
        config_content = {
            "scenario_name": self.current_scenario["name"],
            "streaming_config": self.current_scenario["steps"],
            "variables": self.current_scenario["variables"],
            "advanced_settings": {
                "tts_voice_cloning": self.current_scenario.get("tts_voice_cloning", True),
                "hybrid_mode": self.current_scenario.get("hybrid_mode", True),
                "intelligent_retry": self.current_scenario.get("intelligent_retry", True),
                "performance_monitoring": self.current_scenario.get("performance_monitoring", True)
            }
        }
        
        config_file = scenario_dir / f"{scenario_name}_config.json"
        config_file.write_text(json.dumps(config_content, indent=4, ensure_ascii=False), encoding='utf-8')
        
        print(f"✅ Configuration streaming: {config_file}")

    def _generate_prompts_config(self, scenario_name: str):
        """Génère la configuration des prompts dynamiques"""
        scenario_dir = self.scenarios_dir / scenario_name
        
        # Configuration complète avec toutes les informations collectées
        prompts_config = {
            "company_info": {
                "name": self.current_scenario["company"],
                "address": self.current_scenario.get("company_address", ""),
                "city": self.current_scenario.get("company_city", ""),
                "country": self.current_scenario.get("company_country", ""),
                "phone": self.current_scenario.get("company_phone", ""),
                "website": self.current_scenario.get("company_website", ""),
                "sector": self.current_scenario.get("sector", "Services"),
                "mission": f"Nous aidons nos clients avec {self.current_scenario.get('product_name', 'nos services')}"
            },
            
            "agent_profile": {
                "first_name": self.current_scenario["agent_name"],
                "last_name": self.current_scenario.get("agent_lastname", ""),
                "title": self.current_scenario.get("agent_title", "Conseiller"),
                "personality": self.current_scenario["agent_personality"],
                "tone": self.current_scenario["agent_personality"][1],
                "style_description": self.current_scenario["agent_personality"][1]
            },
            
            "product_info": {
                "name": self.current_scenario.get("product_name", ""),
                "description": self.current_scenario.get("product_description", ""),
                "price": self.current_scenario.get("product_price", ""),
                "advantages": self.current_scenario.get("product_advantages", []),
                "differentiators": self.current_scenario.get("product_differentiators", []),
                "guarantees": self.current_scenario.get("guarantees", ""),
                "social_proof": self.current_scenario.get("social_proof", ""),
                "certifications": self.current_scenario.get("certifications", "")
            },
            
            "tts_voice_config": {
                "personality_type": self.current_scenario["agent_personality"][0],
                "tone_description": self.current_scenario["agent_personality"][1],
                "speed_adjustment": self._get_speed_for_personality(),
                "pitch_adjustment": self._get_pitch_for_personality(),
                "emotion_level": self._get_emotion_for_personality(),
                "professionalism_level": self._get_professionalism_for_personality()
            },
            
            "objection_handling": self.current_scenario.get("objection_responses", {}),
            
            "contextual_responses": self.current_scenario.get("faq", {}),
            
            "conversation_style": {
                "approach": f"Questions courtes et {self.current_scenario['agent_personality'][0].lower()}",
                "language_level": "accessible et professionnel",
                "pace": "respecter le rythme du prospect",
                "personality": f"{self.current_scenario['agent_name']} de {self.current_scenario['company']}"
            },
            
            "scenario_context": self.current_scenario["description"],
            "variables": self.current_scenario["variables"],
            "step_contexts": {}
        }
        
        # Ajouter contexte pour chaque étape
        for step_id, step_data in self.current_scenario["steps"].items():
            prompts_config["step_contexts"][step_id] = {
                "text": step_data.get("text_content", ""),
                "type": step_data.get("step_type", "question"),
                "purpose": f"Étape {step_id} du scénario {self.current_scenario['name']}"
            }
        
        prompts_file = scenario_dir / f"{scenario_name}_prompts.json"
        prompts_file.write_text(json.dumps(prompts_config, indent=4, ensure_ascii=False), encoding='utf-8')
        
        print(f"✅ Configuration prompts: {prompts_file}")

    def _generate_audio_texts(self, scenario_name: str):
        """Génère le mapping des textes audio"""
        scenario_dir = self.scenarios_dir / scenario_name
        
        audio_texts = {}
        
        for step_id, step_data in self.current_scenario["steps"].items():
            if step_data.get("audio_file"):
                audio_texts[step_id] = {
                    "file": step_data["audio_file"],
                    "text": step_data.get("text_content", ""),
                    "tts_enabled": step_data.get("tts_enabled", False),
                    "variables": [var for var in self.current_scenario["variables"].keys() 
                                if f"${var}" in step_data.get("text_content", "")]
                }
        
        audio_file = scenario_dir / f"{scenario_name}_audio_texts.json"
        audio_file.write_text(json.dumps(audio_texts, indent=4, ensure_ascii=False), encoding='utf-8')
        
        print(f"✅ Mapping audio: {audio_file}")

    def _generate_test_script(self, scenario_name: str):
        """Génère un script de test du scénario"""
        scenario_dir = self.scenarios_dir / scenario_name
        
        test_script = f'''#!/usr/bin/env python3
"""
Script de test pour le scénario {self.current_scenario["name"]}
"""

import sys
import os

# Ajouter le répertoire parent au PYTHONPATH
current_dir = os.path.dirname(__file__)
parent_dir = os.path.dirname(current_dir)
sys.path.insert(0, parent_dir)

try:
    from {scenario_name}_scenario import execute_{scenario_name}
    from logger_config import get_logger
except ImportError as e:
    print(f"Warning: Import error: {{e}}")
    import logging
    def get_logger(name): return logging.getLogger(name)

logger = get_logger(__name__)

def test_{scenario_name}():
    """Test du scénario {self.current_scenario["name"]}"""
    
    print("🧪 Test du scénario {self.current_scenario["name"]}")
    print("-" * 50)
    
    # Mock robot pour test
    class MockRobot:
        def play_audio_file(self, channel_id, audio_file):
            print(f"🎵 Playing: {{audio_file}}")
        
        def listen_for_speech(self, channel_id, max_wait):
            return "oui"  # Simulation réponse positive
    
    # Test
    mock_robot = MockRobot()
    result = execute_{scenario_name}(
        robot=mock_robot,
        channel_id="test_channel",
        phone_number="33123456789"
    )
    
    print(f"✅ Résultat test: {{result}}")
    return result

if __name__ == "__main__":
    test_{scenario_name}()
'''
        
        test_file = scenario_dir / f"test_{scenario_name}.py"
        test_file.write_text(test_script, encoding='utf-8')
        
        print(f"✅ Script de test: {test_file}")

    def _get_speed_for_personality(self) -> float:
        """Détermine la vitesse de parole selon la personnalité"""
        personality = self.current_scenario["agent_personality"][0]
        
        speed_map = {
            "Sympathique et décontracté": 0.95,      # Légèrement plus lent, détendu
            "Professionnel et rassurant": 1.0,       # Vitesse normale
            "Énergique et enthousiaste": 1.15,       # Plus rapide, dynamique
            "Discret et consultative": 0.9,          # Plus lent, réfléchi
            "Chaleureux et familial": 0.95,          # Légèrement plus lent, humain
            "Autorité et expertise": 1.05            # Légèrement plus rapide, assertif
        }
        
        return speed_map.get(personality, 1.0)

    def _get_pitch_for_personality(self) -> str:
        """Détermine la hauteur de voix selon la personnalité"""
        personality = self.current_scenario["agent_personality"][0]
        
        pitch_map = {
            "Sympathique et décontracté": "medium-low",   # Voix plus grave, rassurante
            "Professionnel et rassurant": "medium",       # Neutre
            "Énergique et enthousiaste": "medium-high",   # Plus aigu, dynamique
            "Discret et consultative": "medium-low",      # Grave, sérieux
            "Chaleureux et familial": "medium",           # Naturel
            "Autorité et expertise": "medium-low"         # Grave, autoritaire
        }
        
        return pitch_map.get(personality, "medium")

    def _get_emotion_for_personality(self) -> str:
        """Détermine le niveau d'émotion selon la personnalité"""
        personality = self.current_scenario["agent_personality"][0]
        
        emotion_map = {
            "Sympathique et décontracté": "warm",         # Chaleureux
            "Professionnel et rassurant": "confident",    # Confiant
            "Énergique et enthousiaste": "excited",       # Enthousiaste
            "Discret et consultative": "calm",            # Calme
            "Chaleureux et familial": "friendly",         # Amical
            "Autorité et expertise": "authoritative"      # Autoritaire
        }
        
        return emotion_map.get(personality, "neutral")

    def _get_professionalism_for_personality(self) -> int:
        """Détermine le niveau de professionnalisme (1-10)"""
        personality = self.current_scenario["agent_personality"][0]
        
        professionalism_map = {
            "Sympathique et décontracté": 7,      # Professionnel mais accessible
            "Professionnel et rassurant": 9,      # Très professionnel
            "Énergique et enthousiaste": 8,       # Professionnel et dynamique
            "Discret et consultative": 10,        # Maximum professionnel
            "Chaleureux et familial": 6,          # Moins formel, plus humain
            "Autorité et expertise": 9            # Très professionnel, expert
        }
        
        return professionalism_map.get(personality, 8)

def main():
    """Point d'entrée principal"""
    try:
        generator = ScenarioGenerator()
        generator.start_interactive_creation()
    except KeyboardInterrupt:
        print(f"\n{Colors.YELLOW}🛑 Génération interrompue par l'utilisateur{Colors.NC}")
    except Exception as e:
        print(f"\n{Colors.RED}❌ Erreur: {e}{Colors.NC}")
        logger.error(f"Erreur génération scénario: {e}")

if __name__ == "__main__":
    main()