#!/usr/bin/env python3
"""
API de téléchargement sécurisé - MiniBotPanel v2  
Endpoints pour télécharger les enregistrements complets d'appels
Avec authentification par token temporaire et sécurité renforcée
"""

import os
import json
import hashlib
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional, Dict

from fastapi import APIRouter, HTTPException, Query, Request
from fastapi.responses import FileResponse, JSONResponse
from fastapi.security import HTTPBearer

# Ajouter le répertoire parent au PYTHONPATH pour les imports
import sys
from pathlib import Path
current_dir = Path(__file__).parent
parent_dir = current_dir.parent
sys.path.insert(0, str(parent_dir))

from logger_config import get_logger
from config import RECORDINGS_PATH

logger = get_logger(__name__)

# Router pour les téléchargements
downloads_router = APIRouter(prefix="/api/downloads", tags=["downloads"])

# Configuration
TRANSCRIPTS_PATH = Path(__file__).parent.parent / "transcripts"
TOKENS_FILE = TRANSCRIPTS_PATH / "download_tokens.json"

class SecureDownloadManager:
    """Gestionnaire de téléchargements sécurisés"""
    
    def __init__(self):
        self.logger = get_logger(f"{__name__}.SecureDownloadManager")
        
    def validate_token(self, call_id: str, token: str, client_ip: str) -> Optional[Dict]:
        """
        Valide un token de téléchargement
        
        Args:
            call_id: ID de l'appel
            token: Token fourni par le client
            client_ip: IP du client
            
        Returns:
            Dict avec infos du token si valide, None sinon
        """
        try:
            if not TOKENS_FILE.exists():
                self.logger.warning(f"❌ Tokens file not found: {TOKENS_FILE}")
                return None
            
            with open(TOKENS_FILE, 'r') as f:
                tokens_data = json.load(f)
            
            token_info = tokens_data.get(call_id)
            if not token_info:
                self.logger.warning(f"❌ No token found for call {call_id}")
                return None
            
            # Vérifier token
            if token_info.get("token") != token:
                self.logger.warning(f"❌ Invalid token for call {call_id} from {client_ip}")
                return None
            
            # Vérifier expiration
            expires = token_info.get("expires", 0)
            now = int(datetime.now().timestamp())
            
            if now > expires:
                self.logger.warning(f"❌ Expired token for call {call_id}")
                # Nettoyer token expiré
                del tokens_data[call_id]
                with open(TOKENS_FILE, 'w') as f:
                    json.dump(tokens_data, f, indent=2)
                return None
            
            self.logger.info(f"✅ Valid token for call {call_id} from {client_ip}")
            return token_info
            
        except Exception as e:
            self.logger.error(f"❌ Token validation error: {e}")
            return None
    
    def get_file_info(self, file_path: str) -> Dict:
        """Obtient les informations d'un fichier"""
        try:
            if not os.path.exists(file_path):
                return {"exists": False}
            
            stat = os.stat(file_path)
            return {
                "exists": True,
                "size": stat.st_size,
                "modified": datetime.fromtimestamp(stat.st_mtime).isoformat(),
                "size_mb": round(stat.st_size / 1024 / 1024, 2)
            }
        except Exception as e:
            self.logger.error(f"❌ File info error: {e}")
            return {"exists": False, "error": str(e)}
    
    def log_download(self, call_id: str, client_ip: str, file_path: str, success: bool):
        """Log les téléchargements pour audit"""
        try:
            log_entry = {
                "timestamp": datetime.now().isoformat(),
                "call_id": call_id,
                "client_ip": client_ip,
                "file_path": file_path,
                "success": success,
                "user_agent": "unknown"  # TODO: récupérer depuis request
            }
            
            # Log dans fichier audit
            audit_file = TRANSCRIPTS_PATH / "download_audit.jsonl"
            with open(audit_file, 'a') as f:
                f.write(json.dumps(log_entry) + "\n")
                
            if success:
                self.logger.info(f"📥 Download successful: {call_id} by {client_ip}")
            else:
                self.logger.warning(f"❌ Download failed: {call_id} by {client_ip}")
                
        except Exception as e:
            self.logger.error(f"❌ Download logging error: {e}")
    
    def cleanup_expired_tokens(self):
        """Nettoie les tokens expirés (tâche de maintenance)"""
        try:
            if not TOKENS_FILE.exists():
                return
            
            with open(TOKENS_FILE, 'r') as f:
                tokens_data = json.load(f)
            
            now = int(datetime.now().timestamp())
            cleaned_tokens = {}
            expired_count = 0
            
            for call_id, token_info in tokens_data.items():
                expires = token_info.get("expires", 0)
                if now <= expires:
                    cleaned_tokens[call_id] = token_info
                else:
                    expired_count += 1
            
            if expired_count > 0:
                with open(TOKENS_FILE, 'w') as f:
                    json.dump(cleaned_tokens, f, indent=2)
                
                self.logger.info(f"🧹 Cleaned {expired_count} expired tokens")
                
        except Exception as e:
            self.logger.error(f"❌ Token cleanup error: {e}")


