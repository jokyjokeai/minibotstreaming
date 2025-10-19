from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import func
from database import get_db
from models import Call, Campaign, CallInteraction
from logger_config import get_logger

logger = get_logger(__name__)

router = APIRouter()

@router.get("/")
async def get_global_stats(db: Session = Depends(get_db)):
    """
    Statistiques globales du système
    """
    try:
        # Total calls by status
        total_calls = db.query(func.count(Call.id)).scalar() or 0
        completed_calls = db.query(func.count(Call.id)).filter(Call.status == "completed").scalar() or 0
        in_progress_calls = db.query(func.count(Call.id)).filter(Call.status.in_(["initiated", "answered"])).scalar() or 0
        failed_calls = db.query(func.count(Call.id)).filter(Call.status == "failed").scalar() or 0
        
        # Sentiment analysis
        positive_responses = db.query(func.count(Call.id)).filter(Call.final_sentiment == "positive").scalar() or 0
        negative_responses = db.query(func.count(Call.id)).filter(Call.final_sentiment == "negative").scalar() or 0
        unclear_responses = db.query(func.count(Call.id)).filter(Call.final_sentiment == "unclear").scalar() or 0
        
        # Interest rate
        interested_calls = db.query(func.count(Call.id)).filter(Call.is_interested == True).scalar() or 0
        
        # AMD statistics
        human_calls = db.query(func.count(Call.id)).filter(Call.amd_result == "human").scalar() or 0
        machine_calls = db.query(func.count(Call.id)).filter(Call.amd_result == "machine").scalar() or 0
        amd_unknown = db.query(func.count(Call.id)).filter(Call.amd_result.is_(None)).scalar() or 0
        
        # Success rate calculation
        success_rate = 0.0
        if completed_calls > 0:
            success_rate = (positive_responses / completed_calls) * 100
        
        # Interest rate calculation
        interest_rate = 0.0
        if total_calls > 0:
            interest_rate = (interested_calls / total_calls) * 100
        
        # Average call duration
        avg_duration = db.query(func.avg(Call.duration)).filter(Call.duration.isnot(None)).scalar() or 0
        
        # Campaign stats
        total_campaigns = db.query(func.count(Campaign.id)).scalar() or 0
        active_campaigns = db.query(func.count(Campaign.id)).filter(Campaign.status == "active").scalar() or 0
        completed_campaigns = db.query(func.count(Campaign.id)).filter(Campaign.status == "completed").scalar() or 0
        
        return {
            "success": True,
            "data": {
                "calls": {
                    "total": total_calls,
                    "completed": completed_calls,
                    "in_progress": in_progress_calls,
                    "failed": failed_calls
                },
                "sentiment": {
                    "positive": positive_responses,
                    "negative": negative_responses,
                    "unclear": unclear_responses
                },
                "rates": {
                    "success_rate": round(success_rate, 2),
                    "interest_rate": round(interest_rate, 2)
                },
                "performance": {
                    "average_duration_seconds": round(float(avg_duration), 2) if avg_duration else 0,
                    "interested_calls": interested_calls
                },
                "campaigns": {
                    "total": total_campaigns,
                    "active": active_campaigns,
                    "completed": completed_campaigns
                },
                "amd": {
                    "human_detected": human_calls,
                    "machine_detected": machine_calls,
                    "unknown": amd_unknown,
                    "human_rate": round((human_calls / total_calls * 100) if total_calls > 0 else 0, 2),
                    "machine_rate": round((machine_calls / total_calls * 100) if total_calls > 0 else 0, 2)
                }
            }
        }
        
    except Exception as e:
        logger.error(f"❌ Failed to get global stats: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/campaign/{campaign_id}")
