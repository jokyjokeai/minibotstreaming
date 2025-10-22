#!/usr/bin/env python3
"""
Générateur de Scénarios Interactif - MiniBotPanel v2
Créateur de scénarios d'appel avec flow complet, variables dynamiques et barge-in
"""

import os
import sys
import json
import re
import time
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
        
        # Logique "Is Leads" pour qualification
        self.is_leads_qualifying = False  # Cette question détermine si c'est un lead
        self.required_intent_for_leads = None  # "Positif" ou "Négatif" requis
        self.on_leads_fail_goto = "close_echec"  # Où aller si qualification échoue
        
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
            "fallback_step": self.fallback_step,
            "is_leads_qualifying": self.is_leads_qualifying,
            "required_intent_for_leads": self.required_intent_for_leads,
            "on_leads_fail_goto": self.on_leads_fail_goto
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
        
        # Intent types disponibles (4 intentions simplifiées)
        self.available_intents = [
            "Positif", "Négatif", "Neutre", "Unsure"
        ]
        
        # Types d'étapes avec navigation numérique  
        self.step_types = [
            ("intro", "Introduction/Vérification identité (optionnel - toujours → hello)"),
            ("hello", "Présentation agent (si oui → question1, si non → retry)"),
            ("retry", "Tentative récupération (si oui → question1, si non → close_echec)"),
            ("question", "Question de qualification (1 à 10 questions)"), 
            ("rdv", "Proposition de rendez-vous (si oui → confirmation, si non → close_echec)"),
            ("confirmation", "Confirmation d'accord (toujours → close_success)"),
            ("close_success", "Fermeture succès"),
            ("close_echec", "Fermeture échec")
        ]

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
            "E-commerce", "Technologie", "Santé", "Juridique", "Energie renouvelable", "Autre"
        ]
        for i, sector in enumerate(sectors, 1):
            print(f"   {i}. {sector}")
        
        sector_choice = input("\nChoisissez (1-10): ").strip()
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
            ],
            "Energie renouvelable": [
                "L'installation coûte trop cher",
                "Mon toit n'est pas adapté aux panneaux",
                "Je suis locataire, ce n'est pas possible",
                "Les économies ne sont pas garanties",
                "Les panneaux solaires ne marchent pas bien ici"
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
        
        print(f"\n{Colors.CYAN}🎯 CONFIGURATION GLOBALE DES OBJECTIONS{Colors.NC}")
        print("Donnez vos réponses clés, Ollama va les enrichir et proposer des variantes")
        
        for objection in objections:
            print(f"\n{Colors.RED}🚫 Objection: '{objection}'{Colors.NC}")
            user_response = input(f"💬 Votre réponse: ").strip()
            
            if user_response:
                # Utiliser Ollama pour enrichir la réponse
                enriched_responses = self._enrich_response_with_ollama(
                    objection, 
                    user_response, 
                    self.current_scenario
                )
                
                # Présenter les options à l'utilisateur
                selected_responses = self._validate_ollama_responses(
                    objection, 
                    user_response, 
                    enriched_responses
                )
                
                objection_responses[objection] = {
                    "primary_response": selected_responses["primary"],
                    "fallback_response": selected_responses["fallback"],
                    "alternatives": selected_responses["alternatives"],
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
        """Configuration des variables dynamiques avec interface inversée"""
        print(f"\n{Colors.PURPLE}🔧 VARIABLES DYNAMIQUES{Colors.NC}")
        print("-" * 30)
        print("Ajoutez les données que vous voulez utiliser dans vos textes")
        
        # Options de données avec noms de variables suggérés
        data_options = [
            ("contact.first_name", "prenom", "Prénom du contact (ex: Jean)"),
            ("contact.last_name", "nom", "Nom de famille du contact (ex: Dupont)"),
            ("f'{contact.first_name} {contact.last_name}'", "nom_complet", "Nom complet du contact (ex: Jean Dupont)"),
            ("contact.city", "ville", "Ville du contact (ex: Paris)"),
            ("manual", "custom", "Valeur fixe que je définis maintenant")
        ]
        
        variables = {}
        
        while True:
            if variables:
                print(f"\n{Colors.CYAN}Variables créées: {list(variables.keys())}{Colors.NC}")
            
            print(f"\n🔧 QUELLE DONNÉE VOULEZ-VOUS UTILISER?")
            for i, (code, var_name, description) in enumerate(data_options, 1):
                print(f"   {i}. {description} → ${var_name}")
            print(f"   6. Terminé")
            
            choice = input("\nChoix (1-6): ").strip()
            
            if choice == "6" or not choice:
                break
                
            try:
                choice_idx = int(choice) - 1
                if 0 <= choice_idx < len(data_options):
                    code, suggested_name, description = data_options[choice_idx]
                    
                    if code == "manual":
                        # Valeur fixe
                        var_name = input(f"📝 Nom de la variable: ").strip() or "custom"
                        var_value = input(f"🔧 Valeur de ${var_name}: ").strip()
                        
                        variables[var_name] = {
                            "description": f"Valeur fixe: {var_value}",
                            "source": "manual",
                            "value": var_value
                        }
                        print(f"✅ Variable ${var_name} = '{var_value}' créée")
                        
                    else:
                        # Donnée BDD
                        var_name = input(f"📝 Nom de la variable [{suggested_name}]: ").strip() or suggested_name
                        
                        variables[var_name] = {
                            "description": description,
                            "source": "database", 
                            "code": code,
                            "db_description": description
                        }
                        print(f"✅ Variable ${var_name} créée (contiendra {description.lower()})")
                        
            except (ValueError, IndexError):
                print("❌ Choix invalide")
        
        self.current_scenario["variables"] = variables

    def _enrich_response_with_ollama(self, objection: str, user_response: str, scenario_context: Dict) -> List[str]:
        """Utilise Ollama pour enrichir et générer des variantes de réponse"""
        try:
            import requests
            
            # Construire le contexte pour Ollama
            context = f"""
Produit: {scenario_context.get('product_name', 'N/A')}
Secteur: {scenario_context.get('sector', 'N/A')}
Personnalité agent: {scenario_context.get('agent_personality', ['Professionnel'])[0]}
Entreprise: {scenario_context.get('company', 'N/A')}

Objection client: "{objection}"
Réponse utilisateur: "{user_response}"

Génère 3 variantes améliorées de cette réponse pour un appel téléphonique commercial.
Améliore l'orthographe, la structure et ajoute des arguments convaincants.
Garde le sens original mais rends plus professionnel et persuasif.
Réponds UNIQUEMENT avec les 3 variantes, une par ligne, sans numérotation.
"""
            
            payload = {
                "model": "llama3.2:1b",
                "prompt": context,
                "stream": False,
                "options": {
                    "temperature": 0.7,
                    "num_predict": 150
                }
            }
            
            response = requests.post("http://localhost:11434/api/generate", json=payload, timeout=15)
            
            if response.status_code == 200:
                result = response.json()
                ollama_text = result.get("response", "").strip()
                
                # Diviser en variantes
                variants = [line.strip() for line in ollama_text.split('\n') if line.strip()]
                
                # Garder les 3 meilleures
                return variants[:3] if variants else [user_response]
            else:
                self.logger.warning(f"Ollama indisponible: {response.status_code}")
                return [user_response]
                
        except Exception as e:
            self.logger.warning(f"Erreur enrichissement Ollama: {e}")
            return [user_response]
    
    def _validate_ollama_responses(self, objection: str, original: str, enriched: List[str]) -> Dict[str, str]:
        """Présente les options enrichies et laisse l'utilisateur choisir"""
        print(f"\n{Colors.GREEN}🤖 Ollama a généré ces variantes:{Colors.NC}")
        print(f"   Original: {original}")
        
        options = [original] + enriched
        
        for i, option in enumerate(options):
            print(f"   {i+1}. {option}")
        
        # Choix de la réponse principale
        try:
            primary_choice = input(f"\nChoisissez la réponse principale (1-{len(options)}): ").strip()
            primary_idx = int(primary_choice) - 1
            primary = options[primary_idx] if 0 <= primary_idx < len(options) else options[0]
        except:
            primary = options[0]
        
        # Choix de la réponse de fallback
        remaining_options = [opt for opt in options if opt != primary]
        if remaining_options:
            print(f"\nOptions pour réponse alternative:")
            for i, option in enumerate(remaining_options):
                print(f"   {i+1}. {option}")
            
            try:
                fallback_choice = input(f"Choisissez la réponse alternative (1-{len(remaining_options)} ou Enter pour auto): ").strip()
                if fallback_choice:
                    fallback_idx = int(fallback_choice) - 1
                    fallback = remaining_options[fallback_idx] if 0 <= fallback_idx < len(remaining_options) else remaining_options[0]
                else:
                    fallback = remaining_options[0]
            except:
                fallback = remaining_options[0]
        else:
            fallback = primary
        
        return {
            "primary": primary,
            "fallback": fallback,
            "alternatives": [opt for opt in options if opt not in [primary, fallback]]
        }

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
        
        # Type d'étape avec navigation numérique
        print("Types d'étapes disponibles:")
        for i, (key, description) in enumerate(self.step_types, 1):
            print(f"   {i}. {key}: {description}")
        
        try:
            step_choice = input(f"\nType d'étape pour '{step_id}' (1-{len(self.step_types)}): ").strip()
            step_type = self.step_types[int(step_choice) - 1][0]
        except:
            step_type = "question"
        
        step = ScenarioStep(step_id, step_type)
        
        # Gestion spécifique selon le type d'étape
        if step_type == "intro":
            print(f"\n📝 Introduction automatique:")
            print("Format: 'Bonjour, je suis bien sur le téléphone de $nom ?'")
            step.text_content = input("Texte intro [ou Enter pour défaut]: ").strip()
            if not step.text_content:
                step.text_content = "Bonjour, je suis bien sur le téléphone de $nom ?"
            step.tts_enabled = True
            step.audio_file = f"{step_id}.wav"
            
        elif step_type == "hello":
            print(f"\n📝 Présentation agent:")
            print("Format: 'Je suis {agent} de {entreprise}, je vous contacte concernant...'")
            step.text_content = input("Texte présentation: ").strip()
            
            # Choix audio pour hello
            print(f"\n🎵 Mode audio pour cette présentation:")
            print("   1. Audio pré-enregistré uniquement")
            print("   2. TTS uniquement") 
            print("   3. Audio + TTS fallback")
            
            try:
                audio_mode = input("Choix (1-3): ").strip()
                if audio_mode == "1":
                    step.audio_file = input("Nom du fichier audio: ").strip()
                    step.tts_enabled = False
                elif audio_mode == "2":
                    step.tts_enabled = True
                    step.audio_file = f"{step_id}.wav"
                else:  # 3 ou défaut
                    step.audio_file = input("Nom du fichier audio principal: ").strip()
                    step.tts_enabled = True  # Fallback TTS
            except:
                step.tts_enabled = True
                step.audio_file = f"{step_id}.wav"
                
        else:
            # Autres types d'étapes
            print(f"\n📝 Contenu textuel de l'étape '{step_id}':")
            print("(Utilisez $variable pour les substitutions)")
            step.text_content = input("Texte: ").strip()
            
            # Configuration LEADS pour TOUTES les étapes (système cumulatif)
            if step_type in ["question", "rdv", "confirmation"]:
                print(f"\n🎯 QUALIFICATION LEADS CUMULATIVE:")
                print(f"Cette étape ({step_type}) peut-elle qualifier/disqualifier pour LEADS ?")
                is_qualifying = input("Étape qualifiante LEADS ? (o/n) [n]: ").strip().lower()
                
                if is_qualifying in ['o', 'oui', 'y', 'yes']:
                    step.is_leads_qualifying = True
                    step.required_intent_for_leads = "Positif"  # Toujours positif pour qualification
                    print(f"✅ {step_type.upper()} configurée comme étape qualifiante LEADS")
                    print("   → Réponse POSITIVE requise pour continuer")
                    print("   → Réponse NÉGATIVE = BYE immédiat (close_echec)")
                else:
                    step.is_leads_qualifying = False
                    print(f"ℹ️  {step_type.upper()} non-qualifiante pour LEADS")
            
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
        
        # Gestion d'interruption intelligente
        barge_choice = input(f"🔄 Autoriser interruption client (o/n) ? [o]: ").strip().lower()
        step.barge_in_enabled = barge_choice not in ['n', 'non', 'no']
        
        if step.barge_in_enabled:
            print("🎯 Mode interruption:")
            print("   1. Intelligent (IA répond + continue) [RECOMMANDÉ]")
            print("   2. Continue (ignore interruption)")
            print("   3. Restart (recommence étape)")
            
            try:
                mode_choice = input("Choix [1]: ").strip() or "1"
                if mode_choice == "1":
                    step.interruption_handling = "intelligent"
                elif mode_choice == "2": 
                    step.interruption_handling = "continue"
                else:
                    step.interruption_handling = "restart"
            except:
                step.interruption_handling = "intelligent"
            
            if step.interruption_handling == "intelligent":
                print("✅ Interruptions gérées intelligemment par IA")
        
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
            
            intent_input = input("\n🎯 Intention client (numéro ou nom, Enter pour terminer): ").strip()
            if not intent_input:
                break
            
            # Support input numérique
            intent = None
            if intent_input.isdigit():
                idx = int(intent_input) - 1
                if 0 <= idx < len(self.available_intents):
                    intent = self.available_intents[idx]
                else:
                    print(f"{Colors.RED}Numéro invalide. Choisissez entre 1 et {len(self.available_intents)}{Colors.NC}")
                    continue
            else:
                # Support input texte
                if intent_input in self.available_intents:
                    intent = intent_input
                else:
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
        scenario_template = '''#!/usr/bin/env python3
"""
Scénario: {scenario_name_value}
Description: {scenario_description}
Entreprise: {scenario_company}
Agent: {scenario_agent}
Généré le: {generation_date}
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

# Variables du scénario (configuration des sources)
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
        self.logger = get_logger(f"{{__name__}}.{scenario_name_title}Scenario")
        self.scenario_name = "{scenario_name_value}"
        self.variables = SCENARIO_VARIABLES.copy()
        self.streaming_config = STREAMING_CONFIG
        self.advanced_config = ADVANCED_CONFIG
        
        # Services
        self._init_services()
        
        self.logger.info(f"✅ Scénario {{{{self.scenario_name}}}} initialisé")
    
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
            self.logger.error(f"❌ Erreur initialisation services: {{{{e}}}}")
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
        """Résout les variables dynamiques depuis la BDD et valeurs fixes"""
        resolved = {{}}
        
        # Récupérer le contact depuis la BDD
        contact = self._get_contact_by_phone(phone_number)
        
        for var_name, var_config in self.variables.items():
            if var_config["source"] == "manual":
                # Valeur fixe
                resolved[var_name] = var_config["value"]
            elif var_config["source"] == "database":
                # Valeur dynamique depuis BDD
                try:
                    if contact:
                        # Exécuter le code dynamiquement (ex: contact.first_name)
                        value = eval(var_config["code"])
                        resolved[var_name] = str(value) if value is not None else ""
                    else:
                        resolved[var_name] = f"[Contact non trouvé]"
                        self.logger.warning(f"Contact non trouvé pour {{phone_number}}")
                except Exception as e:
                    resolved[var_name] = f"[Erreur: {{e}}]"
                    self.logger.error(f"Erreur résolution variable {{var_name}}: {{e}}")
            else:
                # Fallback
                resolved[var_name] = var_config.get("value", "")
        
        # Variables système automatiques
        resolved.update({{
            "phone_number": phone_number,
            "agent_name": "{self.current_scenario["agent_name"]}",
            "company": "{self.current_scenario["company"]}",
            "datetime": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        }})
        
        return resolved
    
    def _get_contact_by_phone(self, phone_number: str):
        """Récupère le contact depuis la BDD par numéro de téléphone"""
        try:
            from database import SessionLocal
            from models import Contact
            
            with SessionLocal() as session:
                contact = session.query(Contact).filter(Contact.phone == phone_number).first()
                return contact
        except Exception as e:
            self.logger.error(f"Erreur récupération contact {{phone_number}}: {{e}}")
            return None
    
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
            
            # Gérer les codes de retour freestyle
            freestyle_code = step_result.get("freestyle_code")
            if freestyle_code:
                if freestyle_code == "CLOSE_SUCCESS":
                    self.logger.info("🎉 Conversation terminée avec succès via freestyle")
                    return True
                elif freestyle_code == "CLOSE_ECHEC":
                    self.logger.info("❌ Conversation terminée en échec via freestyle")
                    return False
                elif freestyle_code == "RETURN_TO_SCRIPT":
                    self.logger.info("🔄 Retour au script depuis freestyle - Continue étape suivante")
                    # Continue le flow normal à partir de l'étape suivante
            
            # Déterminer la prochaine étape  
            next_step = self._get_next_step(step_result, step_config, conversation_flow)
            
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
        
        # Gérer les codes de retour spéciaux du mode freestyle
        if isinstance(response, str) and response.startswith(("RETURN_TO_SCRIPT", "CLOSE_SUCCESS", "CLOSE_ECHEC")):
            self.logger.info(f"🎯 Code retour freestyle: {response}")
            return {
                "step_id": step_id,
                "response": response,
                "intent": response.split("_")[1].lower() if "_" in response else "freestyle",
                "confidence": 1.0,
                "freestyle_code": response,
                "timestamp": time.time()
            }
        
        # Analyser l'intention
        intent, confidence, metadata = self.intent_engine.get_intent(
            response, 
            context=step_id,
            step=step_id,
            hybrid_mode=self.advanced_config["hybrid_mode"]
        )
        
        # Logique de qualification leads
        leads_status = None
        if step_config.get("is_leads_qualifying", False):
            required_intent = step_config.get("required_intent_for_leads")
            if intent == required_intent:
                leads_status = "qualified"  # Cette question est validée pour leads
                self.logger.info(f"✅ Question qualifiante réussie: {{step_id}} ({{intent}})")
            else:
                leads_status = "disqualified"  # Cette question disqualifie
                self.logger.info(f"❌ Question qualifiante échouée: {{step_id}} ({{intent}} au lieu de {{required_intent}})")
        
        return {{
            "step": step_id,
            "text_sent": text_content,
            "response_received": response,
            "intent": intent,
            "confidence": confidence,
            "metadata": metadata,
            "timestamp": datetime.now().isoformat(),
            "leads_status": leads_status,
            "is_leads_qualifying": step_config.get("is_leads_qualifying", False)
        }}
    
    def _get_next_step(self, step_result: Dict, step_config: Dict, conversation_flow: List[Dict] = None) -> Optional[str]:
        """Détermine la prochaine étape selon la logique de flow intelligent"""
        intent = step_result.get("intent", "unsure")
        leads_status = step_result.get("leads_status")
        current_step_type = step_config.get("type", "")
        
        # Nouvelle logique de flow intelligent avec qualification cumulative
        return self._get_next_step_intelligent(current_step_type, intent, leads_status, step_config, conversation_flow)
    
    def _get_next_step_intelligent(self, step_type: str, intent: str, leads_status: str, step_config: Dict, conversation_flow: List[Dict] = None) -> Optional[str]:
        """
        Logique de flow intelligent selon les nouvelles règles :
        - intro : Toujours → hello (peu importe la réponse)
        - hello : Positif/Neutre → question1, Négatif → retry  
        - retry : Positif/Neutre → question1, Négatif → close_echec
        - question : Logique de qualification (selon règles leads)
        - rdv : Positif → confirmation, Négatif/Neutre → close_echec
        - confirmation : Toujours → close_success
        """
        
        self.logger.info(f"🎯 Flow intelligent: {step_type} + {intent} → ?")
        
        # Règle 1: intro → toujours hello
        if step_type == "intro":
            self.logger.info("📋 intro → hello (règle automatique)")
            return "hello"
        
        # Règle 2: hello → question1 si positif/neutre, retry si négatif
        elif step_type == "hello":
            if intent in ["Positif", "Neutre"]:
                self.logger.info("👋 hello + positif/neutre → question1")
                return "question1"
            else:  # Négatif ou Unsure
                self.logger.info("👋 hello + négatif → retry")
                return "retry"
        
        # Règle 3: retry → question1 si positif/neutre, close_echec si négatif
        elif step_type == "retry":
            if intent in ["Positif", "Neutre"]:
                self.logger.info("🔄 retry + positif/neutre → question1")
                return "question1"
            else:  # Négatif ou Unsure
                self.logger.info("🔄 retry + négatif → close_echec")
                return "close_echec"
        
        # NOUVELLE LOGIQUE: Qualification cumulative LEADS pour TOUTES les étapes
        elif step_type in ["question", "rdv", "confirmation"]:
            return self._handle_leads_qualification_step(step_type, intent, step_config, conversation_flow)
        
        # Fallback sur l'ancien système si pas de règle
        fallback = step_config.get("fallback_step")
        if fallback:
            return fallback
        
        # Fin du scénario
        return None
    
    def _handle_leads_qualification_step(self, step_type: str, intent: str, step_config: Dict, conversation_flow: List[Dict]) -> Optional[str]:
        """
        Gère la qualification cumulative LEADS pour toutes les étapes
        
        LOGIQUE CUMULATIVE:
        - Chaque étape peut être marquée comme "LEADS qualifying"
        - TOUTES les étapes LEADS doivent être positives
        - Première négative = BYE immédiat (close_echec)
        - Toutes positives = LEADS qualifié
        """
        
        # Vérifier si cette étape est qualifiante pour LEADS
        is_leads_qualifying = step_config.get("is_leads_qualifying", False)
        
        if is_leads_qualifying:
            # Cette étape qualifie pour LEADS
            if intent != "Positif":
                # ÉCHEC de qualification LEADS → BYE immédiat
                self.logger.info(f"❌ LEADS: Étape {step_type} échouée ({intent}) → close_echec IMMÉDIAT")
                return "close_echec"
            else:
                # SUCCÈS de cette étape LEADS
                self.logger.info(f"✅ LEADS: Étape {step_type} validée ({intent}) → Continue qualification")
        
        # Déterminer la prochaine étape selon le type
        if step_type == "question":
            # Continuer vers la question suivante ou rdv
            next_question_num = self._get_next_question_number(step_config)
            if next_question_num:
                self.logger.info(f"📋 Question validée → question{next_question_num}")
                return f"question{next_question_num}"
            else:
                self.logger.info("📋 Toutes questions terminées → rdv")
                return "rdv"
                
        elif step_type == "rdv":
            if intent == "Positif":
                self.logger.info("📅 RDV accepté → confirmation")
                return "confirmation"
            else:
                # Si RDV refusé et pas qualifiant LEADS, alors Not_interested
                if not is_leads_qualifying:
                    self.logger.info("📅 RDV refusé (non-qualifiant) → Not_interested")
                    return "close_echec"  # Géré comme échec mais avec statut différent
                # Si qualifiant LEADS, déjà géré plus haut
                
        elif step_type == "confirmation":
            if intent == "Positif":
                # Vérifier qualification cumulative FINALE
                if self._check_cumulative_leads_qualification(conversation_flow, step_config):
                    self.logger.info("🔥 LEADS MAX: Toutes qualifications validées → close_success")
                    return "close_success"
                else:
                    self.logger.info("✅ Confirmation validée (pas toutes LEADS) → close_success")
                    return "close_success"
            else:
                # Confirmation échouée
                if is_leads_qualifying:
                    # Si confirmation qualifiante échoue → BYE (déjà géré plus haut)
                    pass
                else:
                    # Confirmation non-qualifiante échoue → simple échec
                    self.logger.info("❌ Confirmation échouée → close_echec")
                    return "close_echec"
        
        # Fallback
        return "close_echec"
    
    def _check_cumulative_leads_qualification(self, conversation_flow: List[Dict], current_step_config: Dict) -> bool:
        """
        Vérifie si TOUTES les étapes LEADS ont été validées positivement
        """
        if not conversation_flow:
            return False
        
        # Inclure l'étape actuelle si elle est qualifiante
        all_steps = conversation_flow.copy() if conversation_flow else []
        if current_step_config.get("is_leads_qualifying", False):
            all_steps.append({
                "step_id": current_step_config.get("step_id", "current"),
                "intent": "Positif",
                "is_leads_qualifying": True
            })
        
        # Trouver toutes les étapes marquées comme qualifiantes LEADS
        leads_steps = []
        for step in all_steps:
            # Les step_results contiennent déjà is_leads_qualifying
            if step.get("is_leads_qualifying", False):
                leads_steps.append({
                    "step_id": step.get("step_id", "unknown"),
                    "intent": step.get("intent", "unknown"),
                    "is_positive": step.get("intent") == "Positif"
                })
        
        if not leads_steps:
            self.logger.info("🔍 Aucune étape LEADS qualifiante trouvée")
            return False
        
        # Vérifier que TOUTES les étapes LEADS sont positives
        all_positive = all(step["is_positive"] for step in leads_steps)
        
        leads_count = len(leads_steps)
        positive_count = sum(1 for step in leads_steps if step["is_positive"])
        
        self.logger.info(f"🎯 Qualification LEADS: {positive_count}/{leads_count} étapes validées")
        
        if all_positive:
            self.logger.info(f"🔥 LEADS QUALIFICATION COMPLETE: {leads_count} étapes toutes positives!")
            return True
        else:
            self.logger.info(f"⚠️ Qualification incomplète: {leads_count - positive_count} étapes échouées")
            return False
    
    def _get_next_question_number(self, step_config: Dict) -> Optional[int]:
        """Détermine le numéro de la prochaine question (1-10)"""
        current_step = step_config.get("step_name", "")
        
        # Extraire le numéro actuel si c'est une question numérotée
        if current_step.startswith("question") and current_step[8:].isdigit():
            current_num = int(current_step[8:])
            # Vérifier s'il y a une question suivante configurée
            total_questions = step_config.get("total_questions", 1)
            if current_num < total_questions:
                return current_num + 1
        
        return None
    
    def _listen_with_barge_in(self, robot, channel_id: str, max_wait: float, interruption_handling: str) -> str:
        """Écoute avec support barge-in et gestion intelligente d'interruption"""
        try:
            # Démarrer l'écoute avec détection d'interruption
            response = self._listen_simple(robot, channel_id, max_wait)
            
            # Détecter si c'est une interruption majeure qui nécessite le mode FREESTYLE
            if self._requires_freestyle_mode(response):
                self.logger.info("🎙️ INTERRUPTION MAJEURE → Bascule MODE FREESTYLE")
                return self._handle_freestyle_conversation(robot, channel_id, response, interruption_handling)
            
            # Analyser interruptions mineures (ancien système)
            interruption_intent = self._detect_interruption_intent(response)
            
            if interruption_intent:
                # Générer une réponse automatique appropriée
                auto_response = self._generate_interruption_response(interruption_intent, response)
                
                # Jouer la réponse automatique
                if auto_response:
                    self._speak_text(robot, channel_id, auto_response)
                    
                    # Selon la stratégie, continuer ou recommencer
                    if interruption_handling == "restart":
                        return "RESTART_STEP"
                    elif interruption_handling == "continue":
                        # Écouter à nouveau après la réponse automatique
                        return self._listen_simple(robot, channel_id, max_wait)
                    # ignore = continuer normalement
            
            return response
            
        except Exception as e:
            self.logger.error(f"Erreur écoute barge-in: {{e}}")
            return self._listen_simple(robot, channel_id, max_wait)
    
    def _detect_interruption_intent(self, response: str) -> Optional[str]:
        """Détecte le type d'interruption pour générer une réponse automatique appropriée"""
        if not response or len(response.strip()) < 2:
            return None
            
        response_lower = response.lower().strip()
        
        # Patterns d'interruption courantes
        interruption_patterns = {{
            "qui_etes_vous": ["qui êtes-vous", "qui vous êtes", "vous êtes qui", "c'est qui", "qui appelle"],
            "pas_compris": ["quoi", "comment", "hein", "pardon", "j'ai pas compris", "pas compris"],
            "mal_entendu": ["j'entends mal", "entends pas", "plus fort", "mal", "coupé"],
            "pas_interesse": ["pas intéressé", "ça m'intéresse pas", "me dérange pas", "raccrochez"],
            "rappeler": ["rappeler", "rappelez", "plus tard", "pas le temps", "occupé"],
            "trop_cher": ["trop cher", "coûte cher", "prix", "combien", "tarif"],
            "deja_quelque_chose": ["j'ai déjà", "déjà", "satisfait", "ma banque"],
            "arnaque": ["arnaque", "arnaqueur", "escroquerie", "sérieux"]
        }}
        
        for intent, patterns in interruption_patterns.items():
            for pattern in patterns:
                if pattern in response_lower:
                    return intent
        
        return None
    
    def _generate_interruption_response(self, intent: str, original_response: str) -> Optional[str]:
        """Génère une réponse automatique selon le type d'interruption"""
        # Variables dynamiques disponibles
        agent_name = "{self.current_scenario.get('agent_name', 'votre conseiller')}"
        company = "{self.current_scenario.get('company', 'notre entreprise')}"
        
        interruption_responses = {{
            "qui_etes_vous": f"Je suis {{agent_name}} de {{company}}, je vous contacte concernant votre épargne.",
            
            "pas_compris": "Excusez-moi, je n'ai pas été assez clair. Laissez-moi reformuler...",
            
            "mal_entendu": "Je vous entends un peu mal, je vais parler plus distinctement. Puis-je continuer ?",
            
            "pas_interesse": "Je comprends parfaitement. Laissez-moi juste vous expliquer en 30 secondes pourquoi cela pourrait vous intéresser.",
            
            "rappeler": "Bien sûr, quand puis-je vous rappeler ? Demain matin ou plutôt en fin d'après-midi ?",
            
            "trop_cher": "Je comprends votre préoccupation. Justement, nous pouvons commencer avec seulement 500 euros pour un test.",
            
            "deja_quelque_chose": "C'est parfait d'avoir déjà quelque chose ! Il ne faut jamais mettre tous ses œufs dans le même panier. Entre nous, combien vous rapporte actuellement votre placement ?",
            
            "arnaque": "Je comprends votre méfiance, c'est même intelligent. C'est d'ailleurs pour cela que nous proposons toujours de commencer petit, avec 500 euros maximum."
        }}
        
        return interruption_responses.get(intent, None)
    
    def _speak_text(self, robot, channel_id: str, text: str):
        """Fait parler le robot avec le texte donné"""
        try:
            # Si TTS disponible, utiliser le service TTS
            if hasattr(self, 'tts_service') and self.tts_service:
                self.tts_service.synthesize_and_play(text, channel_id)
            else:
                # Fallback : utiliser le robot directement
                robot.speak(channel_id, text)
        except Exception as e:
            self.logger.error(f"Erreur synthèse vocale: {{e}}")
    
    def _listen_simple(self, robot, channel_id: str, max_wait: float) -> str:
        """Écoute simple sans barge-in"""
        # TODO: Implémenter écoute ASR
        # Pour l'instant, simulation
        return "oui"
    
    # ====== MODE FREESTYLE OLLAMA + TTS ======
    
    def _requires_freestyle_mode(self, response: str) -> bool:
        """Détermine si une interruption nécessite le mode freestyle complet"""
        
        # Patterns qui déclenchent le mode freestyle (interruptions majeures)
        freestyle_triggers = [
            # Questions agressives/méfiantes
            "qui vous a donné", "qui vous êtes", "où avez-vous", "comment vous", 
            "pourquoi vous", "qu'est-ce que", "c'est quoi", "d'où sortez",
            
            # Objections majeures
            "pas intéressé", "raccrochez", "arrêtez", "spam", "démarchage", 
            "liste rouge", "interdire", "signaler", "arnaque",
            
            # Questions complexes
            "expliquez", "comment ça marche", "garantie", "sécurité", "légal",
            "combien", "quel pourcentage", "risque", "durée",
            
            # Situations personnelles
            "ma situation", "mes revenus", "mon âge", "retraité", "chômage",
            "divorce", "problème", "maladie", "difficile",
            
            # Interruptions émotionnelles
            "en colère", "énerve", "agace", "fatigue", "stress", "inquiet"
        ]
        
        response_lower = response.lower()
        for trigger in freestyle_triggers:
            if trigger in response_lower:
                self.logger.info(f"🎯 Trigger freestyle détecté: '{trigger}' dans '{response[:50]}...'")
                return True
        
        # Détecter aussi les réponses longues (> 15 mots = besoin de discussion)
        word_count = len(response.split())
        if word_count > 15:
            self.logger.info(f"🎯 Réponse longue ({word_count} mots) → Mode freestyle")
            return True
            
        return False
    
    def _handle_freestyle_conversation(self, robot, channel_id: str, initial_response: str, interruption_handling: str) -> str:
        """
        Gère une conversation freestyle complète avec Ollama + TTS
        Conversation libre jusqu'à résolution ou échec
        """
        self.logger.info("🚀 DÉMARRAGE MODE FREESTYLE - Conversation libre avec IA")
        
        # Context pour Ollama
        context = self._build_freestyle_context()
        conversation_history = [
            {"role": "client", "message": initial_response, "timestamp": time.time()}
        ]
        
        max_freestyle_turns = 10  # Limite de sécurité
        turn_count = 0
        
        try:
            while turn_count < max_freestyle_turns:
                turn_count += 1
                self.logger.info(f"🎙️ Tour freestyle {turn_count}/{max_freestyle_turns}")
                
                # Générer réponse intelligente avec Ollama
                ai_response = self._generate_freestyle_response(
                    conversation_history, 
                    context, 
                    turn_count
                )
                
                if not ai_response:
                    self.logger.warning("❌ Pas de réponse IA - Retour script")
                    return "RETURN_TO_SCRIPT"
                
                # Jouer la réponse avec TTS
                self._speak_text(robot, channel_id, ai_response["text"])
                
                # Enregistrer dans l'historique
                conversation_history.append({
                    "role": "agent", 
                    "message": ai_response["text"], 
                    "intent": ai_response.get("intent", "freestyle"),
                    "timestamp": time.time()
                })
                
                # Vérifier si on doit terminer la conversation freestyle
                if ai_response.get("action") == "close_success":
                    self.logger.info("✅ Freestyle terminé avec succès")
                    return "CLOSE_SUCCESS"
                elif ai_response.get("action") == "close_fail":
                    self.logger.info("❌ Freestyle terminé en échec")
                    return "CLOSE_ECHEC"
                elif ai_response.get("action") == "return_script":
                    self.logger.info("🔄 Retour au script depuis freestyle")
                    return "RETURN_TO_SCRIPT"
                
                # Écouter la réponse suivante du client
                client_response = self._listen_simple(robot, channel_id, 10.0)
                conversation_history.append({
                    "role": "client", 
                    "message": client_response, 
                    "timestamp": time.time()
                })
                
                # Vérifier si le client veut raccrocher
                if self._client_wants_to_hang_up(client_response):
                    self.logger.info("📞 Client veut raccrocher - Fin freestyle")
                    return "CLOSE_ECHEC"
        
        except Exception as e:
            self.logger.error(f"❌ Erreur mode freestyle: {e}")
            
        # Fin de conversation freestyle - retour script par défaut
        self.logger.info("🔄 Fin freestyle - Retour au script")
        return "RETURN_TO_SCRIPT"
    
    def _build_freestyle_context(self) -> Dict[str, Any]:
        """Construit le contexte pour les réponses freestyle"""
        return {
            "agent_name": self.current_scenario.get("agent_name", "Marc"),
            "company": self.current_scenario.get("company", "Patrimoine Conseil"),
            "product": self.current_scenario.get("product", "épargne patrimoniale"),
            "sector": self.current_scenario.get("sector", "finance"),
            "product_price": self.current_scenario.get("product_price", "à partir de 500€"),
            "current_step": "freestyle_mode",
            "call_objective": "convaincre et obtenir un rendez-vous",
            "tone": "professionnel mais chaleureux",
            "max_response_length": "2-3 phrases maximum"
        }
    
    def _generate_freestyle_response(self, conversation_history: List[Dict], context: Dict, turn_count: int) -> Optional[Dict]:
        """Génère une réponse freestyle intelligente avec Ollama"""
        try:
            if not hasattr(self, 'intent_engine') or not self.intent_engine:
                self.logger.error("❌ Service NLP non disponible pour freestyle")
                return None
            
            # Construire le prompt pour Ollama
            last_client_message = conversation_history[-1]["message"]
            
            prompt = f"""Tu es {context['agent_name']} de {context['company']}, expert en {context['product']}.
            
            CONVERSATION EN COURS:
            """
            
            # Ajouter l'historique des 3 derniers échanges
            recent_history = conversation_history[-6:] if len(conversation_history) > 6 else conversation_history
            for msg in recent_history:
                role = "CLIENT" if msg["role"] == "client" else "VOUS"
                prompt += f"{role}: {msg['message']}\n"
            
            prompt += f"""
            
            RÈGLES:
            1. Répondre naturellement et professionnellement au client
            2. Rester concentré sur l'objectif: obtenir un rendez-vous
            3. Gérer les objections avec empathie et arguments solides
            4. Si client très hostile → recommander action 'close_fail'
            5. Si client convaincu → recommander action 'return_script' 
            6. Si besoin de continuer → recommander action 'continue'
            7. Maximum 2-3 phrases par réponse
            
            ANALYSEZ le dernier message du client et générez:
            - Une réponse appropriée (2-3 phrases max)
            - L'action recommandée: continue/return_script/close_success/close_fail
            
            Format JSON requis:
            {{"text": "votre réponse au client", "action": "continue", "confidence": 0.8}}
            """
            
            # Appeler Ollama via le service NLP
            result = self.intent_engine._call_ollama_direct(prompt)
            
            if result and "text" in result:
                self.logger.info(f"🤖 Réponse freestyle générée: {result['text'][:50]}...")
                return result
            else:
                # Fallback avec réponse prédéfinie selon le contexte
                return self._generate_fallback_freestyle_response(last_client_message, turn_count)
                
        except Exception as e:
            self.logger.error(f"❌ Erreur génération freestyle: {e}")
            return self._generate_fallback_freestyle_response(conversation_history[-1]["message"], turn_count)
    
    def _generate_fallback_freestyle_response(self, client_message: str, turn_count: int) -> Dict:
        """Génère une réponse freestyle de fallback selon le contexte"""
        
        client_lower = client_message.lower()
        
        # Réponses selon le type de message client
        if any(word in client_lower for word in ["pas intéressé", "pas le temps", "raccrocher"]):
            return {
                "text": "Je comprends parfaitement. Laissez-moi juste vous dire en 30 secondes pourquoi cela pourrait vous intéresser malgré tout.",
                "action": "continue",
                "confidence": 0.7
            }
        
        elif any(word in client_lower for word in ["qui êtes", "d'où", "comment"]):
            return {
                "text": f"Je suis {self.current_scenario.get('agent_name', 'Marc')} de {self.current_scenario.get('company', 'Patrimoine Conseil')}. Nous aidons nos clients à optimiser leur épargne.",
                "action": "continue", 
                "confidence": 0.8
            }
        
        elif any(word in client_lower for word in ["combien", "prix", "coût"]):
            return {
                "text": f"Nous pouvons commencer avec seulement {self.current_scenario.get('product_price', '500€')}. L'important c'est de commencer petit et voir les résultats.",
                "action": "continue",
                "confidence": 0.8
            }
        
        elif turn_count > 7:  # Conversation trop longue
            return {
                "text": "Je vois que vous avez des questions importantes. Accepteriez-vous que je vous rappelle demain pour en discuter plus calmement ?",
                "action": "return_script",
                "confidence": 0.6
            }
        
        else:  # Réponse générique
            return {
                "text": "C'est une excellente question. Laissez-moi vous expliquer simplement comment cela fonctionne.",
                "action": "continue",
                "confidence": 0.5
            }
    
    def _client_wants_to_hang_up(self, response: str) -> bool:
        """Détecte si le client veut clairement raccrocher"""
        hangup_signals = [
            "raccrocher", "raccrochez", "au revoir", "bye", "stop", "arrêt", 
            "termine", "fini", "ça suffit", "j'arrête", "plus jamais"
        ]
        
        response_lower = response.lower()
        return any(signal in response_lower for signal in hangup_signals)
    
    def _analyze_final_result(self, conversation_flow: List[Dict]) -> bool:
        """
        Analyse le résultat final avec système de qualification cumulative LEADS
        """
        if not conversation_flow:
            return False
        
        # Nouvelle logique: Qualification cumulative LEADS
        leads_qualified = self._check_final_leads_qualification(conversation_flow)
        
        if leads_qualified:
            # TOUTES les étapes LEADS validées → LEADS MAX!
            self._update_contact_status("Leads")
            self.logger.info("🔥 Contact qualifié comme LEADS MAX - qualification cumulative complète")
            return True
        else:
            # Qualification échouée ou pas d'étapes qualifiantes
            last_step = conversation_flow[-1]
            last_intent = last_step.get("intent", "")
            
            # Déterminer le statut selon la dernière étape
            if last_intent == "Positif":
                # Conversation positive mais pas LEADS qualifié
                self._update_contact_status("Completed")
                self.logger.info("✅ Conversation terminée positivement (non-LEADS)")
                return True
            else:
                # Conversation échouée
                self._update_contact_status("Not_interested")
                self.logger.info("❌ Conversation terminée en échec")
                return False
    
    def _check_final_leads_qualification(self, conversation_flow: List[Dict]) -> bool:
        """
        Vérification finale de qualification LEADS cumulative
        """
        # Trouver toutes les étapes marquées comme qualifiantes LEADS
        leads_steps = []
        for step in conversation_flow:
            if step.get("is_leads_qualifying", False):
                leads_steps.append({
                    "step_id": step.get("step_id", "unknown"),
                    "intent": step.get("intent", "unknown"),
                    "is_positive": step.get("intent") == "Positif"
                })
        
        if not leads_steps:
            self.logger.info("🔍 Aucune étape LEADS qualifiante dans la conversation")
            return False
        
        # Vérifier que TOUTES sont positives
        all_positive = all(step["is_positive"] for step in leads_steps)
        
        leads_count = len(leads_steps)
        positive_count = sum(1 for step in leads_steps if step["is_positive"])
        
        self.logger.info(f"🎯 FINAL - Qualification LEADS: {positive_count}/{leads_count} étapes validées")
        
        if all_positive:
            self.logger.info(f"🔥 LEADS QUALIFICATION FINALE RÉUSSIE: {leads_count} étapes toutes positives!")
            return True
        else:
            failed_steps = [step["step_id"] for step in leads_steps if not step["is_positive"]]
            self.logger.info(f"❌ Qualification échouée sur: {', '.join(failed_steps)}")
            return False
    
    def _update_contact_status(self, status: str):
        """Met à jour le statut du contact dans la BDD"""
        try:
            # Cette méthode sera appelée avec le phone_number du contexte
            # Pour l'instant, on log juste le statut à appliquer
            self.logger.info(f"📋 Statut contact à appliquer: {status}")
            # TODO: Implémenter mise à jour BDD réelle
        except Exception as e:
            self.logger.error(f"Erreur mise à jour statut contact: {e}")

# Instance du scénario pour utilisation globale
{scenario_name}_scenario = {scenario_name.title()}Scenario()

def execute_{scenario_name}(robot, channel_id: str, phone_number: str, campaign_id: str = None) -> bool:
    \"\"\"
    Fonction d'entrée pour exécuter le scénario {self.current_scenario["name"]}
    \"\"\"
    return {scenario_name}_scenario.execute_scenario(robot, channel_id, phone_number, campaign_id)
'''
        
        # Formater le template avec les vraies valeurs
        formatted_template = scenario_template.format(
            scenario_name_value=self.current_scenario["name"],
            scenario_description=self.current_scenario["description"],
            scenario_company=self.current_scenario["company"],
            scenario_agent=self.current_scenario["agent_name"],
            generation_date=datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            scenario_name=scenario_name,
            scenario_name_title=scenario_name.title()
        )
        
        scenario_file = scenario_dir / f"{scenario_name}_scenario.py"
        scenario_file.write_text(formatted_template, encoding='utf-8')
        
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