# Instance globale
download_manager = SecureDownloadManager()


@downloads_router.get("/call-audio/{call_id}")
async def download_call_audio(
    call_id: str,
    token: str = Query(..., description="Token de sécurité temporaire"),
    expires: Optional[int] = Query(None, description="Timestamp d'expiration"),
    request: Request = None
):
    """
    Télécharge l'enregistrement complet d'un appel
    
    - **call_id**: ID de l'appel
    - **token**: Token de sécurité généré lors du traitement
    - **expires**: Timestamp d'expiration (optionnel, pour vérification)
    """
    try:
        # Obtenir IP client
        client_ip = request.client.host if request else "unknown"
        
        # Validation token
        token_info = download_manager.validate_token(call_id, token, client_ip)
        if not token_info:
            download_manager.log_download(call_id, client_ip, "", False)
            raise HTTPException(
                status_code=403, 
                detail="Token invalide ou expiré"
            )
        
        # Vérification fichier
        file_path = token_info.get("file_path")
        if not file_path:
            download_manager.log_download(call_id, client_ip, "", False)
            raise HTTPException(
                status_code=404,
                detail="Chemin de fichier non trouvé"
            )
        
        file_info = download_manager.get_file_info(file_path)
        if not file_info.get("exists"):
            download_manager.log_download(call_id, client_ip, file_path, False)
            raise HTTPException(
                status_code=404,
                detail="Fichier d'enregistrement non trouvé"
            )
        
        # Log et retourner fichier
        download_manager.log_download(call_id, client_ip, file_path, True)
        
        # Headers sécurisés
        headers = {
            "Content-Disposition": f"attachment; filename=call_{call_id}_complete.wav",
            "Content-Type": "audio/wav",
            "X-Content-Type-Options": "nosniff",
            "X-Frame-Options": "DENY"
        }
        
        logger.info(f"📥 Serving audio file: {file_path} ({file_info['size_mb']} MB)")
        
        return FileResponse(
            file_path,
            headers=headers,
            media_type="audio/wav"
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Download error for call {call_id}: {e}")
        download_manager.log_download(call_id, client_ip, "", False)
        raise HTTPException(
            status_code=500,
            detail="Erreur interne lors du téléchargement"
        )


@downloads_router.get("/call-transcript/{call_id}")
async def download_call_transcript(
    call_id: str,
    format: str = Query("json", regex="^(json|txt)$", description="Format: json ou txt"),
    token: str = Query(..., description="Token de sécurité"),
    request: Request = None
):
    """
    Télécharge la transcription d'un appel
    
    - **call_id**: ID de l'appel
    - **format**: Format de sortie (json ou txt)
    - **token**: Token de sécurité
    """
    try:
        client_ip = request.client.host if request else "unknown"
        
        # Validation token (même système que pour l'audio)
        token_info = download_manager.validate_token(call_id, token, client_ip)
        if not token_info:
            raise HTTPException(status_code=403, detail="Token invalide")
        
        # Fichier transcription
        if format == "json":
            transcript_file = TRANSCRIPTS_PATH / f"complete_call_{call_id}.json"
            media_type = "application/json"
            filename = f"transcript_{call_id}.json"
        else:
            transcript_file = TRANSCRIPTS_PATH / f"complete_call_{call_id}.txt"
            media_type = "text/plain"
            filename = f"transcript_{call_id}.txt"
        
        if not transcript_file.exists():
            raise HTTPException(
                status_code=404,
                detail="Transcription non trouvée"
            )
        
        headers = {
            "Content-Disposition": f"attachment; filename={filename}",
            "Content-Type": media_type
        }
        
        return FileResponse(transcript_file, headers=headers, media_type=media_type)
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Transcript download error: {e}")
        raise HTTPException(status_code=500, detail="Erreur interne")


@downloads_router.get("/call-info/{call_id}")
async def get_call_download_info(
    call_id: str,
    token: str = Query(..., description="Token de sécurité")
):
    """
    Obtient les informations de téléchargement d'un appel
    (sans télécharger les fichiers)
    """
    try:
        # Validation token
        token_info = download_manager.validate_token(call_id, token, "info_request")
        if not token_info:
            raise HTTPException(status_code=403, detail="Token invalide")
        
        # Infos fichier audio
        audio_file = token_info.get("file_path", "")
        audio_info = download_manager.get_file_info(audio_file)
        
        # Infos transcriptions
        transcript_json = TRANSCRIPTS_PATH / f"complete_call_{call_id}.json"
        transcript_txt = TRANSCRIPTS_PATH / f"complete_call_{call_id}.txt"
        
        return {
            "call_id": call_id,
            "token_expires": token_info.get("expires"),
            "audio_recording": {
                "available": audio_info.get("exists", False),
                "size_mb": audio_info.get("size_mb", 0),
                "path": audio_file
            },
            "transcriptions": {
                "json_available": transcript_json.exists(),
                "txt_available": transcript_txt.exists()
            },
            "download_links": {
                "audio": f"/api/downloads/call-audio/{call_id}?token={token}",
                "transcript_json": f"/api/downloads/call-transcript/{call_id}?format=json&token={token}",
                "transcript_txt": f"/api/downloads/call-transcript/{call_id}?format=txt&token={token}"
            }
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Call info error: {e}")
        raise HTTPException(status_code=500, detail="Erreur interne")


@downloads_router.post("/cleanup-tokens")
async def cleanup_expired_tokens():
    """
    Endpoint de maintenance pour nettoyer les tokens expirés
    (À appeler périodiquement par cron ou tâche système)
    """
    try:
        download_manager.cleanup_expired_tokens()
        return {"success": True, "message": "Tokens expirés nettoyés"}
    except Exception as e:
        logger.error(f"❌ Cleanup error: {e}")
        raise HTTPException(status_code=500, detail="Erreur nettoyage")


@downloads_router.get("/status")
async def get_download_service_status():
    """Status du service de téléchargement"""
    try:
        tokens_count = 0
        if TOKENS_FILE.exists():
            with open(TOKENS_FILE, 'r') as f:
                tokens_data = json.load(f)
                tokens_count = len(tokens_data)
        
        return {
            "service": "downloads",
            "status": "active",
            "recordings_path": RECORDINGS_PATH,
            "transcripts_path": str(TRANSCRIPTS_PATH),
            "active_tokens": tokens_count,
            "tokens_file": str(TOKENS_FILE),
            "endpoints": [
                "/api/downloads/call-audio/{call_id}",
                "/api/downloads/call-transcript/{call_id}", 
                "/api/downloads/call-info/{call_id}"
            ]
        }
        
    except Exception as e:
        return {"error": str(e), "status": "error"}