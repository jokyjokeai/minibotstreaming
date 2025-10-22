#!/usr/bin/env python3
"""
Streaming Stats Service - MiniBotPanel v2
Service pour analyser et fournir les statistiques streaming
"""

# Ajouter le répertoire parent au PYTHONPATH pour les imports
import sys
from pathlib import Path
current_dir = Path(__file__).parent
parent_dir = current_dir.parent
sys.path.insert(0, str(parent_dir))

from typing import Dict, List, Optional, Any
from datetime import datetime, timedelta
from sqlalchemy.orm import Session
from sqlalchemy import func, and_
from database import SessionLocal
from models import Call, CallInteraction, Campaign
from logger_config import get_logger
import json

logger = get_logger(__name__)

class StreamingStatsService:
    """Service de statistiques streaming pour MiniBotPanel v2"""
    
    def __init__(self):
        self.logger = get_logger(f"{__name__}.StreamingStatsService")
    
    def get_call_streaming_stats(self, call_id: str) -> Optional[Dict[str, Any]]:
        """
        Récupère les statistiques streaming pour un appel spécifique
        
        Args:
            call_id: ID de l'appel
            
        Returns:
            Dict avec les stats streaming ou None si pas trouvé
        """
        try:
            db = SessionLocal()
            
            # Récupérer l'appel
            call = db.query(Call).filter(Call.call_id == call_id).first()
            if not call:
                return None
            
            # Récupérer toutes les interactions
            interactions = db.query(CallInteraction).filter(
                CallInteraction.call_id == call_id
            ).order_by(CallInteraction.played_at).all()
            
            # Analyser les données streaming
            streaming_interactions = [i for i in interactions if i.processing_method == "streaming"]
            classic_interactions = [i for i in interactions if i.processing_method == "classic"]
            
            # Calculer les métriques
            stats = {
                "call_id": call_id,
                "phone_number": call.phone_number,
                "processing_mode": self._determine_call_mode(interactions),
                "total_interactions": len(interactions),
                "streaming_interactions": len(streaming_interactions),
                "classic_interactions": len(classic_interactions),
                
                # Métriques de latence
                "latency_metrics": self._calculate_latency_metrics(streaming_interactions),
                
                # Métriques barge-in
                "barge_in_metrics": self._calculate_barge_in_metrics(streaming_interactions),
                
                # Métriques intent
                "intent_metrics": self._calculate_intent_metrics(streaming_interactions),
                
                # Timeline détaillée
                "interaction_timeline": self._build_interaction_timeline(interactions),
                
                # Performance comparative
                "performance_comparison": self._compare_streaming_vs_classic(
                    streaming_interactions, classic_interactions
                )
            }
            
            db.close()
            return stats
            
        except Exception as e:
            self.logger.error(f"❌ Error getting streaming stats for {call_id}: {e}")
            return None
    
    def get_call_intent_analysis(self, call_id: str) -> Optional[Dict[str, Any]]:
        """
        Analyse détaillée des intents pour un appel
        
        Args:
            call_id: ID de l'appel
            
        Returns:
            Dict avec l'analyse des intents
        """
        try:
            db = SessionLocal()
            
            interactions = db.query(CallInteraction).filter(
                and_(
                    CallInteraction.call_id == call_id,
                    CallInteraction.intent.isnot(None)
                )
            ).order_by(CallInteraction.played_at).all()
            
            if not interactions:
                return None
            
            analysis = {
                "call_id": call_id,
                "total_intents": len(interactions),
                
                # Distribution des intents
                "intent_distribution": self._analyze_intent_distribution(interactions),
                
                # Évolution de la confiance
                "confidence_evolution": self._analyze_confidence_evolution(interactions),
                
                # Patterns conversationnels
                "conversation_patterns": self._analyze_conversation_patterns(interactions),
                
                # Décisions clés
                "key_decisions": self._identify_key_decisions(interactions),
                
                # Qualité de la détection
                "detection_quality": self._assess_detection_quality(interactions)
            }
            
            db.close()
            return analysis
            
        except Exception as e:
            self.logger.error(f"❌ Error getting intent analysis for {call_id}: {e}")
            return None
    
    def get_global_performance_stats(self, days: int = 7) -> Dict[str, Any]:
        """
        Statistiques de performance globales
        
        Args:
            days: Nombre de jours à analyser
            
        Returns:
            Dict avec les stats de performance
        """
        try:
            db = SessionLocal()
            
            # Période d'analyse
            since_date = datetime.now() - timedelta(days=days)
            
            # Requêtes de base
            total_calls = db.query(Call).filter(Call.started_at >= since_date).count()
            
            streaming_interactions = db.query(CallInteraction).filter(
                and_(
                    CallInteraction.created_at >= since_date,
                    CallInteraction.processing_method == "streaming"
                )
            ).all()
            
            classic_interactions = db.query(CallInteraction).filter(
                and_(
                    CallInteraction.created_at >= since_date,
                    CallInteraction.processing_method == "classic"
                )
            ).all()
            
            # Calculs globaux
            stats = {
                "analysis_period": {
                    "days": days,
                    "start_date": since_date.isoformat(),
                    "end_date": datetime.now().isoformat()
                },
                
                "global_metrics": {
                    "total_calls": total_calls,
                    "total_interactions": len(streaming_interactions) + len(classic_interactions),
                    "streaming_interactions": len(streaming_interactions),
                    "classic_interactions": len(classic_interactions),
                    "streaming_adoption_rate": (
                        len(streaming_interactions) / max(len(streaming_interactions) + len(classic_interactions), 1) * 100
                    )
                },
                
                # Performance streaming
                "streaming_performance": self._analyze_global_streaming_performance(streaming_interactions),
                
                # Comparaison modes
                "mode_comparison": self._compare_modes_globally(streaming_interactions, classic_interactions),
                
                # Tendances temporelles
                "temporal_trends": self._analyze_temporal_trends(streaming_interactions, classic_interactions, days),
                
                # Métriques système
                "system_health": self._assess_system_health(streaming_interactions, classic_interactions)
            }
            
            db.close()
            return stats
            
        except Exception as e:
            self.logger.error(f"❌ Error getting global performance stats: {e}")
            return {}
    
    # ========================================================================
    # MÉTHODES D'ANALYSE PRIVÉES
    # ========================================================================
    
    def _determine_call_mode(self, interactions: List[CallInteraction]) -> str:
        """Détermine le mode principal de l'appel"""
        streaming_count = sum(1 for i in interactions if i.processing_method == "streaming")
        classic_count = sum(1 for i in interactions if i.processing_method == "classic")
        
        if streaming_count > classic_count:
            return "streaming"
        elif classic_count > streaming_count:
            return "classic"
        else:
            return "hybrid"
    
    def _calculate_latency_metrics(self, interactions: List[CallInteraction]) -> Dict[str, Any]:
        """Calcule les métriques de latence"""
        if not interactions:
            return {}
        
        asr_latencies = [i.asr_latency_ms for i in interactions if i.asr_latency_ms is not None]
        intent_latencies = [i.intent_latency_ms for i in interactions if i.intent_latency_ms is not None]
        
        def calculate_stats(values):
            if not values:
                return None
            return {
                "min": min(values),
                "max": max(values),
                "avg": sum(values) / len(values),
                "count": len(values)
            }
        
        return {
            "asr_latency": calculate_stats(asr_latencies),
            "intent_latency": calculate_stats(intent_latencies),
            "total_latency": calculate_stats([
                (a or 0) + (i or 0) for a, i in zip(
                    [i.asr_latency_ms or 0 for i in interactions],
                    [i.intent_latency_ms or 0 for i in interactions]
                )
            ])
        }
    
    def _calculate_barge_in_metrics(self, interactions: List[CallInteraction]) -> Dict[str, Any]:
        """Calcule les métriques barge-in"""
        if not interactions:
            return {}
        
        total_interactions = len(interactions)
        barge_in_count = sum(1 for i in interactions if i.barge_in_detected)
        
        return {
            "total_opportunities": total_interactions,
            "barge_in_used": barge_in_count,
            "barge_in_rate": (barge_in_count / total_interactions * 100) if total_interactions > 0 else 0,
            "barge_in_by_step": self._group_barge_in_by_step(interactions)
        }
    
    def _group_barge_in_by_step(self, interactions: List[CallInteraction]) -> Dict[str, int]:
        """Groupe les barge-in par étape"""
        barge_in_by_step = {}
        for interaction in interactions:
            if interaction.barge_in_detected:
                step = interaction.question_played or "unknown"
                barge_in_by_step[step] = barge_in_by_step.get(step, 0) + 1
        return barge_in_by_step
    
    def _calculate_intent_metrics(self, interactions: List[CallInteraction]) -> Dict[str, Any]:
        """Calcule les métriques d'intent"""
        if not interactions:
            return {}
        
        intents = [i.intent for i in interactions if i.intent]
        confidences = [i.intent_confidence for i in interactions if i.intent_confidence is not None]
        
        intent_distribution = {}
        for intent in intents:
            intent_distribution[intent] = intent_distribution.get(intent, 0) + 1
        
        return {
            "total_intents": len(intents),
            "unique_intents": len(set(intents)),
            "intent_distribution": intent_distribution,
            "confidence_stats": {
                "avg": sum(confidences) / len(confidences) if confidences else 0,
                "min": min(confidences) if confidences else 0,
                "max": max(confidences) if confidences else 0
            }
        }
    
    def _build_interaction_timeline(self, interactions: List[CallInteraction]) -> List[Dict[str, Any]]:
        """Construit la timeline des interactions"""
        timeline = []
        
        for interaction in interactions:
            timeline.append({
                "timestamp": interaction.played_at.isoformat(),
                "question": interaction.question_played,
                "transcription": interaction.transcription,
                "intent": interaction.intent,
                "intent_confidence": interaction.intent_confidence,
                "processing_method": interaction.processing_method,
                "asr_latency_ms": interaction.asr_latency_ms,
                "intent_latency_ms": interaction.intent_latency_ms,
                "barge_in_detected": interaction.barge_in_detected
            })
        
        return timeline
    
    def _compare_streaming_vs_classic(self, streaming: List[CallInteraction], 
                                    classic: List[CallInteraction]) -> Dict[str, Any]:
        """Compare les performances streaming vs classic"""
        return {
            "streaming": {
                "count": len(streaming),
                "avg_confidence": sum(i.intent_confidence or i.confidence or 0 for i in streaming) / max(len(streaming), 1),
                "barge_in_usage": sum(1 for i in streaming if i.barge_in_detected)
            },
            "classic": {
                "count": len(classic),
                "avg_confidence": sum(i.confidence or 0 for i in classic) / max(len(classic), 1),
                "barge_in_usage": 0  # Classic mode doesn't support barge-in
            }
        }
    
    def _analyze_intent_distribution(self, interactions: List[CallInteraction]) -> Dict[str, Any]:
        """Analyse la distribution des intents"""
        intent_counts = {}
        intent_confidences = {}
        
        for interaction in interactions:
            if interaction.intent:
                intent = interaction.intent
                intent_counts[intent] = intent_counts.get(intent, 0) + 1
                
                if interaction.intent_confidence:
                    if intent not in intent_confidences:
                        intent_confidences[intent] = []
                    intent_confidences[intent].append(interaction.intent_confidence)
        
        # Calculer moyennes de confiance par intent
        intent_avg_confidence = {}
        for intent, confidences in intent_confidences.items():
            intent_avg_confidence[intent] = sum(confidences) / len(confidences)
        
        return {
            "counts": intent_counts,
            "average_confidence": intent_avg_confidence,
            "most_common": max(intent_counts, key=intent_counts.get) if intent_counts else None
        }
    
    def _analyze_confidence_evolution(self, interactions: List[CallInteraction]) -> List[Dict[str, Any]]:
        """Analyse l'évolution de la confiance au cours de l'appel"""
        evolution = []
        
        for i, interaction in enumerate(interactions):
            if interaction.intent_confidence is not None:
                evolution.append({
                    "step": i + 1,
                    "question": interaction.question_played,
                    "intent": interaction.intent,
                    "confidence": interaction.intent_confidence,
                    "timestamp": interaction.played_at.isoformat()
                })
        
        return evolution
    
    def _analyze_conversation_patterns(self, interactions: List[CallInteraction]) -> Dict[str, Any]:
        """Analyse les patterns conversationnels"""
        intent_sequence = [i.intent for i in interactions if i.intent]
        
        # Patterns communs
        patterns = {}
        for i in range(len(intent_sequence) - 1):
            pattern = f"{intent_sequence[i]} -> {intent_sequence[i+1]}"
            patterns[pattern] = patterns.get(pattern, 0) + 1
        
        return {
            "intent_sequence": intent_sequence,
            "common_patterns": patterns,
            "conversation_length": len(intent_sequence)
        }
    
    def _identify_key_decisions(self, interactions: List[CallInteraction]) -> List[Dict[str, Any]]:
        """Identifie les décisions clés de l'appel"""
        key_decisions = []
        
        for interaction in interactions:
            # Identifier les étapes cruciales
            if interaction.question_played in ["is_leads.wav", "hello.wav", "retry.wav"]:
                key_decisions.append({
                    "step": interaction.question_played,
                    "intent": interaction.intent,
                    "confidence": interaction.intent_confidence,
                    "transcription": interaction.transcription,
                    "importance": "high" if interaction.question_played == "is_leads.wav" else "medium"
                })
        
        return key_decisions
    
    def _assess_detection_quality(self, interactions: List[CallInteraction]) -> Dict[str, Any]:
        """Évalue la qualité de la détection d'intent"""
        if not interactions:
            return {}
        
        high_confidence = sum(1 for i in interactions if (i.intent_confidence or 0) > 0.8)
        medium_confidence = sum(1 for i in interactions if 0.5 <= (i.intent_confidence or 0) <= 0.8)
        low_confidence = sum(1 for i in interactions if (i.intent_confidence or 0) < 0.5)
        
        total = len(interactions)
        
        return {
            "high_confidence_rate": (high_confidence / total * 100) if total > 0 else 0,
            "medium_confidence_rate": (medium_confidence / total * 100) if total > 0 else 0,
            "low_confidence_rate": (low_confidence / total * 100) if total > 0 else 0,
            "quality_score": (high_confidence * 1.0 + medium_confidence * 0.6) / max(total, 1) * 100
        }
    
    def _analyze_global_streaming_performance(self, interactions: List[CallInteraction]) -> Dict[str, Any]:
        """Analyse la performance streaming globale"""
        if not interactions:
            return {}
        
        latencies = [i.asr_latency_ms for i in interactions if i.asr_latency_ms is not None]
        intent_latencies = [i.intent_latency_ms for i in interactions if i.intent_latency_ms is not None]
        
        return {
            "total_streaming_interactions": len(interactions),
            "average_asr_latency": sum(latencies) / len(latencies) if latencies else 0,
            "average_intent_latency": sum(intent_latencies) / len(intent_latencies) if intent_latencies else 0,
            "latency_target_compliance": {
                "asr_under_400ms": sum(1 for l in latencies if l < 400) / max(len(latencies), 1) * 100,
                "intent_under_600ms": sum(1 for l in intent_latencies if l < 600) / max(len(intent_latencies), 1) * 100
            },
            "barge_in_usage": sum(1 for i in interactions if i.barge_in_detected)
        }
    
    def _compare_modes_globally(self, streaming: List[CallInteraction], 
                               classic: List[CallInteraction]) -> Dict[str, Any]:
        """Compare les modes globalement"""
        total = len(streaming) + len(classic)
        
        return {
            "streaming_percentage": (len(streaming) / max(total, 1) * 100),
            "classic_percentage": (len(classic) / max(total, 1) * 100),
            "streaming_avg_confidence": sum(i.intent_confidence or 0 for i in streaming) / max(len(streaming), 1),
            "classic_avg_confidence": sum(i.confidence or 0 for i in classic) / max(len(classic), 1)
        }
    
    def _analyze_temporal_trends(self, streaming: List[CallInteraction], 
                               classic: List[CallInteraction], days: int) -> Dict[str, Any]:
        """Analyse les tendances temporelles"""
        # Grouper par jour
        daily_stats = {}
        
        all_interactions = streaming + classic
        for interaction in all_interactions:
            day = interaction.created_at.date().isoformat()
            if day not in daily_stats:
                daily_stats[day] = {"streaming": 0, "classic": 0}
            
            mode = interaction.processing_method or "unknown"
            if mode in daily_stats[day]:
                daily_stats[day][mode] += 1
        
        return {
            "daily_breakdown": daily_stats,
            "trend_direction": "increasing" if len(streaming) > len(classic) else "stable"
        }
    
    def _assess_system_health(self, streaming: List[CallInteraction], 
                            classic: List[CallInteraction]) -> Dict[str, Any]:
        """Évalue la santé du système"""
        streaming_errors = sum(1 for i in streaming if i.intent == "error" or i.sentiment == "error")
        classic_errors = sum(1 for i in classic if i.sentiment == "error")
        
        total_streaming = len(streaming)
        total_classic = len(classic)
        
        return {
            "streaming_error_rate": (streaming_errors / max(total_streaming, 1) * 100),
            "classic_error_rate": (classic_errors / max(total_classic, 1) * 100),
            "overall_health_score": max(0, 100 - (streaming_errors + classic_errors) / max(total_streaming + total_classic, 1) * 100)
        }

# Instance globale du service
streaming_stats_service = StreamingStatsService()

if __name__ == "__main__":
    # Test du service
    print("🧪 Testing Streaming Stats Service")
    
    # Test avec un call_id fictif
    stats = streaming_stats_service.get_call_streaming_stats("test-call-123")
    print(f"Call stats: {stats}")
    
    # Test stats globales
    global_stats = streaming_stats_service.get_global_performance_stats(7)
    print(f"Global stats keys: {list(global_stats.keys()) if global_stats else 'None'}")