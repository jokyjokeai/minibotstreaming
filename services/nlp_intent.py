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

# Import des configurations et services existants
import config
from logger_config import get_logger

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

    def __init__(self):
        self.logger = get_logger(f"{__name__}.IntentEngine")
        self.is_available = OLLAMA_AVAILABLE
        self.ollama_client = None
        
        # Statistiques
        self.stats = {
            "total_requests": 0,
            "ollama_success": 0,
            "fallback_used": 0,
            "avg_latency_ms": 0.0,
            "model_loaded": False
        }
        
        # Mapping des intents vers les statuts MiniBotPanel
        self.intent_to_status = {
            "affirm": "positive",
            "deny": "negative", 
            "callback": "positive",
            "price": "interrogatif",
            "unsure": "neutre",
            "interested": "positive",
            "not_interested": "negative"
        }
        
        # Prompts système optimisés pour le context français
        self.system_prompts = {
            "general": """Tu es un module NLP pour un robot d'appel français de qualification commerciale.
Analyse l'intention du client et réponds UNIQUEMENT en JSON au format {"intent": "...", "confidence": 0.9}.

Intents possibles :
- "affirm" : oui, d'accord, ok, tout à fait, absolument, évidemment
- "deny" : non, pas intéressé, pas le temps, pas maintenant  
- "callback" : rappel, rappeler, plus tard, demain, autre moment
- "price" : combien, coût, prix, tarif, cher, gratuit
- "interested" : intéressé, ça m'intéresse, dites-moi en plus
- "not_interested" : pas intéressé, n'ai pas besoin, ça ne m'intéresse pas
- "unsure" : peut-être, je ne sais pas, il faut que je réfléchisse

Réponds TOUJOURS en JSON valide.""",

            "greeting": """Tu analyses la réponse à une introduction commerciale.
Réponds UNIQUEMENT en JSON : {"intent": "...", "confidence": 0.9}

Contexte : "J'ai juste trois petites questions pour voir si nous pouvons vous aider à protéger, optimiser votre patrimoine. Ça vous va ?"

Intents :
- "affirm" : oui, ok, d'accord, allez-y, je vous écoute
- "deny" : non, pas le temps, pas intéressé, raccrochez
- "unsure" : peut-être, ça dépend, voyons
- "callback" : rappel plus tard, pas maintenant""",

            "qualification": """Tu analyses la réponse à une question de qualification financière.
Réponds UNIQUEMENT en JSON : {"intent": "...", "confidence": 0.9}

Intents :
- "affirm" : oui, j'ai, effectivement, bien sûr
- "deny" : non, je n'ai pas, pas du tout
- "price" : combien ça rapporte, quel taux, quel rendement
- "unsure" : je ne sais pas, peut-être, il faut voir""",

            "final_offer": """Tu analyses la réponse à une proposition de rappel commercial.
Réponds UNIQUEMENT en JSON : {"intent": "...", "confidence": 0.9}

Contexte : "Un de nos experts vous rappelle sous 48h pour analyser votre dossier. Ça vous va ?"

Intents :
- "affirm" : oui, d'accord, ok, parfait, allez-y
- "deny" : non, pas intéressé, ça ne m'intéresse pas
- "callback" : oui mais plus tard, pas cette semaine, dans un mois
- "price" : c'est gratuit, ça coûte combien, y a-t-il des frais"""
        }
        
        self._initialize_ollama()

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
                options={"temperature": 0.1}
            )
            
            self.stats["model_loaded"] = True
            self.logger.info(f"✅ Ollama initialized successfully with model {config.OLLAMA_MODEL}")
            return True
            
        except Exception as e:
            self.logger.error(f"❌ Failed to initialize Ollama: {e}")
            self.is_available = False
            return False

    def get_intent(self, text: str, context: str = "general") -> Tuple[str, float, Dict[str, Any]]:
        """
        Analyse l'intention d'un texte
        
        Args:
            text: Texte à analyser
            context: Contexte de la conversation (general, greeting, qualification, final_offer)
            
        Returns:
            Tuple[intent, confidence, metadata]
            intent: string de l'intention détectée
            confidence: score de confiance 0-1
            metadata: informations supplémentaires
        """
        start_time = time.time()
        self.stats["total_requests"] += 1
        
        # Nettoyage du texte
        text_clean = self._clean_text(text)
        if not text_clean:
            return "unsure", 0.0, {"method": "empty_text", "latency_ms": 0.0}
        
        # Tentative Ollama en premier
        if self.is_available and self.ollama_client:
            try:
                intent, confidence, metadata = self._get_intent_ollama(text_clean, context)
                
                latency_ms = (time.time() - start_time) * 1000
                self._update_latency_stats(latency_ms)
                
                if intent != "error":
                    self.stats["ollama_success"] += 1
                    metadata.update({
                        "method": "ollama",
                        "latency_ms": latency_ms,
                        "meets_target": latency_ms < config.TARGET_INTENT_LATENCY
                    })
                    
                    self.logger.debug(f"🧠 Ollama intent: '{text_clean}' → {intent} ({confidence:.2f}) [{latency_ms:.1f}ms]")
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
                    "temperature": 0.1,
                    "top_p": 0.9,
                    "num_predict": 50  # Limite les tokens pour rapidité
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
                valid_intents = ["affirm", "deny", "callback", "price", "interested", "not_interested", "unsure"]
                if intent not in valid_intents:
                    intent = "unsure"
                    confidence = 0.5
                
                return intent, confidence, {"ollama_response": content, "context": context}
                
            except json.JSONDecodeError as e:
                self.logger.warning(f"⚠️ Invalid JSON from Ollama: {content}")
                return "error", 0.0, {"error": "json_decode", "raw_response": content}
                
        except Exception as e:
            self.logger.error(f"❌ Ollama request failed: {e}")
            return "error", 0.0, {"error": str(e)}

    def _get_intent_fallback(self, text: str, context: str) -> Tuple[str, float, Dict[str, Any]]:
        """Fallback sur analyse par mots-clés"""
        sentiment, confidence = self._analyze_sentiment_keywords(text)
        
        # Mapper le sentiment vers intent
        sentiment_to_intent = {
            "positif": "affirm",
            "negatif": "deny", 
            "interrogatif": "price",
            "neutre": "unsure"
        }
        
        intent = sentiment_to_intent.get(sentiment, "unsure")
        
        # Ajustements contextuels
        if context == "final_offer" and sentiment == "positif":
            intent = "interested"
        elif context == "final_offer" and sentiment == "negatif":
            intent = "not_interested"
        
        return intent, confidence, {"original_sentiment": sentiment, "context": context}

    def _get_intent_keywords(self, text: str, context: str) -> Tuple[str, float, Dict[str, Any]]:
        """Analyse simple par mots-clés"""
        text_lower = text.lower()
        
        # Mots-clés par intent
        keywords = {
            "affirm": ["oui", "ok", "d'accord", "allez-y", "parfait", "très bien", "exactement", "tout à fait"],
            "deny": ["non", "pas intéressé", "pas le temps", "arrêtez", "raccroc", "jamais"],
            "callback": ["rappel", "rappeler", "plus tard", "demain", "semaine", "autre moment"],
            "price": ["combien", "coût", "prix", "tarif", "cher", "gratuit", "payant", "euros"],
            "interested": ["intéresse", "intéressé", "en savoir plus", "dites-moi"],
            "not_interested": ["pas intéressé", "n'ai pas besoin", "ça ne m'intéresse pas"]
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
        
        return "unsure", 0.3, {"keyword_matches": {}}

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