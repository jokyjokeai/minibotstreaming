from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session
from sqlalchemy import desc
from pydantic import BaseModel
from typing import Optional, List
import os
from database import get_db
from models import Call, CallInteraction
from services.call_launcher import launch_call
from logger_config import get_logger
from config import RECORDINGS_PATH

logger = get_logger(__name__)

router = APIRouter()

# Chemins vers les enregistrements
ASSEMBLED_AUDIO_PATH = "assembled_audio"
TRANSCRIPTS_PATH = "transcripts"

class LaunchCallRequest(BaseModel):
    phone_number: str
    scenario: str = "production"
    campaign_id: Optional[str] = None

class CallResponse(BaseModel):
    id: int
    call_id: str
    phone_number: str
    campaign_id: Optional[str]
    status: str
    amd_result: Optional[str]
    final_sentiment: Optional[str]
    is_interested: bool
    duration: Optional[int]
    recording_path: Optional[str]  # Ancien (MixMonitor - deprecated)
    assembled_audio_path: Optional[str]  # NOUVEAU: Audio complet assemblé (bot + client)
    transcript_json_path: Optional[str]  # NOUVEAU: Transcription JSON
    transcript_txt_path: Optional[str]   # NOUVEAU: Transcription TXT
    started_at: str
    ended_at: Optional[str]

class InteractionResponse(BaseModel):
    id: int
    question_number: int
    question_played: str
    transcription: Optional[str]
    sentiment: Optional[str]
    confidence: Optional[float]
    response_duration: Optional[float]
    played_at: str

class CallDetailResponse(BaseModel):
    call: CallResponse
    interactions: List[InteractionResponse]

@router.post("/launch")
async def launch_single_call(request: LaunchCallRequest, db: Session = Depends(get_db)):
    """
    Lancer un appel unique
    """
    try:
        logger.info(f"📞 API request to launch call to {request.phone_number}")
        
        # Validate phone number (basic validation)
        if not request.phone_number or len(request.phone_number) < 10:
            raise HTTPException(status_code=400, detail="Invalid phone number")
        
        # Validate scenario
        valid_scenarios = ["production"]
        if request.scenario not in valid_scenarios:
            raise HTTPException(status_code=400, detail=f"Invalid scenario. Must be: production")
        
        # Launch call via ARI
        call_id = launch_call(
            phone_number=request.phone_number,
            scenario=request.scenario,
            campaign_id=request.campaign_id
        )
        
        return {
            "success": True,
            "call_id": call_id,
            "phone_number": request.phone_number,
            "scenario": request.scenario,
            "campaign_id": request.campaign_id
        }
        
    except Exception as e:
        logger.error(f"❌ Failed to launch call: {e}", exc_info=True)
        error_message = str(e)
        logger.error(f"Error details: {error_message}")
        raise HTTPException(status_code=500, detail=error_message)

@router.get("/")
async def list_calls(
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=1000),
    status: Optional[str] = Query(None),
    db: Session = Depends(get_db)
):
    """
    Liste des appels avec pagination
    """
    try:
        query = db.query(Call)
        
        if status:
            query = query.filter(Call.status == status)
        
        calls = query.order_by(desc(Call.created_at)).offset(skip).limit(limit).all()
        
        call_responses = []
        for call in calls:
            call_responses.append(CallResponse(
                id=call.id,
                call_id=call.call_id,
                phone_number=call.phone_number,
                campaign_id=call.campaign_id,
                status=call.status,
                amd_result=call.amd_result,
                final_sentiment=call.final_sentiment,
                is_interested=call.is_interested,
                duration=call.duration,
                recording_path=call.recording_path,
                assembled_audio_path=call.assembled_audio_path,
                transcript_json_path=f"{TRANSCRIPTS_PATH}/transcript_{call.call_id}.json" if call.assembled_audio_path else None,
                transcript_txt_path=f"{TRANSCRIPTS_PATH}/transcript_{call.call_id}.txt" if call.assembled_audio_path else None,
                started_at=call.started_at.isoformat(),
                ended_at=call.ended_at.isoformat() if call.ended_at else None
            ))
        
        return {
            "success": True,
            "calls": call_responses,
            "total": len(call_responses),
            "skip": skip,
            "limit": limit
        }
        
    except Exception as e:
        logger.error(f"❌ Failed to list calls: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/{call_id}")
