#!/usr/bin/env python3
"""
Scénarios d'appel pour MiniBotPanel v2 - Version Streaming
Scénarios temps réel avec Vosk ASR + Ollama NLP + barge-in
Compatible avec l'architecture existante
"""

from datetime import datetime
from sqlalchemy.orm import Session
from database import SessionLocal
from models import Call, CallInteraction, Contact
from logger_config import get_logger
import time
import os
import asyncio
from typing import Dict, Any, Optional, Tuple

logger = get_logger(__name__)

# Import des services (avec fallback)
import config

# Services assemblage et transcription (existants gardés)
try:
    from services.audio_assembly_service import audio_assembly_service
    from services.transcript_service import transcript_service
    ASSEMBLY_AVAILABLE = True
except Exception as e:
    logger.warning(f"⚠️ Audio assembly/transcript services not available: {e}")
    ASSEMBLY_AVAILABLE = False

# Services streaming (requis)
logger.info("🤖 Loading streaming services for scenarios...")
try:
    from services.live_asr_vad import live_asr_vad_service
    from services.nlp_intent import intent_engine
    from services.amd_service import amd_service
    STREAMING_SERVICES_AVAILABLE = True
    logger.info("✅ Streaming services available for scenarios")
except Exception as e:
    logger.error(f"❌ Streaming services not available for scenarios: {e}")
    STREAMING_SERVICES_AVAILABLE = False
    raise RuntimeError("Streaming services required but not available")

# ============================================================================
# ⏱️ CONFIGURATION DES TEMPS D'ÉCOUTE (existant gardé + streaming)
# ============================================================================


# Configuration streaming
STREAMING_CONFIG = {
    "hello": {
        "barge_in_enabled": True,
        "max_wait_seconds": 15.0,
        "intent_mapping": {
            "affirm": "q1",
            "interested": "q1",
            "deny": "retry",
            "not_interested": "retry",
            "unsure": "retry",
            "callback": "retry"
        }
    },
    "retry": {
        "barge_in_enabled": True,
        "max_wait_seconds": 15.0,
        "intent_mapping": {
            "affirm": "q1",
            "interested": "q1",
            "deny": "bye_failed",
            "not_interested": "bye_failed",
            "unsure": "bye_failed"
        }
    },
    "q1": {
        "barge_in_enabled": True,
        "max_wait_seconds": 12.0,
        "intent_mapping": {
            "*": "q2"  # Toujours continuer
        }
    },
    "q2": {
        "barge_in_enabled": True,
        "max_wait_seconds": 12.0,
        "intent_mapping": {
            "*": "q3"  # Toujours continuer
        }
    },
    "q3": {
        "barge_in_enabled": True,
        "max_wait_seconds": 12.0,
        "intent_mapping": {
            "*": "is_leads"  # Toujours continuer
        }
    },
    "is_leads": {
        "barge_in_enabled": True,
        "max_wait_seconds": 15.0,
        "intent_mapping": {
            "affirm": "confirm",
            "interested": "confirm",
            "deny": "bye_failed",
            "not_interested": "bye_failed",
            "unsure": "bye_failed"
        }
    },
    "confirm": {
        "barge_in_enabled": True,
        "max_wait_seconds": 10.0,
        "intent_mapping": {
            "*": "bye_success"  # Toujours continuer
        }
    }
}

# ============================================================================
# SCÉNARIOS HYBRIDES - COMPATIBLE STREAMING ET CLASSIC
# ============================================================================