async def get_campaign_stats(campaign_id: str, db: Session = Depends(get_db)):
    """
    Statistiques pour une campagne spécifique
    """
    try:
        # Verify campaign exists
        campaign = db.query(Campaign).filter(Campaign.campaign_id == campaign_id).first()
        if not campaign:
            raise HTTPException(status_code=404, detail="Campaign not found")
        
        # Get campaign calls
        campaign_calls = db.query(Call).filter(Call.campaign_id == campaign_id)
        
        total_calls = campaign_calls.count()
        completed_calls = campaign_calls.filter(Call.status == "completed").count()
        in_progress_calls = campaign_calls.filter(Call.status.in_(["initiated", "answered"])).count()
        failed_calls = campaign_calls.filter(Call.status == "failed").count()
        
        # Sentiment for this campaign
        positive_responses = campaign_calls.filter(Call.final_sentiment == "positive").count()
        negative_responses = campaign_calls.filter(Call.final_sentiment == "negative").count()
        unclear_responses = campaign_calls.filter(Call.final_sentiment == "unclear").count()
        
        # Interest for this campaign
        interested_calls = campaign_calls.filter(Call.is_interested == True).count()
        
        # Success and interest rates
        success_rate = (positive_responses / completed_calls * 100) if completed_calls > 0 else 0
        interest_rate = (interested_calls / total_calls * 100) if total_calls > 0 else 0
        
        # Average duration for this campaign
        avg_duration = db.query(func.avg(Call.duration)).filter(
            Call.campaign_id == campaign_id,
            Call.duration.isnot(None)
        ).scalar() or 0
        
        return {
            "success": True,
            "campaign_id": campaign_id,
            "campaign_name": campaign.name,
            "data": {
                "calls": {
                    "total": total_calls,
                    "completed": completed_calls,
                    "in_progress": in_progress_calls,
                    "failed": failed_calls
                },
                "sentiment": {
                    "positive": positive_responses,
                    "negative": negative_responses,
                    "unclear": unclear_responses
                },
                "rates": {
                    "success_rate": round(success_rate, 2),
                    "interest_rate": round(interest_rate, 2)
                },
                "performance": {
                    "average_duration_seconds": round(float(avg_duration), 2) if avg_duration else 0,
                    "interested_calls": interested_calls
                }
            }
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Failed to get campaign stats: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/sentiment-analysis")
async def get_sentiment_analysis_stats(db: Session = Depends(get_db)):
    """
    Statistiques détaillées de l'analyse de sentiment
    """
    try:
        # Sentiment distribution across all interactions
        sentiment_stats = db.query(
            CallInteraction.sentiment,
            func.count(CallInteraction.id).label("count"),
            func.avg(CallInteraction.confidence).label("avg_confidence")
        ).filter(
            CallInteraction.sentiment.isnot(None)
        ).group_by(CallInteraction.sentiment).all()
        
        # Language detection stats
        language_stats = db.query(
            CallInteraction.whisper_language,
            func.count(CallInteraction.id).label("count")
        ).filter(
            CallInteraction.whisper_language.isnot(None)
        ).group_by(CallInteraction.whisper_language).all()
        
        # Confidence distribution
        high_confidence = db.query(func.count(CallInteraction.id)).filter(
            CallInteraction.confidence >= 0.8
        ).scalar() or 0
        
        medium_confidence = db.query(func.count(CallInteraction.id)).filter(
            CallInteraction.confidence >= 0.5,
            CallInteraction.confidence < 0.8
        ).scalar() or 0
        
        low_confidence = db.query(func.count(CallInteraction.id)).filter(
            CallInteraction.confidence < 0.5,
            CallInteraction.confidence.isnot(None)
        ).scalar() or 0
        
        # Average response duration
        avg_response_duration = db.query(func.avg(CallInteraction.response_duration)).filter(
            CallInteraction.response_duration.isnot(None)
        ).scalar() or 0
        
        sentiment_data = []
        for stat in sentiment_stats:
            sentiment_data.append({
                "sentiment": stat.sentiment,
                "count": stat.count,
                "average_confidence": round(float(stat.avg_confidence), 3) if stat.avg_confidence else 0
            })
        
        language_data = []
        for stat in language_stats:
            language_data.append({
                "language": stat.whisper_language,
                "count": stat.count
            })
        
        return {
            "success": True,
            "data": {
                "sentiment_distribution": sentiment_data,
                "language_distribution": language_data,
                "confidence_distribution": {
                    "high_confidence": high_confidence,
                    "medium_confidence": medium_confidence,
                    "low_confidence": low_confidence
                },
                "performance": {
                    "average_response_duration_seconds": round(float(avg_response_duration), 2) if avg_response_duration else 0
                }
            }
        }
        
    except Exception as e:
        logger.error(f"❌ Failed to get sentiment analysis stats: {e}")
        raise HTTPException(status_code=500, detail=str(e))