async def get_call_details(call_id: str, db: Session = Depends(get_db)):
    """
    Détails d'un appel avec toutes les interactions
    """
    try:
        # Get call
        call = db.query(Call).filter(Call.call_id == call_id).first()
        if not call:
            raise HTTPException(status_code=404, detail="Call not found")
        
        # Get interactions
        interactions = db.query(CallInteraction).filter(
            CallInteraction.call_id == call_id
        ).order_by(CallInteraction.question_number).all()
        
        call_response = CallResponse(
            id=call.id,
            call_id=call.call_id,
            phone_number=call.phone_number,
            campaign_id=call.campaign_id,
            status=call.status,
            amd_result=call.amd_result,
            final_sentiment=call.final_sentiment,
            is_interested=call.is_interested,
            duration=call.duration,
            recording_path=call.recording_path,
            assembled_audio_path=call.assembled_audio_path,
            transcript_json_path=f"{TRANSCRIPTS_PATH}/transcript_{call.call_id}.json" if call.assembled_audio_path else None,
            transcript_txt_path=f"{TRANSCRIPTS_PATH}/transcript_{call.call_id}.txt" if call.assembled_audio_path else None,
            started_at=call.started_at.isoformat(),
            ended_at=call.ended_at.isoformat() if call.ended_at else None
        )
        
        interaction_responses = []
        for interaction in interactions:
            interaction_responses.append(InteractionResponse(
                id=interaction.id,
                question_number=interaction.question_number,
                question_played=interaction.question_played,
                transcription=interaction.transcription,
                sentiment=interaction.sentiment,
                confidence=interaction.confidence,
                response_duration=interaction.response_duration,
                played_at=interaction.played_at.isoformat()
            ))
        
        return {
            "success": True,
            "call": call_response,
            "interactions": interaction_responses
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Failed to get call details: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/recordings/{filename}")
async def get_recording(filename: str):
    """
    Télécharger ou écouter un enregistrement audio

    Usage: http://localhost:8000/calls/recordings/full_call_xxx.wav
    """
    try:
        # Sécurité: vérifier que le filename ne contient pas de path traversal
        if ".." in filename or "/" in filename:
            raise HTTPException(status_code=400, detail="Invalid filename")

        # Chemin complet du fichier
        file_path = os.path.join(RECORDINGS_PATH, filename)

        # Vérifier que le fichier existe
        if not os.path.exists(file_path):
            logger.warning(f"⚠️ Recording not found: {filename}")
            raise HTTPException(status_code=404, detail="Recording not found")

        logger.info(f"🎵 Serving recording: {filename}")

        # Retourner le fichier avec le bon content-type
        return FileResponse(
            file_path,
            media_type="audio/wav",
            filename=filename
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Failed to serve recording: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/assembled/{filename}")
async def get_assembled_audio(filename: str):
    """
    Télécharger l'audio complet assemblé (bot + client)

    Usage: http://localhost:8000/calls/assembled/full_call_assembled_xxx.wav
    """
    try:
        # Sécurité: vérifier que le filename ne contient pas de path traversal
        if ".." in filename or "/" in filename:
            raise HTTPException(status_code=400, detail="Invalid filename")

        # Chemin complet du fichier
        file_path = os.path.join(ASSEMBLED_AUDIO_PATH, filename)

        # Vérifier que le fichier existe
        if not os.path.exists(file_path):
            logger.warning(f"⚠️ Assembled audio not found: {filename}")
            raise HTTPException(status_code=404, detail="Assembled audio not found")

        logger.info(f"🎵 Serving assembled audio: {filename}")

        # Retourner le fichier avec le bon content-type
        return FileResponse(
            file_path,
            media_type="audio/wav",
            filename=filename
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Failed to serve assembled audio: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/transcripts/{call_id}.json")
async def get_transcript_json(call_id: str):
    """
    Télécharger la transcription complète en JSON

    Usage: http://localhost:8000/calls/transcripts/1760546116.43.json
    """
    try:
        # Sécurité: vérifier que le call_id ne contient pas de path traversal
        if ".." in call_id or "/" in call_id:
            raise HTTPException(status_code=400, detail="Invalid call_id")

        # Chemin complet du fichier
        filename = f"transcript_{call_id}.json"
        file_path = os.path.join(TRANSCRIPTS_PATH, filename)

        # Vérifier que le fichier existe
        if not os.path.exists(file_path):
            logger.warning(f"⚠️ Transcript JSON not found: {call_id}")
            raise HTTPException(status_code=404, detail="Transcript not found")

        logger.info(f"📝 Serving transcript JSON: {call_id}")

        # Retourner le fichier avec le bon content-type
        return FileResponse(
            file_path,
            media_type="application/json",
            filename=filename
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Failed to serve transcript JSON: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/transcripts/{call_id}.txt")
async def get_transcript_txt(call_id: str):
    """
    Télécharger la transcription complète en TXT (format lisible)

    Usage: http://localhost:8000/calls/transcripts/1760546116.43.txt
    """
    try:
        # Sécurité: vérifier que le call_id ne contient pas de path traversal
        if ".." in call_id or "/" in call_id:
            raise HTTPException(status_code=400, detail="Invalid call_id")

        # Chemin complet du fichier
        filename = f"transcript_{call_id}.txt"
        file_path = os.path.join(TRANSCRIPTS_PATH, filename)

        # Vérifier que le fichier existe
        if not os.path.exists(file_path):
            logger.warning(f"⚠️ Transcript TXT not found: {call_id}")
            raise HTTPException(status_code=404, detail="Transcript not found")

        logger.info(f"📝 Serving transcript TXT: {call_id}")

        # Retourner le fichier avec le bon content-type
        return FileResponse(
            file_path,
            media_type="text/plain; charset=utf-8",
            filename=filename
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Failed to serve transcript TXT: {e}")
        raise HTTPException(status_code=500, detail=str(e))