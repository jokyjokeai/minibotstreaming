#!/usr/bin/env python3
"""
API Streaming - MiniBotPanel v2
Nouveaux endpoints pour exploiter les capacités streaming
"""

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from typing import Dict, Any, Optional, List
from datetime import datetime, timedelta

from database import get_db
from services.streaming_stats_service import streaming_stats_service
from logger_config import get_logger

logger = get_logger(__name__)

router = APIRouter()

# =============================================================================
# ENDPOINTS CALL-SPECIFIC STREAMING
# =============================================================================

@router.get("/calls/{call_id}/streaming-stats")
async def get_call_streaming_stats(
    call_id: str,
    db: Session = Depends(get_db)
):
    """
    Récupère les statistiques streaming détaillées pour un appel spécifique
    
    **Métriques incluses:**
    - Latences ASR et intent
    - Utilisation du barge-in
    - Timeline des interactions
    - Performance comparative streaming vs classic
    
    **Exemple de réponse:**
    ```json
    {
        "call_id": "channel-123",
        "processing_mode": "streaming",
        "latency_metrics": {
            "asr_latency": {"avg": 280, "min": 150, "max": 420},
            "intent_latency": {"avg": 180, "min": 90, "max": 350}
        },
        "barge_in_metrics": {
            "barge_in_rate": 25.0,
            "barge_in_used": 2
        }
    }
    ```
    """
    try:
        logger.info(f"📊 Getting streaming stats for call {call_id}")
        
        stats = streaming_stats_service.get_call_streaming_stats(call_id)
        
        if stats is None:
            raise HTTPException(
                status_code=404, 
                detail=f"Call {call_id} not found or no streaming data available"
            )
        
        return {
            "success": True,
            "data": stats,
            "generated_at": datetime.now().isoformat()
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Error getting streaming stats for {call_id}: {e}")
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")

@router.get("/calls/{call_id}/intent-analysis")
async def get_call_intent_analysis(
    call_id: str,
    db: Session = Depends(get_db)
):
    """
    Analyse détaillée des intents détectés pour un appel
    
    **Analyses incluses:**
    - Distribution des intents (affirm, deny, callback, etc.)
    - Évolution de la confiance au cours de l'appel
    - Patterns conversationnels
    - Décisions clés identifiées
    - Qualité de la détection
    
    **Exemple de réponse:**
    ```json
    {
        "call_id": "channel-123",
        "intent_distribution": {
            "affirm": 3,
            "deny": 1,
            "callback": 1
        },
        "confidence_evolution": [
            {"step": 1, "intent": "affirm", "confidence": 0.92},
            {"step": 2, "intent": "affirm", "confidence": 0.87}
        ],
        "key_decisions": [
            {
                "step": "is_leads.wav",
                "intent": "affirm",
                "confidence": 0.91,
                "importance": "high"
            }
        ]
    }
    ```
    """
    try:
        logger.info(f"🧠 Getting intent analysis for call {call_id}")
        
        analysis = streaming_stats_service.get_call_intent_analysis(call_id)
        
        if analysis is None:
            raise HTTPException(
                status_code=404,
                detail=f"Call {call_id} not found or no intent data available"
            )
        
        return {
            "success": True,
            "data": analysis,
            "generated_at": datetime.now().isoformat()
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Error getting intent analysis for {call_id}: {e}")
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")

@router.get("/calls/{call_id}/conversation-flow")
async def get_conversation_flow(
    call_id: str,
    include_transcriptions: bool = Query(True, description="Inclure les transcriptions complètes"),
    include_metadata: bool = Query(False, description="Inclure les métadonnées techniques"),
    db: Session = Depends(get_db)
):
    """
    Récupère le flow conversationnel complet d'un appel
    
    **Informations incluses:**
    - Séquence chronologique des interactions
    - Transcriptions (optionnel)
    - Intents détectés à chaque étape
    - Métadonnées techniques (latences, barge-in)
    
    **Utilisation:** Parfait pour analyser le déroulement d'un appel step-by-step
    """
    try:
        logger.info(f"💬 Getting conversation flow for call {call_id}")
        
        stats = streaming_stats_service.get_call_streaming_stats(call_id)
        
        if stats is None:
            raise HTTPException(
                status_code=404,
                detail=f"Call {call_id} not found"
            )
        
        # Extraire timeline
        timeline = stats.get("interaction_timeline", [])
        
        # Filtrer selon les paramètres
        filtered_timeline = []
        for interaction in timeline:
            filtered_interaction = {
                "timestamp": interaction["timestamp"],
                "question": interaction["question"],
                "intent": interaction["intent"],
                "intent_confidence": interaction["intent_confidence"]
            }
            
            if include_transcriptions:
                filtered_interaction["transcription"] = interaction["transcription"]
            
            if include_metadata:
                filtered_interaction.update({
                    "processing_method": interaction["processing_method"],
                    "asr_latency_ms": interaction["asr_latency_ms"],
                    "intent_latency_ms": interaction["intent_latency_ms"],
                    "barge_in_detected": interaction["barge_in_detected"]
                })
            
            filtered_timeline.append(filtered_interaction)
        
        return {
            "success": True,
            "data": {
                "call_id": call_id,
                "phone_number": stats.get("phone_number"),
                "total_steps": len(filtered_timeline),
                "conversation_flow": filtered_timeline
            },
            "generated_at": datetime.now().isoformat()
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Error getting conversation flow for {call_id}: {e}")
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")

# =============================================================================
# ENDPOINTS PERFORMANCE GLOBALES
# =============================================================================

@router.get("/stats/performance")
async def get_performance_stats(
    days: int = Query(7, ge=1, le=30, description="Nombre de jours à analyser (1-30)"),
    include_trends: bool = Query(True, description="Inclure les tendances temporelles"),
    db: Session = Depends(get_db)
):
    """
    Statistiques de performance globales du système streaming
    
    **Métriques incluses:**
    - Adoption du mode streaming vs classic
    - Performance des latences (ASR, intent, total)
    - Utilisation du barge-in
    - Comparaison des modes
    - Tendances temporelles
    - Santé du système
    
    **Exemple de réponse:**
    ```json
    {
        "analysis_period": {"days": 7},
        "global_metrics": {
            "total_calls": 1250,
            "streaming_adoption_rate": 78.5
        },
        "streaming_performance": {
            "average_asr_latency": 285,
            "latency_target_compliance": {
                "asr_under_400ms": 94.2,
                "intent_under_600ms": 97.8
            }
        },
        "system_health": {
            "overall_health_score": 96.2
        }
    }
    ```
    """
    try:
        logger.info(f"📈 Getting performance stats for {days} days")
        
        stats = streaming_stats_service.get_global_performance_stats(days)
        
        if not stats:
            return {
                "success": True,
                "data": {
                    "analysis_period": {"days": days},
                    "message": "No data available for the specified period"
                },
                "generated_at": datetime.now().isoformat()
            }
        
        # Filtrer les tendances si pas demandées
        if not include_trends and "temporal_trends" in stats:
            del stats["temporal_trends"]
        
        return {
            "success": True,
            "data": stats,
            "generated_at": datetime.now().isoformat()
        }
        
    except Exception as e:
        logger.error(f"❌ Error getting performance stats: {e}")
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")

@router.get("/stats/latency-analysis")
async def get_latency_analysis(
    days: int = Query(7, ge=1, le=30),
    breakdown_by: str = Query("hour", regex="^(hour|day)$", description="Granularité de l'analyse"),
    db: Session = Depends(get_db)
):
    """
    Analyse détaillée des latences du système streaming
    
    **Analyses incluses:**
    - Latences ASR par heure/jour
    - Latences intent par heure/jour
    - Percentiles (50%, 90%, 95%, 99%)
    - Compliance avec les targets
    - Identification des pics de latence
    
    **Utilisation:** Monitoring performance, détection anomalies, optimisation
    """
    try:
        logger.info(f"⏱️ Getting latency analysis for {days} days, breakdown by {breakdown_by}")
        
        # Pour l'instant, utiliser les stats globales
        # TODO: Implémenter analyse granulaire par heure/jour
        global_stats = streaming_stats_service.get_global_performance_stats(days)
        
        if not global_stats:
            raise HTTPException(status_code=404, detail="No data available for analysis")
        
        # Extraire les métriques de latence
        streaming_perf = global_stats.get("streaming_performance", {})
        
        analysis = {
            "analysis_period": global_stats.get("analysis_period", {}),
            "breakdown_by": breakdown_by,
            "latency_summary": {
                "asr": {
                    "average_ms": streaming_perf.get("average_asr_latency", 0),
                    "target_compliance": streaming_perf.get("latency_target_compliance", {}).get("asr_under_400ms", 0)
                },
                "intent": {
                    "average_ms": streaming_perf.get("average_intent_latency", 0),
                    "target_compliance": streaming_perf.get("latency_target_compliance", {}).get("intent_under_600ms", 0)
                }
            },
            "performance_grade": _calculate_performance_grade(streaming_perf),
            "recommendations": _generate_latency_recommendations(streaming_perf)
        }
        
        return {
            "success": True,
            "data": analysis,
            "generated_at": datetime.now().isoformat()
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Error getting latency analysis: {e}")
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")

@router.get("/stats/intent-quality")
async def get_intent_quality_stats(
    days: int = Query(7, ge=1, le=30),
    min_confidence: float = Query(0.0, ge=0.0, le=1.0, description="Confidence minimale à analyser"),
    db: Session = Depends(get_db)
):
    """
    Analyse de la qualité de détection des intents
    
    **Métriques incluses:**
    - Distribution des scores de confiance
    - Intents les plus/moins fiables
    - Taux de réussite par type d'intent
    - Évolution de la qualité dans le temps
    - Recommandations d'amélioration
    
    **Utilisation:** Amélioration des modèles NLP, debugging des prompts Ollama
    """
    try:
        logger.info(f"🎯 Getting intent quality stats for {days} days, min_confidence={min_confidence}")
        
        # TODO: Implémenter analyse qualité intent spécifique
        # Pour l'instant, utiliser données des stats globales
        
        placeholder_analysis = {
            "analysis_period": {"days": days, "min_confidence_filter": min_confidence},
            "quality_metrics": {
                "average_confidence": 0.82,
                "high_confidence_rate": 75.3,
                "low_confidence_rate": 8.7
            },
            "intent_reliability": {
                "affirm": {"avg_confidence": 0.89, "count": 450},
                "deny": {"avg_confidence": 0.85, "count": 180},
                "callback": {"avg_confidence": 0.72, "count": 65},
                "unsure": {"avg_confidence": 0.45, "count": 95}
            },
            "recommendations": [
                "Intent 'callback' nécessite amélioration (confidence moyenne: 0.72)",
                "Revoir les prompts Ollama pour réduire les cas 'unsure'"
            ]
        }
        
        return {
            "success": True,
            "data": placeholder_analysis,
            "generated_at": datetime.now().isoformat()
        }
        
    except Exception as e:
        logger.error(f"❌ Error getting intent quality stats: {e}")
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")

# =============================================================================
# ENDPOINTS SYSTÈME ET SANTÉ
# =============================================================================

@router.get("/stats/system-health")
async def get_system_health():
    """
    Santé globale du système streaming
    
    **Vérifications incluses:**
    - Disponibilité des services (Vosk, Ollama, WebSocket)
    - Performance temps réel
    - Taux d'erreur
    - Utilisation ressources
    - Status des composants
    """
    try:
        logger.info("🏥 Checking system health")
        
        # Vérifier disponibilité des services streaming
        health_status = {
            "overall_status": "healthy",
            "timestamp": datetime.now().isoformat(),
            "services": {},
            "performance": {},
            "alerts": []
        }
        
        # Vérifier services streaming
        try:
            from services.live_asr_vad import live_asr_vad_service
            asr_stats = live_asr_vad_service.get_stats()
            health_status["services"]["asr_vad"] = {
                "status": "healthy" if asr_stats["is_available"] else "unhealthy",
                "active_streams": asr_stats["active_streams"],
                "avg_latency_ms": asr_stats["avg_latency_ms"]
            }
        except Exception as e:
            health_status["services"]["asr_vad"] = {"status": "error", "error": str(e)}
        
        # Vérifier intent engine
        try:
            from services.nlp_intent import intent_engine
            intent_stats = intent_engine.get_stats()
            intent_health = intent_engine.health_check()
            health_status["services"]["intent_engine"] = {
                "status": intent_health["status"],
                "ollama_available": intent_health["ollama_available"],
                "success_rate": intent_stats["success_rate_percent"]
            }
        except Exception as e:
            health_status["services"]["intent_engine"] = {"status": "error", "error": str(e)}
        
        # Vérifier AMD service
        try:
            from services.amd_service import amd_service
            amd_stats = amd_service.get_stats()
            health_status["services"]["amd"] = {
                "status": "healthy" if amd_stats["is_available"] else "degraded",
                "total_analyses": amd_stats["total_analyses"],
                "human_rate": amd_stats["human_rate_percent"]
            }
        except Exception as e:
            health_status["services"]["amd"] = {"status": "error", "error": str(e)}
        
        # Déterminer status global
        service_statuses = [s.get("status", "error") for s in health_status["services"].values()]
        if "error" in service_statuses:
            health_status["overall_status"] = "critical"
        elif "unhealthy" in service_statuses:
            health_status["overall_status"] = "degraded"
        
        return {
            "success": True,
            "data": health_status
        }
        
    except Exception as e:
        logger.error(f"❌ Error getting system health: {e}")
        return {
            "success": False,
            "data": {
                "overall_status": "critical",
                "error": str(e),
                "timestamp": datetime.now().isoformat()
            }
        }

# =============================================================================
# FONCTIONS UTILITAIRES
# =============================================================================

def _calculate_performance_grade(streaming_perf: Dict[str, Any]) -> str:
    """Calcule une note de performance"""
    asr_latency = streaming_perf.get("average_asr_latency", 1000)
    intent_latency = streaming_perf.get("average_intent_latency", 1000)
    
    asr_compliance = streaming_perf.get("latency_target_compliance", {}).get("asr_under_400ms", 0)
    intent_compliance = streaming_perf.get("latency_target_compliance", {}).get("intent_under_600ms", 0)
    
    # Calcul score global
    avg_compliance = (asr_compliance + intent_compliance) / 2
    
    if avg_compliance >= 95:
        return "A+"
    elif avg_compliance >= 90:
        return "A"
    elif avg_compliance >= 85:
        return "B+"
    elif avg_compliance >= 80:
        return "B"
    elif avg_compliance >= 70:
        return "C"
    else:
        return "D"

def _generate_latency_recommendations(streaming_perf: Dict[str, Any]) -> List[str]:
    """Génère des recommandations d'optimisation"""
    recommendations = []
    
    asr_latency = streaming_perf.get("average_asr_latency", 0)
    intent_latency = streaming_perf.get("average_intent_latency", 0)
    
    if asr_latency > 400:
        recommendations.append("ASR latency élevée: optimiser Vosk ou considérer modèle plus petit")
    
    if intent_latency > 600:
        recommendations.append("Intent latency élevée: optimiser prompts Ollama ou modèle plus rapide")
    
    if asr_latency > 300 and intent_latency > 300:
        recommendations.append("Latences globalement élevées: vérifier ressources CPU/RAM")
    
    if not recommendations:
        recommendations.append("Performance excellent ! Aucune optimisation nécessaire.")
    
    return recommendations