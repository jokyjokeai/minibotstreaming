from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from sqlalchemy import desc
from pydantic import BaseModel
from typing import Optional, List
from database import get_db
from models import Campaign, Call, CallQueue
from services.call_launcher import launch_call
import uuid
from datetime import datetime
from logger_config import get_logger

logger = get_logger(__name__)

router = APIRouter()

class CreateCampaignRequest(BaseModel):
    name: str
    description: Optional[str] = None
    phone_numbers: List[str]
    scenario: str = "production"

class CampaignResponse(BaseModel):
    id: int
    campaign_id: str
    name: str
    description: Optional[str]
    total_calls: int
    successful_calls: int
    positive_responses: int
    negative_responses: int
    status: str
    started_at: str
    completed_at: Optional[str]

class CampaignCallResponse(BaseModel):
    id: int
    call_id: str
    phone_number: str
    status: str
    final_sentiment: Optional[str]
    is_interested: bool
    duration: Optional[int]
    started_at: str
    ended_at: Optional[str]

class CampaignDetailResponse(BaseModel):
    campaign: CampaignResponse
    calls: List[CampaignCallResponse]

@router.post("/create")
async def create_campaign(request: CreateCampaignRequest, db: Session = Depends(get_db)):
    """
    Créer et lancer une campagne d'appels
    """
    try:
        logger.info(f"📢 Creating campaign: {request.name} with {len(request.phone_numbers)} numbers")
        
        # Validate inputs
        if not request.phone_numbers:
            raise HTTPException(status_code=400, detail="No phone numbers provided")
        
        if len(request.phone_numbers) > 1000:
            raise HTTPException(status_code=400, detail="Too many phone numbers (max: 1000)")
        
        valid_scenarios = ["production"]
        if request.scenario not in valid_scenarios:
            raise HTTPException(status_code=400, detail=f"Invalid scenario. Must be: production")
        
        # Generate unique campaign ID
        campaign_id = f"camp_{uuid.uuid4().hex[:8]}"
        
        # Create campaign record
        campaign = Campaign(
            campaign_id=campaign_id,
            name=request.name,
            description=request.description,
            total_calls=len(request.phone_numbers),
            status="active",
            started_at=datetime.now()
        )
        
        db.add(campaign)
        db.commit()
        
        logger.info(f"✅ Campaign created: {campaign_id}")

        # Ajouter tous les appels dans la queue (pas de lancement direct)
        # Le batch_caller va les traiter avec throttling
        queued_calls = 0
        failed_calls = 0

        for phone_number in request.phone_numbers:
            try:
                # Créer entrée dans call_queue
                queue_item = CallQueue(
                    campaign_id=campaign_id,
                    phone_number=phone_number,
                    scenario=request.scenario,
                    status="pending",
                    priority=1,  # Priorité normale par défaut
                    max_attempts=1
                )

                db.add(queue_item)
                queued_calls += 1

            except Exception as e:
                failed_calls += 1
                logger.error(f"❌ Failed to queue call to {phone_number}: {e}")

        # Commit tous les ajouts à la queue
        db.commit()

        logger.info(f"✅ {queued_calls} appel(s) ajouté(s) à la queue pour campagne {campaign.name}")
        logger.info(f"📡 Le batch_caller va traiter ces appels avec throttling")

        return {
            "success": True,
            "campaign_id": campaign_id,
            "name": request.name,
            "total_calls": len(request.phone_numbers),
            "queued": queued_calls,
            "failed": failed_calls,
            "message": f"{queued_calls} appels ajoutés à la queue. Le batch_caller va les traiter automatiquement."
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Failed to create campaign: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/")
async def list_campaigns(
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=1000),
    db: Session = Depends(get_db)
):
    """
    Liste de toutes les campagnes
    """
    try:
        campaigns = db.query(Campaign).order_by(desc(Campaign.created_at)).offset(skip).limit(limit).all()
        
        campaign_responses = []
        for campaign in campaigns:
            campaign_responses.append(CampaignResponse(
                id=campaign.id,
                campaign_id=campaign.campaign_id,
                name=campaign.name,
                description=campaign.description,
                total_calls=campaign.total_calls,
                successful_calls=campaign.successful_calls,
                positive_responses=campaign.positive_responses,
                negative_responses=campaign.negative_responses,
                status=campaign.status,
                started_at=campaign.started_at.isoformat(),
                completed_at=campaign.completed_at.isoformat() if campaign.completed_at else None
            ))
        
        return {
            "success": True,
            "campaigns": campaign_responses,
            "total": len(campaign_responses),
            "skip": skip,
            "limit": limit
        }
        
    except Exception as e:
        logger.error(f"❌ Failed to list campaigns: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/{campaign_id}")
async def get_campaign_details(campaign_id: str, db: Session = Depends(get_db)):
    """
    Détails d'une campagne avec tous ses appels
    """
    try:
        # Get campaign
        campaign = db.query(Campaign).filter(Campaign.campaign_id == campaign_id).first()
        if not campaign:
            raise HTTPException(status_code=404, detail="Campaign not found")
        
        # Get all calls for this campaign
        calls = db.query(Call).filter(Call.campaign_id == campaign_id).order_by(desc(Call.started_at)).all()
        
        campaign_response = CampaignResponse(
            id=campaign.id,
            campaign_id=campaign.campaign_id,
            name=campaign.name,
            description=campaign.description,
            total_calls=campaign.total_calls,
            successful_calls=campaign.successful_calls,
            positive_responses=campaign.positive_responses,
            negative_responses=campaign.negative_responses,
            status=campaign.status,
            started_at=campaign.started_at.isoformat(),
            completed_at=campaign.completed_at.isoformat() if campaign.completed_at else None
        )
        
        call_responses = []
        for call in calls:
            call_responses.append(CampaignCallResponse(
                id=call.id,
                call_id=call.call_id,
                phone_number=call.phone_number,
                status=call.status,
                final_sentiment=call.final_sentiment,
                is_interested=call.is_interested,
                duration=call.duration,
                started_at=call.started_at.isoformat(),
                ended_at=call.ended_at.isoformat() if call.ended_at else None
            ))
        
        return {
            "success": True,
            "campaign": campaign_response,
            "calls": call_responses
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Failed to get campaign details: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.patch("/{campaign_id}/status")
async def update_campaign_status(
    campaign_id: str,
    status: str,
    db: Session = Depends(get_db)
):
    """
    Mettre à jour le statut d'une campagne (active, paused, completed)
    """
    try:
        valid_statuses = ["active", "paused", "completed"]
        if status not in valid_statuses:
            raise HTTPException(status_code=400, detail=f"Invalid status. Must be one of: {valid_statuses}")
        
        campaign = db.query(Campaign).filter(Campaign.campaign_id == campaign_id).first()
        if not campaign:
            raise HTTPException(status_code=404, detail="Campaign not found")
        
        campaign.status = status
        if status == "completed":
            campaign.completed_at = datetime.now()
        
        db.commit()
        
        logger.info(f"📊 Campaign status updated: {campaign_id} -> {status}")
        
        return {
            "success": True,
            "campaign_id": campaign_id,
            "status": status
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Failed to update campaign status: {e}")
        raise HTTPException(status_code=500, detail=str(e))