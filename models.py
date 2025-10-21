from sqlalchemy import Column, Integer, String, Boolean, Float, Text, DateTime, ForeignKey, TIMESTAMP
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.sql import func
from datetime import datetime

Base = declarative_base()

class Call(Base):
    """Table calls - Main call records"""
    __tablename__ = "calls"
    
    id = Column(Integer, primary_key=True, index=True)
    call_id = Column(String(100), unique=True, index=True)
    phone_number = Column(String(20), nullable=False)
    campaign_id = Column(String(100), nullable=True)
    status = Column(String(50), nullable=False)  # initiated, answered, completed, failed
    amd_result = Column(String(20), nullable=True)  # human, machine, unknown
    final_sentiment = Column(String(20), nullable=True)  # positive, negative, unclear
    is_interested = Column(Boolean, default=False)
    duration = Column(Integer, nullable=True)  # en secondes
    recording_path = Column(String(255), nullable=True)
    assembled_audio_path = Column(String(255), nullable=True)  # Audio complet assemblé (bot + client)
    started_at = Column(DateTime, nullable=False)
    ended_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

class CallInteraction(Base):
    """Table call_interactions - Individual interactions within a call"""
    __tablename__ = "call_interactions"
    
    id = Column(Integer, primary_key=True, index=True)
    call_id = Column(String(100), ForeignKey("calls.call_id"), nullable=False)
    question_number = Column(Integer, nullable=False)
    question_played = Column(String(255), nullable=False)
    transcription = Column(Text, nullable=True)
    audio_path = Column(String(255), nullable=True)
    sentiment = Column(String(20), nullable=True)  # positive, negative, unclear
    confidence = Column(Float, nullable=True)  # Score 0-1
    response_duration = Column(Float, nullable=True)  # en secondes
    whisper_language = Column(String(10), nullable=True)
    whisper_metadata = Column(JSONB, nullable=True)
    played_at = Column(DateTime, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    
    # Nouvelles colonnes streaming
    intent = Column(String(50), nullable=True)  # intent detecté (affirm, deny, etc.)
    intent_confidence = Column(Float, nullable=True)  # confidence intent 0-1
    asr_latency_ms = Column(Float, nullable=True)  # latence ASR en ms
    intent_latency_ms = Column(Float, nullable=True)  # latence intent en ms
    barge_in_detected = Column(Boolean, default=False)  # barge-in utilisé
    processing_method = Column(String(20), nullable=True)  # "streaming" ou "classic"
    streaming_metadata = Column(JSONB, nullable=True)  # métadonnées streaming

class Campaign(Base):
    """Table campaigns - Call campaigns"""
    __tablename__ = "campaigns"
    
    id = Column(Integer, primary_key=True, index=True)
    campaign_id = Column(String(100), unique=True, index=True)
    name = Column(String(255), nullable=False)
    description = Column(Text, nullable=True)
    total_calls = Column(Integer, default=0)
    successful_calls = Column(Integer, default=0)
    positive_responses = Column(Integer, default=0)
    negative_responses = Column(Integer, default=0)
    status = Column(String(50), nullable=False)  # active, paused, completed
    started_at = Column(DateTime, nullable=False)
    completed_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

class Contact(Base):
    """Table contacts - Contact list for campaigns"""
    __tablename__ = "contacts"

    id = Column(Integer, primary_key=True, index=True)
    first_name = Column(String(100), nullable=True)
    last_name = Column(String(100), nullable=True)
    phone = Column(String(20), nullable=False, unique=True, index=True)
    email = Column(String(255), nullable=True)
    company = Column(String(255), nullable=True)
    status = Column(String(50), nullable=False, default="New")  # New, Calling, Completed, Leads, No_answer, Not_interested, Error
    priority = Column(Integer, default=1)
    attempts = Column(Integer, default=0)
    last_attempt = Column(DateTime, nullable=True)
    transcript = Column(Text, nullable=True)
    call_duration = Column(Integer, nullable=True)
    final_status = Column(String(50), nullable=True)
    audio_recording_path = Column(String(255), nullable=True)  # Chemin vers l'enregistrement complet
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

class CallQueue(Base):
    """Table call_queue - Queue d'appels à traiter avec throttling"""
    __tablename__ = "call_queue"

    id = Column(Integer, primary_key=True, index=True)
    campaign_id = Column(String(100), ForeignKey("campaigns.campaign_id"), nullable=False, index=True)
    phone_number = Column(String(20), nullable=False, index=True)
    scenario = Column(String(50), nullable=False)
    status = Column(String(50), nullable=False, default="pending", index=True)  # pending, calling, completed, failed, retrying
    priority = Column(Integer, default=1, index=True)  # 1=normal, 2=high, 3=urgent
    attempts = Column(Integer, default=0)
    max_attempts = Column(Integer, default=1)
    last_attempt_at = Column(DateTime, nullable=True)
    call_id = Column(String(100), nullable=True)  # ID de l'appel lancé (référence vers calls.call_id)
    error_message = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), index=True)
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())