class ScenarioManager:
    """Gestionnaire de scénarios streaming temps réel"""
    
    def __init__(self):
        self.logger = get_logger(f"{__name__}.ScenarioManager")
        
    def execute_scenario(self, robot, channel_id: str, phone_number: str, campaign_id: str, 
                        scenario_name: str = "production"):
        """
        Exécute un scénario en mode streaming
        
        Args:
            robot: Instance RobotARI streaming
            channel_id: ID du canal Asterisk
            phone_number: Numéro appelé
            campaign_id: ID de campagne
            scenario_name: "production" ou "test"
        """
        if not STREAMING_SERVICES_AVAILABLE:
            raise RuntimeError("Streaming services required but not available")
        
        self.logger.info(f"🎬 Starting scenario '{scenario_name}' in streaming mode for {phone_number}")
        
        try:
            if scenario_name == "production":
                return self._scenario_production_streaming(robot, channel_id, phone_number, campaign_id)
            elif scenario_name == "test":
                return self._scenario_test_streaming(robot, channel_id, phone_number, campaign_id)
            else:
                self.logger.error(f"❌ Unknown scenario: {scenario_name}")
                return False
                
        except Exception as e:
            self.logger.error(f"❌ Error in scenario {scenario_name}: {e}", exc_info=True)
            return False
    
    
    # ========================================================================
    # SCÉNARIOS STREAMING (nouveaux)
    # ========================================================================
    
    def _scenario_production_streaming(self, robot, channel_id: str, phone_number: str, campaign_id: str) -> bool:
        """Scénario production en mode streaming avec barge-in et intent"""
        self.logger.info(f"🌊 Production scenario streaming for {phone_number}")
        
        try:
            # Initialiser tracking
            conversation_flow = []
            
            # Étape 1: Introduction
            step_result = self._execute_streaming_step(
                robot, channel_id, "hello", "hello.wav", phone_number
            )
            conversation_flow.append(step_result)
            
            # Décision basée sur intent
            if step_result["intent"] in ["affirm", "interested"]:
                # Client intéressé - continuer avec questions
                return self._continue_with_questions_streaming(
                    robot, channel_id, phone_number, campaign_id, conversation_flow
                )
            elif step_result["intent"] in ["deny", "not_interested"]:
                # Client pas intéressé - tenter retry
                return self._try_retry_streaming(
                    robot, channel_id, phone_number, campaign_id, conversation_flow
                )
            else:
                # Cas incertain - tenter retry également
                return self._try_retry_streaming(
                    robot, channel_id, phone_number, campaign_id, conversation_flow
                )
                
        except Exception as e:
            self.logger.error(f"❌ Error in production streaming scenario: {e}")
            return False
    
    def _execute_streaming_step(self, robot, channel_id: str, step_name: str, 
                               audio_file: str, phone_number: str) -> Dict[str, Any]:
        """Exécute une étape de scénario en mode streaming"""
        step_config = STREAMING_CONFIG.get(step_name, {})
        barge_in_enabled = step_config.get("barge_in_enabled", False)
        max_wait = step_config.get("max_wait_seconds", 10.0)
        
        self.logger.debug(f"🎯 Step {step_name}: {audio_file} (barge-in: {barge_in_enabled})")
        
        start_time = time.time()
        
        try:
            # Jouer audio avec barge-in
            robot.play_audio_file(channel_id, audio_file, enable_barge_in=barge_in_enabled)
            
            # Attendre réponse streaming
            response = robot._wait_for_streaming_response(channel_id, step_name, max_wait)
            
            # Enregistrer interaction
            self._save_interaction(channel_id, step_name, audio_file, response)
            
            elapsed_time = time.time() - start_time
            
            return {
                "step": step_name,
                "audio_file": audio_file,
                "intent": response.get("intent", "unsure"),
                "confidence": response.get("confidence", 0.0),
                "text": response.get("text", ""),
                "barge_in_used": response.get("barge_in_used", False),
                "elapsed_time": elapsed_time,
                "success": True
            }
            
        except Exception as e:
            self.logger.error(f"❌ Error in streaming step {step_name}: {e}")
            return {
                "step": step_name,
                "audio_file": audio_file,
                "intent": "error",
                "confidence": 0.0,
                "text": "",
                "error": str(e),
                "success": False
            }
    
    def _continue_with_questions_streaming(self, robot, channel_id: str, phone_number: str, 
                                         campaign_id: str, conversation_flow: list) -> bool:
        """Continue avec les questions de qualification en streaming"""
        self.logger.debug(f"❓ Qualification questions for {phone_number}")
        
        questions = [
            ("q1", "q1.wav"),
            ("q2", "q2.wav"), 
            ("q3", "q3.wav")
        ]
        
        # Poser toutes les questions
        for step_name, audio_file in questions:
            step_result = self._execute_streaming_step(
                robot, channel_id, step_name, audio_file, phone_number
            )
            conversation_flow.append(step_result)
            
            # En mode qualification, on continue même si réponse négative
            self.logger.debug(f"💬 {step_name} response: {step_result['intent']} ({step_result['confidence']:.2f})")
        
        # Question finale de leads
        return self._ask_final_leads_streaming(robot, channel_id, phone_number, campaign_id, conversation_flow)
    
    def _ask_final_leads_streaming(self, robot, channel_id: str, phone_number: str,
                                 campaign_id: str, conversation_flow: list) -> bool:
        """Question finale pour déterminer si c'est un lead"""
        self.logger.debug(f"🎯 Final leads question for {phone_number}")
        
        step_result = self._execute_streaming_step(
            robot, channel_id, "is_leads", "is_leads.wav", phone_number
        )
        conversation_flow.append(step_result)
        
        if step_result["intent"] in ["affirm", "interested"]:
            # C'est un lead !
            self.logger.info(f"✅ LEAD detected: {phone_number}")
            
            # Demander confirmation/créneau
            confirm_result = self._execute_streaming_step(
                robot, channel_id, "confirm", "confirm.wav", phone_number
            )
            conversation_flow.append(confirm_result)
            
            # Message de succès
            robot.play_audio_file(channel_id, "bye_success.wav")
            
            # Mettre à jour statut
            self._update_contact_status(phone_number, "Leads", conversation_flow)
            return True
            
        else:
            # Pas intéressé
            self.logger.info(f"❌ Not interested: {phone_number}")
            
            robot.play_audio_file(channel_id, "bye_failed.wav")
            
            self._update_contact_status(phone_number, "Not_interested", conversation_flow)
            return False
    
    def _try_retry_streaming(self, robot, channel_id: str, phone_number: str,
                           campaign_id: str, conversation_flow: list) -> bool:
        """Tentative de relance en mode streaming"""
        self.logger.debug(f"🔄 Retry attempt for {phone_number}")
        
        step_result = self._execute_streaming_step(
            robot, channel_id, "retry", "retry.wav", phone_number
        )
        conversation_flow.append(step_result)
        
        if step_result["intent"] in ["affirm", "interested"]:
            # Client accepte après retry
            return self._continue_with_questions_streaming(
                robot, channel_id, phone_number, campaign_id, conversation_flow
            )
        else:
            # Client refuse définitivement
            robot.play_audio_file(channel_id, "bye_failed.wav")
            
            self._update_contact_status(phone_number, "Not_interested", conversation_flow)
            return False
    
    def _scenario_test_streaming(self, robot, channel_id: str, phone_number: str, campaign_id: str) -> bool:
        """Scénario test simplifié en mode streaming"""
        self.logger.info(f"🧪 Test scenario streaming for {phone_number}")
        
        try:
            step_result = self._execute_streaming_step(
                robot, channel_id, "test", "test_audio.wav", phone_number
            )
            
            self.logger.info(f"🧪 Test result: {step_result['intent']} ({step_result['confidence']:.2f})")
            return True
            
        except Exception as e:
            self.logger.error(f"❌ Error in test streaming scenario: {e}")
            return False
    
    
    # ========================================================================
    # MÉTHODES UTILITAIRES COMMUNES
    # ========================================================================
    
    
    def _save_interaction(self, channel_id: str, step_name: str, audio_file: str, response: Dict[str, Any]):
        """Sauvegarde une interaction en base de données"""
        try:
            db = SessionLocal()
            
            interaction = CallInteraction(
                call_id=channel_id,
                question_number=self._get_question_number(step_name),
                question_played=audio_file,
                transcription=response.get("text", ""),
                sentiment=response.get("intent", "unsure"),
                confidence=response.get("confidence", 0.0),
                played_at=datetime.now()
            )
            
            db.add(interaction)
            db.commit()
            db.close()
            
            self.logger.debug(f"💾 Interaction saved: {step_name}")
            
        except Exception as e:
            self.logger.error(f"❌ Failed to save interaction: {e}")
    
    def _get_question_number(self, step_name: str) -> int:
        """Convertit le nom d'étape en numéro de question"""
        mapping = {
            "hello": 1,
            "retry": 2,
            "q1": 3,
            "q2": 4,
            "q3": 5,
            "is_leads": 6,
            "confirm": 7
        }
        return mapping.get(step_name, 0)
    
    def _update_contact_status(self, phone_number: str, status: str, conversation_flow: list = None):
        """Met à jour le statut d'un contact"""
        try:
            db = SessionLocal()
            
            contact = db.query(Contact).filter(Contact.phone == phone_number).first()
            if contact:
                contact.status = status
                contact.last_attempt = datetime.now()
                contact.attempts += 1
                
                # Sauvegarder conversation si disponible
                if conversation_flow and ASSEMBLY_AVAILABLE:
                    # TODO: Sauvegarder le flow de conversation
                    pass
                
                db.commit()
                self.logger.info(f"📊 Contact {phone_number} → {status}")
            
            db.close()
            
        except Exception as e:
            self.logger.error(f"❌ Failed to update contact status: {e}")

