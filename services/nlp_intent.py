#!/usr/bin/env python3
"""
NLP Intent Service - MiniBotPanel v2 Streaming
Moteur d'analyse d'intention local avec Ollama
Fallback sur analyse par mots-clés intégrée
"""

import json
import time
import re
from typing import Dict, Optional, Tuple, Any
from datetime import datetime

# Ajouter le répertoire parent au PYTHONPATH pour les imports
import sys
from pathlib import Path
current_dir = Path(__file__).parent
parent_dir = current_dir.parent
sys.path.insert(0, str(parent_dir))

# Import des configurations et services existants
import config
from logger_config import get_logger, log_function_call, log_performance_summary, log_exception, log_memory_usage

logger = get_logger(__name__)

# Import Ollama avec fallback
try:
    import ollama
    OLLAMA_AVAILABLE = True
    logger.info("✅ Ollama imported successfully for local NLP")
except ImportError as e:
    OLLAMA_AVAILABLE = False
    logger.warning(f"⚠️ Ollama not available: {e}. Will fallback to keyword-based sentiment")

# Service sentiment supprimé - utilisation de keywords fallback uniquement
SENTIMENT_FALLBACK_AVAILABLE = False

class IntentEngine:
    """
    Moteur d'analyse d'intention compatible avec MiniBotPanel v2
    Support Ollama local + fallback sur analyse sentiment existante
    """

    @log_function_call(include_args=False, log_performance=True)
    @log_memory_usage
    def __init__(self):
        self.logger = get_logger(f"{__name__}.IntentEngine")
        self.logger.info("🧠 Initializing NLP Intent Engine with hybrid prompts")
        self.is_available = OLLAMA_AVAILABLE
        self.ollama_client = None
        
        # Chargement du contexte de campagne
        self.logger.debug("📖 Loading campaign context from scenarios")
        self.campaign_context = self._load_campaign_context()
        
        # Chargement des prompts dynamiques
        self.logger.debug("🎯 Loading dynamic prompts configuration")
        self.dynamic_prompts = self._load_dynamic_prompts()
        
        # Statistiques
        self.stats = {
            "total_requests": 0,
            "ollama_success": 0,
            "fallback_used": 0,
            "avg_latency_ms": 0.0,
            "model_loaded": False
        }
        
        self.logger.info("✅ NLP Intent Engine initialized successfully")
        
        # Mapping des intents simplifiés vers les statuts MiniBotPanel
        self.intent_to_status = {
            "Positif": "positive",
            "Négatif": "negative", 
            "Neutre": "neutre",
            "Unsure": "unsure"
        }
        
        # Prompts système optimisés avec contexte campagne
        self.system_prompts = {
            "general": f"""Tu es un module NLP pour un robot d'appel de FRANCE PATRIMOINE.

CONTEXTE CAMPAGNE:
{self.campaign_context}

Tu analyses les réponses des prospects français à nos questions sur l'optimisation de placements financiers.
Réponds UNIQUEMENT en JSON au format {{"intent": "...", "confidence": 0.9}}.

Intents possibles (4 seulement) :
- "Positif" : oui, d'accord, ok, intéressé, absolument, évidemment, j'aimerais en savoir plus
- "Négatif" : non, pas intéressé, pas le temps, ça ne m'intéresse pas, arrêtez
- "Neutre" : peut-être, je ne sais pas, il faut que je réfléchisse, ça dépend
- "Unsure" : je n'ai pas compris, pouvez-vous répéter, pardon, comment

Pour les questions (qui, quoi, combien, etc.) → TTS répond automatiquement puis continue.
Réponds TOUJOURS en JSON valide.""",

            "greeting": f"""Tu analyses la réponse à l'introduction FRANCE PATRIMOINE.
Réponds UNIQUEMENT en JSON : {{"intent": "...", "confidence": 0.9}}

{self.campaign_context}

Le prospect répond à l'introduction: "J'ai juste trois petites questions pour voir si nous pouvons vous aider à protéger, optimiser votre patrimoine. Ça vous va ?"

Intents :
- "Positif" : oui, ok, d'accord, allez-y, je vous écoute, pourquoi pas
- "Négatif" : non, pas le temps, pas intéressé, raccrochez, ça ne m'intéresse pas
- "Neutre" : peut-être, ça dépend, voyons, je ne sais pas
- "Unsure" : je n'ai pas compris, pardon, comment""",

            "qualification": f"""Tu analyses la réponse aux questions de qualification FRANCE PATRIMOINE.
Réponds UNIQUEMENT en JSON : {{"intent": "...", "confidence": 0.9}}

{self.campaign_context}

Les questions de qualification portent sur:
- Les placements actuels (livret A, PEL, assurance-vie)
- Le rendement par rapport à l'inflation  
- La satisfaction du conseiller bancaire actuel

Intents :
- "Positif" : oui, j'ai, effectivement, bien sûr, tout à fait
- "Négatif" : non, je n'ai pas, pas du tout, jamais
- "Neutre" : je ne sais pas, peut-être, il faut voir, ça dépend
- "Unsure" : je n'ai pas compris, pardon, comment""",

            "final_offer": f"""Tu analyses la réponse à l'offre finale FRANCE PATRIMOINE.
Réponds UNIQUEMENT en JSON : {{"intent": "...", "confidence": 0.9}}

{self.campaign_context}

Le prospect répond à la proposition: "Un de nos experts vous rappelle sous 48h pour analyser votre dossier et vous présenter nos solutions. Ça vous va ?"

Intents :
- "Positif" : oui, d'accord, ok, parfait, allez-y, très bien
- "Négatif" : non, pas intéressé, ça ne m'intéresse pas, merci mais non
- "Neutre" : oui mais plus tard, pas cette semaine, dans un mois, je réfléchis
- "Unsure" : je n'ai pas compris, pardon, comment"""
        }
        
        self._initialize_ollama()

    def _load_campaign_context(self) -> str:
        """Charge le contexte de campagne complet depuis scenarios_streaming.py"""
        try:
            import os
            
            # Chemin vers scenarios_streaming.py
            scenarios_path = os.path.join(os.path.dirname(__file__), '..', 'scenarios_streaming.py')
            
            if os.path.exists(scenarios_path):
                with open(scenarios_path, 'r', encoding='utf-8') as f:
                    scenario_content = f.read()
                
                # Extraire les parties clés du scénario
                context_parts = []
                
                # Extraire STREAMING_CONFIG
                if 'STREAMING_CONFIG' in scenario_content:
                    start = scenario_content.find('STREAMING_CONFIG = {')
                    if start != -1:
                        # Trouver la fin du dictionnaire
                        brace_count = 0
                        end = start
                        for i, char in enumerate(scenario_content[start:]):
                            if char == '{':
                                brace_count += 1
                            elif char == '}':
                                brace_count -= 1
                                if brace_count == 0:
                                    end = start + i + 1
                                    break
                        
                        config_section = scenario_content[start:end]
                        context_parts.append("CONFIGURATION STREAMING:")
                        context_parts.append(config_section)
                
                # Extraire les commentaires de flow
                lines = scenario_content.split('\n')
                flow_comments = [line.strip() for line in lines if 
                               (line.strip().startswith('# ') and 
                                any(keyword in line.lower() for keyword in 
                                    ['flow', 'étape', 'qualification', 'lead', 'conversation']))]
                
                if flow_comments:
                    context_parts.append("\nFLOW DE CONVERSATION:")
                    context_parts.extend(flow_comments)
                
                full_context = '\n'.join(context_parts)
                
                self.logger.info(f"✅ Contexte scénario complet chargé: {len(full_context)} caractères")
                return full_context
            
        except Exception as e:
            self.logger.warning(f"⚠️ Impossible de charger le contexte scénario: {e}")
        
        # Fallback - contexte par défaut
        return """
CONTEXTE: Robot d'appel FRANCE PATRIMOINE pour qualification commerciale
OBJECTIF: Identifier les prospects intéressés par l'optimisation de placements financiers
FLOW: hello → q1 (placements) → q2 (rendement) → q3 (conseiller) → is_leads (proposition rappel)
QUALIFICATION: livret A, PEL, assurance-vie, inflation, conseiller bancaire
"""

    def _load_dynamic_prompts(self) -> Dict[str, Any]:
        """Charge les prompts dynamiques (prompts_config.json supprimé - utilise prompts par défaut)"""
        # Ancien système prompts_config.json supprimé car remplacé par scenario_generator
        # Les prompts sont maintenant générés dynamiquement dans chaque scénario
        
        # Prompts par défaut intégrés
        return {
            "company_info": {"name": "France Patrimoine", "tone": "professionnel"},
            "conversation_style": {"personality": "Thierry", "approach": "Questions simples"},
            "hybrid_mode_instructions": {"base_rule": "Revenir au scénario principal"}
        }

    def _build_hybrid_prompt(self, context: str, user_text: str, step: str) -> str:
        """Construit un prompt hybride avec contexte dynamique"""
        
        company = self.dynamic_prompts.get("company_info", {})
        style = self.dynamic_prompts.get("conversation_style", {})
        hybrid = self.dynamic_prompts.get("hybrid_mode_instructions", {})
        
        hybrid_prompt = f"""Tu es {style.get('personality', 'Thierry')} de {company.get('name', 'France Patrimoine')}.

CONTEXTE ENTREPRISE:
- Mission: {company.get('mission', 'Optimisation patrimoniale')}
- Ton: {company.get('tone', 'professionnel et chaleureux')}
- Style: {style.get('approach', 'Questions courtes et simples')}

SCÉNARIO PRINCIPAL:
{self.campaign_context}

ÉTAPE ACTUELLE: {step}

RÈGLES HYBRIDES:
- {hybrid.get('base_rule', 'TOUJOURS revenir au scénario principal')}
- Digression max: {hybrid.get('max_digression_time', '30 secondes')}
- Priorité: {hybrid.get('scenario_priority', 'Le scénario reste la trame principale')}

RÉPONSE CLIENT: "{user_text}"

Analyse cette réponse et détermine:
1. Si c'est une réponse directe au scénario → intent normal
2. Si c'est une question/objection hors-script → intent "digression" avec contextual_response

Réponds UNIQUEMENT en JSON: {{"intent": "...", "confidence": 0.9, "contextual_response": "...", "return_to_step": "..."}}"""

        return hybrid_prompt

    def _initialize_ollama(self):
        """Initialise la connexion Ollama"""
        if not OLLAMA_AVAILABLE:
            return False
            
        try:
            self.logger.info(f"🤖 Initializing Ollama client: {config.OLLAMA_URL}")
            self.ollama_client = ollama.Client(host=config.OLLAMA_URL)
            
            # Test de connexion et du modèle
            response = self.ollama_client.list()
            models = [model['name'] for model in response.get('models', [])]
            
            if config.OLLAMA_MODEL not in models:
                self.logger.warning(f"⚠️ Model {config.OLLAMA_MODEL} not found. Available: {models}")
                if models:
                    # Utiliser le premier modèle disponible
                    fallback_model = models[0]
                    self.logger.info(f"🔄 Using fallback model: {fallback_model}")
                    # Mettre à jour temporairement
                else:
                    self.logger.error("❌ No models available in Ollama")
                    self.is_available = False
                    return False
            
            # Test simple
            test_response = self.ollama_client.chat(
                model=config.OLLAMA_MODEL,
                messages=[
                    {"role": "system", "content": "Réponds juste 'OK' en JSON: {\"status\": \"OK\"}"},
                    {"role": "user", "content": "test"}
                ],
                options={
                    "temperature": 0.05,
                    "top_p": 0.15, 
                    "num_predict": 10
                }
            )
            
            self.stats["model_loaded"] = True
            self.logger.info(f"✅ Ollama initialized successfully with model {config.OLLAMA_MODEL}")
            return True
            
        except Exception as e:
            self.logger.error(f"❌ Failed to initialize Ollama: {e}")
            self.is_available = False
            return False

    def get_intent(self, text: str, context: str = "general", step: str = None, hybrid_mode: bool = True) -> Tuple[str, float, Dict[str, Any]]:
        """
        Analyse l'intention d'un texte avec mode hybride
        
        Args:
            text: Texte à analyser
            context: Contexte de la conversation (general, greeting, qualification, final_offer)
            step: Étape actuelle du scénario (pour mode hybride)
            hybrid_mode: Active le mode hybride (scénario + réponses libres)
            
        Returns:
            Tuple[intent, confidence, metadata]
            intent: string de l'intention détectée
            confidence: score de confiance 0-1
            metadata: informations supplémentaires + contexte hybride
        """
        start_time = time.time()
        self.stats["total_requests"] += 1
        
        # Nettoyage du texte
        text_clean = self._clean_text(text)
        if not text_clean:
            return "unsure", 0.0, {"method": "empty_text", "latency_ms": 0.0}
        
        # Tentative Ollama avec mode hybride
        if self.is_available and self.ollama_client:
            try:
                if hybrid_mode and step:
                    # Mode hybride - analyse contextuelle avancée
                    intent, confidence, metadata = self._get_intent_hybrid(text_clean, context, step)
                else:
                    # Mode classique
                    intent, confidence, metadata = self._get_intent_ollama(text_clean, context)
                
                latency_ms = (time.time() - start_time) * 1000
                self._update_latency_stats(latency_ms)
                
                if intent != "error":
                    self.stats["ollama_success"] += 1
                    metadata.update({
                        "method": "ollama_hybrid" if hybrid_mode else "ollama",
                        "latency_ms": latency_ms,
                        "meets_target": latency_ms < config.TARGET_INTENT_LATENCY,
                        "hybrid_mode": hybrid_mode
                    })
                    
                    mode_label = "🔄 Hybrid" if hybrid_mode else "🧠 Classic"
                    self.logger.debug(f"{mode_label} Ollama intent: '{text_clean}' → {intent} ({confidence:.2f}) [{latency_ms:.1f}ms]")
                    return intent, confidence, metadata
                    
            except Exception as e:
                self.logger.warning(f"⚠️ Ollama error for '{text_clean}': {e}")
        
        # Fallback sur sentiment service existant
        if SENTIMENT_FALLBACK_AVAILABLE and config.OLLAMA_FALLBACK_TO_KEYWORDS:
            try:
                intent, confidence, metadata = self._get_intent_fallback(text_clean, context)
                
                latency_ms = (time.time() - start_time) * 1000
                self.stats["fallback_used"] += 1
                
                metadata.update({
                    "method": "sentiment_fallback",
                    "latency_ms": latency_ms
                })
                
                self.logger.debug(f"🔄 Fallback intent: '{text_clean}' → {intent} ({confidence:.2f}) [{latency_ms:.1f}ms]")
                return intent, confidence, metadata
                
            except Exception as e:
                self.logger.error(f"❌ Fallback error for '{text_clean}': {e}")
        
        # Dernier recours - analyse simple par mots-clés
        intent, confidence, metadata = self._get_intent_keywords(text_clean, context)
        latency_ms = (time.time() - start_time) * 1000
        
        metadata.update({
            "method": "keywords_simple",
            "latency_ms": latency_ms
        })
        
        self.logger.debug(f"🔧 Keywords intent: '{text_clean}' → {intent} ({confidence:.2f}) [{latency_ms:.1f}ms]")
        return intent, confidence, metadata

    def _get_intent_ollama(self, text: str, context: str) -> Tuple[str, float, Dict[str, Any]]:
        """Analyse avec Ollama"""
        try:
            system_prompt = self.system_prompts.get(context, self.system_prompts["general"])
            
            response = self.ollama_client.chat(
                model=config.OLLAMA_MODEL,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": text}
                ],
                options={
                    "temperature": 0.05,  # Optimisé pour consistance JSON
                    "top_p": 0.15,        # Réduction pour réponses plus déterministes
                    "num_predict": 20,    # Optimisé pour réponses JSON courtes
                    "stop": ["}"]         # Arrêt après fermeture JSON
                }
            )
            
            # Parser la réponse JSON
            content = response['message']['content'].strip()
            
            # Nettoyer le JSON si nécessaire
            if content.startswith('```json'):
                content = content.replace('```json', '').replace('```', '').strip()
            
            try:
                result = json.loads(content)
                intent = result.get("intent", "unsure")
                confidence = float(result.get("confidence", 0.7))
                
                # Validation de l'intent
                valid_intents = ["Positif", "Négatif", "Neutre", "Unsure"]
                if intent not in valid_intents:
                    intent = "Unsure"
                    confidence = 0.5
                
                return intent, confidence, {"ollama_response": content, "context": context}
                
            except json.JSONDecodeError as e:
                self.logger.warning(f"⚠️ Invalid JSON from Ollama: {content}")
                return "error", 0.0, {"error": "json_decode", "raw_response": content}
                
        except Exception as e:
            self.logger.error(f"❌ Ollama request failed: {e}")
            return "error", 0.0, {"error": str(e)}

    def _get_intent_hybrid(self, text: str, context: str, step: str) -> Tuple[str, float, Dict[str, Any]]:
        """Analyse hybride avec détection de digressions et réponses contextuelles"""
        try:
            # Construire le prompt hybride
            hybrid_prompt = self._build_hybrid_prompt(context, text, step)
            
            # Utiliser Ollama avec le prompt hybride
            response = self.ollama_client.chat(
                model=config.OLLAMA_MODEL,
                messages=[
                    {"role": "system", "content": hybrid_prompt},
                    {"role": "user", "content": text}
                ],
                options={
                    "temperature": 0.05,
                    "top_p": 0.15,
                    "num_predict": 50,  # Plus long pour réponses hybrides
                    "stop": ["}"]
                }
            )
            
            # Parser la réponse JSON hybride
            content = response['message']['content'].strip()
            
            if content.startswith('```json'):
                content = content.replace('```json', '').replace('```', '').strip()
            
            try:
                result = json.loads(content)
                intent = result.get("intent", "unsure")
                confidence = float(result.get("confidence", 0.7))
                contextual_response = result.get("contextual_response", "")
                return_to_step = result.get("return_to_step", step)
                
                # Validation des intents simplifiés
                valid_intents = ["Positif", "Négatif", "Neutre", "Unsure"]
                if intent not in valid_intents:
                    intent = "Unsure"
                    confidence = 0.5
                
                metadata = {
                    "ollama_response": content,
                    "context": context,
                    "step": step,
                    "hybrid_mode": True
                }
                
                # Ajouter les données de digression si pertinentes
                if intent == "digression" and contextual_response:
                    metadata["contextual_response"] = contextual_response
                    metadata["return_to_step"] = return_to_step
                    
                    # Chercher réponse préfabriquée dans prompts_config
                    predefined_response = self._get_predefined_response(text)
                    if predefined_response:
                        metadata["predefined_response"] = predefined_response
                
                return intent, confidence, metadata
                
            except json.JSONDecodeError as e:
                self.logger.warning(f"⚠️ Invalid JSON from hybrid mode: {content}")
                # Fallback sur mode classique
                return self._get_intent_ollama(text, context)
                
        except Exception as e:
            self.logger.error(f"❌ Hybrid mode failed: {e}")
            # Fallback sur mode classique
            return self._get_intent_ollama(text, context)

    def _get_predefined_response(self, user_text: str) -> Optional[str]:
        """Cherche une réponse préfabriquée pour les questions courantes"""
        try:
            contextual_responses = self.dynamic_prompts.get("contextual_responses", {})
            objection_handling = self.dynamic_prompts.get("objection_handling", {})
            
            user_lower = user_text.lower()
            
            # Détection par mots-clés
            if any(word in user_lower for word in ["inflation", "taux", "rendement"]):
                return contextual_responses.get("inflation_question", "")
            elif any(word in user_lower for word in ["conseiller", "banque", "bancaire"]):
                return contextual_responses.get("bank_advisor_question", "")
            elif any(word in user_lower for word in ["prix", "coût", "cher", "gratuit"]):
                return objection_handling.get("price_concerns", {}).get("response", "")
            elif any(word in user_lower for word in ["temps", "occupé", "rapide"]):
                return objection_handling.get("time_constraints", {}).get("response", "")
            elif any(word in user_lower for word in ["confiance", "sérieux", "arnaque"]):
                return objection_handling.get("trust_issues", {}).get("response", "")
            
            return None
            
        except Exception as e:
            self.logger.warning(f"⚠️ Error in predefined response lookup: {e}")
            return None

    def _get_intent_fallback(self, text: str, context: str) -> Tuple[str, float, Dict[str, Any]]:
        """Fallback sur analyse par mots-clés"""
        sentiment, confidence = self._analyze_sentiment_keywords(text)
        
        # Mapper le sentiment vers intent simplifié
        sentiment_to_intent = {
            "positif": "Positif",
            "negatif": "Négatif", 
            "interrogatif": "Unsure",  # Questions → Unsure
            "neutre": "Neutre"
        }
        
        intent = sentiment_to_intent.get(sentiment, "Unsure")
        
        return intent, confidence, {"original_sentiment": sentiment, "context": context}

    def _get_intent_keywords(self, text: str, context: str) -> Tuple[str, float, Dict[str, Any]]:
        """Analyse simple par mots-clés"""
        text_lower = text.lower()
        
        # Mots-clés par intent simplifié
        keywords = {
            "Positif": ["oui", "ok", "d'accord", "allez-y", "parfait", "très bien", "exactement", "tout à fait", "intéresse", "intéressé"],
            "Négatif": ["non", "pas intéressé", "pas le temps", "arrêtez", "raccroc", "jamais", "n'ai pas besoin", "ça ne m'intéresse pas"],
            "Neutre": ["peut-être", "je ne sais pas", "il faut voir", "ça dépend", "rappel", "rappeler", "plus tard"],
            "Unsure": ["quoi", "comment", "pardon", "hein", "compris", "répéter", "combien", "prix", "qui"]
        }
        
        # Compter les matches
        scores = {}
        for intent, words in keywords.items():
            score = sum(1 for word in words if word in text_lower)
            if score > 0:
                scores[intent] = score / len(words)  # Score normalisé
        
        if scores:
            best_intent = max(scores, key=scores.get)
            confidence = min(scores[best_intent], 0.8)  # Cap à 0.8 pour keywords
            return best_intent, confidence, {"keyword_matches": scores}
        
        return "Unsure", 0.3, {"keyword_matches": {}}

    def _analyze_sentiment_keywords(self, text: str) -> Tuple[str, float]:
        """Analyse de sentiment simple par mots-clés"""
        text_lower = text.lower()
        
        positive_words = ["oui", "ok", "d'accord", "parfait", "bien", "intéresse", "génial"]
        negative_words = ["non", "pas", "jamais", "arrêt", "raccroc", "n'aime"]
        
        positive_count = sum(1 for word in positive_words if word in text_lower)
        negative_count = sum(1 for word in negative_words if word in text_lower)
        
        if positive_count > negative_count:
            return "positif", min(0.7, positive_count / len(positive_words))
        elif negative_count > positive_count:
            return "negatif", min(0.7, negative_count / len(negative_words))
        else:
            return "neutre", 0.5

    def _clean_text(self, text: str) -> str:
        """Nettoie le texte pour analyse"""
        if not text:
            return ""
        
        # Supprimer la ponctuation excessive et normaliser
        text = re.sub(r'[^\w\s\'-]', ' ', text)
        text = ' '.join(text.split())  # Normaliser les espaces
        
        return text.strip()

    def _update_latency_stats(self, latency_ms: float):
        """Met à jour les statistiques de latence"""
        if self.stats["ollama_success"] == 1:
            self.stats["avg_latency_ms"] = latency_ms
        else:
            # Moyenne mobile
            self.stats["avg_latency_ms"] = (
                self.stats["avg_latency_ms"] * 0.9 + latency_ms * 0.1
            )

    def get_stats(self) -> Dict[str, Any]:
        """Retourne les statistiques du service"""
        success_rate = 0.0
        if self.stats["total_requests"] > 0:
            success_rate = (self.stats["ollama_success"] / self.stats["total_requests"]) * 100
        
        fallback_rate = 0.0
        if self.stats["total_requests"] > 0:
            fallback_rate = (self.stats["fallback_used"] / self.stats["total_requests"]) * 100
        
        return {
            **self.stats,
            "is_available": self.is_available,
            "ollama_connected": self.ollama_client is not None,
            "success_rate_percent": success_rate,
            "fallback_rate_percent": fallback_rate,
            "sentiment_fallback_available": SENTIMENT_FALLBACK_AVAILABLE
        }

    def health_check(self) -> Dict[str, Any]:
        """Vérifie la santé du service"""
        health = {
            "status": "healthy",
            "ollama_available": False,
            "sentiment_fallback_available": SENTIMENT_FALLBACK_AVAILABLE,
            "total_methods_available": 0
        }
        
        # Test Ollama
        if self.is_available and self.ollama_client:
            try:
                test_response = self.ollama_client.list()
                health["ollama_available"] = True
                health["total_methods_available"] += 1
            except Exception as e:
                health["ollama_error"] = str(e)
        
        # Test fallback sentiment
        if SENTIMENT_FALLBACK_AVAILABLE:
            health["total_methods_available"] += 1
        
        # Keywords toujours disponible
        health["total_methods_available"] += 1
        
        if health["total_methods_available"] == 0:
            health["status"] = "unhealthy"
        elif not health["ollama_available"]:
            health["status"] = "degraded"
        
        return health
    
    def _call_ollama_direct(self, prompt: str) -> Optional[Dict]:
        """
        Appel direct à Ollama pour génération de texte freestyle
        Utilisé par le mode freestyle du scenario generator
        """
        if not self.is_available or not self.ollama_client:
            self.logger.warning("❌ Ollama non disponible pour appel direct")
            return None
        
        try:
            # Préparer le prompt avec contexte de conversation
            full_prompt = f"""Tu es un agent commercial expert. Réponds uniquement en JSON valide.

{prompt}

Réponds EXACTEMENT dans ce format JSON:
{{"text": "ta réponse commerciale (2-3 phrases)", "action": "continue|return_script|close_success|close_fail", "confidence": 0.8}}
"""
            
            # Appel Ollama
            response = self.ollama_client.generate(
                model=self.model_name,
                prompt=full_prompt,
                options={
                    "temperature": 0.3,  # Plus créatif pour le freestyle
                    "top_p": 0.9,
                    "top_k": 40
                }
            )
            
            if response and 'response' in response:
                response_text = response['response'].strip()
                
                # Tenter de parser le JSON
                try:
                    import json
                    # Extraire JSON de la réponse si nécessaire
                    json_start = response_text.find('{')
                    json_end = response_text.rfind('}') + 1
                    
                    if json_start != -1 and json_end > json_start:
                        json_str = response_text[json_start:json_end]
                        result = json.loads(json_str)
                        
                        # Valider la structure
                        if "text" in result and "action" in result:
                            self.logger.info(f"🤖 Ollama direct: {result['text'][:50]}... → {result['action']}")
                            return result
                    
                except json.JSONDecodeError:
                    self.logger.warning("⚠️ Réponse Ollama non-JSON, extraction manuelle")
                
                # Fallback: extraire manuellement
                return {
                    "text": response_text[:200] + "..." if len(response_text) > 200 else response_text,
                    "action": "continue",
                    "confidence": 0.5
                }
                
        except Exception as e:
            self.logger.error(f"❌ Erreur appel Ollama direct: {e}")
            
        return None