# ============================================================================
# INSTANCES GLOBALES ET FONCTIONS DE COMPATIBILITÉ
# ============================================================================

# Instance globale du gestionnaire
scenario_manager = ScenarioManager()

# Fonctions de compatibilité avec l'existant
def scenario_production(robot, channel_id: str, phone_number: str, campaign_id: str):
    """Fonction de compatibilité pour scenario_production existant"""
    return scenario_manager.execute_scenario(
        robot, channel_id, phone_number, campaign_id, "production"
    )

def scenario_test(robot, channel_id: str, phone_number: str, campaign_id: str):
    """Fonction de compatibilité pour scenario_test existant"""
    return scenario_manager.execute_scenario(
        robot, channel_id, phone_number, campaign_id, "test"
    )

# Nouvelles fonctions spécifiques
def scenario_production_streaming(robot, channel_id: str, phone_number: str, campaign_id: str):
    """Scénario production en mode streaming"""
    return scenario_manager.execute_scenario(
        robot, channel_id, phone_number, campaign_id, "production"
    )

def scenario_test_streaming(robot, channel_id: str, phone_number: str, campaign_id: str):
    """Scénario test en mode streaming"""
    return scenario_manager.execute_scenario(
        robot, channel_id, phone_number, campaign_id, "test"
    )

if __name__ == "__main__":
    # Test des scénarios
    logger.info("🧪 Testing scenario manager")
    
    # Test configuration
    manager = ScenarioManager()
    
    print(f"\n📋 Streaming config available: {bool(STREAMING_CONFIG)}")
    print(f"📋 Services available: streaming={STREAMING_SERVICES_AVAILABLE}, assembly={ASSEMBLY_AVAILABLE}")
    print(f"📋 Mode: streaming only")