# Instance globale (singleton pattern comme autres services MiniBotPanel)
intent_engine = IntentEngine()

# Fonction de convenience pour compatibilité
def get_intent(text: str, context: str = "general") -> Tuple[str, float]:
    """
    Interface simple compatible avec l'architecture existante
    Retourne (intent, confidence)
    """
    intent, confidence, _ = intent_engine.get_intent(text, context)
    return intent, confidence

if __name__ == "__main__":
    # Test standalone
    def test_intent_engine():
        logger.info("🧪 Testing IntentEngine in standalone mode")
        
        test_cases = [
            ("oui ça me va", "greeting"),
            ("non pas intéressé", "greeting"), 
            ("combien ça coûte", "qualification"),
            ("d'accord rappellez-moi", "final_offer"),
            ("peut-être", "general"),
            ("", "general")  # Test texte vide
        ]
        
        for text, context in test_cases:
            intent, confidence, metadata = intent_engine.get_intent(text, context)
            print(f"Text: '{text}' | Context: {context}")
            print(f"→ Intent: {intent} | Confidence: {confidence:.2f} | Method: {metadata.get('method', 'unknown')}")
            print(f"  Latency: {metadata.get('latency_ms', 0):.1f}ms")
            print()
        
        # Afficher les stats
        stats = intent_engine.get_stats()
        print("📊 Stats:", json.dumps(stats, indent=2))
        
        # Health check
        health = intent_engine.health_check()
        print("🏥 Health:", json.dumps(health, indent=2))
    
    test_intent_engine()