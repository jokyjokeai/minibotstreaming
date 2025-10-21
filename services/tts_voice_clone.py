#!/usr/bin/env python3
"""
TTS Voice Cloning Service - MiniBotPanel v2
Service de synthèse vocale avec clonage de voix à partir des fichiers audio existants
Utilise Coqui TTS (gratuit, open source)
"""

import os
import json
import time
from pathlib import Path
from typing import Optional, Dict, Any
import tempfile
import shutil

from logger_config import get_logger

logger = get_logger(__name__)

# Import TTS avec fallback
try:
    from TTS.api import TTS
    import torch
    TTS_AVAILABLE = True
    logger.info("✅ Coqui TTS imported successfully")
except ImportError as e:
    TTS_AVAILABLE = False
    logger.warning(f"⚠️ Coqui TTS not available: {e}")

class VoiceCloneService:
    """
    Service de clonage vocal pour réponses dynamiques
    Clone la voix de Thierry à partir des fichiers audio existants
    """
    
    def __init__(self):
        self.logger = get_logger(f"{__name__}.VoiceCloneService")
        self.is_available = TTS_AVAILABLE
        self.tts_model = None
        self.reference_voice_path = None
        self.voice_characteristics = {}
        
        # Configuration TTS
        self.config = {
            "model_name": "tts_models/multilingual/multi-dataset/xtts_v2",  # Support français
            "device": "cpu",  # CPU par défaut (GPU auto-détecté si disponible)
            "language": "fr",
            "sample_rate": 16000,  # Compatible avec Asterisk
            "output_format": "wav"
        }
        
        # Statistiques
        self.stats = {
            "total_generations": 0,
            "avg_generation_time": 0.0,
            "voice_cloned": False,
            "reference_audio_duration": 0.0
        }
        
        if self.is_available:
            self._initialize_tts()
    
    def _initialize_tts(self) -> bool:
        """Initialise le modèle TTS et analyse les fichiers de référence"""
        try:
            self.logger.info("🎙️ Initializing Coqui TTS for voice cloning...")
            
            # Détecter GPU si disponible
            if torch.cuda.is_available():
                self.config["device"] = "cuda"
                self.logger.info("🚀 GPU detected, using CUDA acceleration")
            
            # Charger le modèle XTTS v2 (multilingue avec clonage)
            self.tts_model = TTS(self.config["model_name"]).to(self.config["device"])
            
            # Analyser les fichiers audio existants pour la référence vocale
            self._prepare_reference_voice()
            
            self.logger.info("✅ TTS voice cloning initialized successfully")
            return True
            
        except Exception as e:
            self.logger.error(f"❌ Failed to initialize TTS: {e}")
            self.is_available = False
            return False
    
    def _prepare_reference_voice(self):
        """Prépare la voix de référence avec embeddings pour performance optimale"""
        try:
            # Chemins
            audio_dir = Path(__file__).parent.parent / "audio"
            voices_dir = Path(__file__).parent.parent / "voices"
            voices_dir.mkdir(exist_ok=True)
            
            # Fichier d'embedding sauvegardé
            self.embedding_path = voices_dir / "thierry_voice_embedding.json"
            
            # Collecter tous les fichiers audio valides pour l'embedding
            reference_files = []
            total_duration = 0
            
            # Lire audio_texts.json pour les métadonnées
            audio_texts_path = audio_dir.parent / "audio_texts.json"
            if audio_texts_path.exists():
                with open(audio_texts_path, 'r', encoding='utf-8') as f:
                    audio_data = json.load(f)
                
                for key, info in audio_data.items():
                    duration = info.get("duration", 0)
                    audio_file = audio_dir / info.get("file", f"{key}.wav")
                    
                    # Prendre tous les fichiers > 3 secondes pour un meilleur embedding
                    if audio_file.exists() and duration > 3.0:
                        reference_files.append({
                            "path": str(audio_file),
                            "duration": duration,
                            "text": info.get("text", ""),
                            "key": key
                        })
                        total_duration += duration
            
            if reference_files:
                # Trier par durée décroissante et prendre les 5 meilleurs
                reference_files.sort(key=lambda x: x["duration"], reverse=True)
                best_references = reference_files[:5]
                
                # Utiliser le plus long comme référence principale
                self.reference_voice_path = best_references[0]["path"]
                
                self.voice_characteristics = {
                    "total_references": len(best_references),
                    "total_duration": sum(ref["duration"] for ref in best_references),
                    "best_reference": best_references[0]["key"],
                    "references": best_references
                }
                
                # Générer ou charger l'embedding
                self._generate_voice_embedding(best_references)
                
                self.stats["reference_audio_duration"] = total_duration
                self.stats["voice_cloned"] = True
                
                self.logger.info(f"🎯 Voice references prepared: {len(best_references)} files ({total_duration:.1f}s total)")
            else:
                self.logger.warning("⚠️ No suitable reference audio found for voice cloning")
                
        except Exception as e:
            self.logger.error(f"❌ Failed to prepare reference voice: {e}")

    def _generate_voice_embedding(self, reference_files):
        """Génère ou charge l'embedding vocal pour performance optimale"""
        try:
            # Vérifier si l'embedding existe déjà
            if self.embedding_path.exists():
                self.logger.info("🔄 Loading existing voice embedding...")
                self.use_embedding = True
                return
            
            self.logger.info("🧠 Generating voice embedding from reference files...")
            
            # Créer fichier temporaire avec les meilleurs échantillons
            temp_dir = Path(tempfile.gettempdir()) / "minibotpanel_voice_training"
            temp_dir.mkdir(exist_ok=True)
            
            # Copier les fichiers de référence
            training_files = []
            for i, ref in enumerate(reference_files):
                dest_file = temp_dir / f"thierry_sample_{i+1}.wav"
                shutil.copy2(ref["path"], dest_file)
                training_files.append(str(dest_file))
            
            # Générer l'embedding avec le modèle XTTS v2
            # Note: cette approche nécessite la commande compute_embeddings
            try:
                import subprocess
                cmd = [
                    "python3", "-m", "TTS.bin.compute_embeddings",
                    "--model_name", "tts_models/multilingual/multi-dataset/xtts_v2",
                    "--out_path", str(self.embedding_path),
                    "--speaker_wav", training_files[0]  # Utiliser le meilleur échantillon
                ]
                
                result = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
                
                if result.returncode == 0 and self.embedding_path.exists():
                    self.use_embedding = True
                    self.logger.info("✅ Voice embedding generated successfully")
                else:
                    self.logger.warning("⚠️ Embedding generation failed, using direct WAV reference")
                    self.use_embedding = False
                    
            except Exception as e:
                self.logger.warning(f"⚠️ Embedding generation error: {e}, using direct WAV reference")
                self.use_embedding = False
            
            # Nettoyer les fichiers temporaires
            if temp_dir.exists():
                shutil.rmtree(temp_dir)
                
        except Exception as e:
            self.logger.error(f"❌ Voice embedding preparation failed: {e}")
            self.use_embedding = False
    
    def generate_speech(self, text: str, output_path: Optional[str] = None, speed: float = 1.0) -> Optional[str]:
        """
        Génère un fichier audio avec la voix clonée
        
        Args:
            text: Texte à synthétiser
            output_path: Chemin de sortie (si None, fichier temporaire)
            speed: Vitesse de parole (1.0 = normal)
            
        Returns:
            Chemin vers le fichier audio généré ou None si erreur
        """
        if not self.is_available or not self.tts_model:
            self.logger.error("❌ TTS not available")
            return None
        
        if not hasattr(self, 'use_embedding') and not self.reference_voice_path:
            self.logger.error("❌ No voice reference available")
            return None
        
        start_time = time.time()
        self.stats["total_generations"] += 1
        
        try:
            # Préparer le fichier de sortie
            if output_path is None:
                temp_file = tempfile.NamedTemporaryFile(delete=False, suffix=".wav")
                output_path = temp_file.name
                temp_file.close()
            
            # Nettoyer le texte
            text_clean = self._clean_text_for_tts(text)
            
            self.logger.debug(f"🎙️ Generating speech: '{text_clean[:50]}...'")
            
            # Générer avec clonage vocal (embedding ou WAV direct)
            if hasattr(self, 'use_embedding') and self.use_embedding and self.embedding_path.exists():
                # Utiliser l'embedding précomputé (plus rapide)
                self.logger.debug("🧠 Using voice embedding for generation")
                self.tts_model.tts_to_file(
                    text=text_clean,
                    speaker_embeddings=str(self.embedding_path),
                    language=self.config["language"],
                    file_path=output_path,
                    speed=speed
                )
            else:
                # Fallback sur WAV direct
                self.logger.debug("🎵 Using direct WAV reference for generation")
                self.tts_model.tts_to_file(
                    text=text_clean,
                    speaker_wav=self.reference_voice_path,
                    language=self.config["language"],
                    file_path=output_path,
                    speed=speed
                )
            
            # Vérifier que le fichier a été créé
            if not os.path.exists(output_path):
                raise Exception("Generated audio file not found")
            
            generation_time = time.time() - start_time
            self._update_generation_stats(generation_time)
            
            self.logger.info(f"✅ Speech generated: {os.path.basename(output_path)} [{generation_time:.1f}s]")
            return output_path
            
        except Exception as e:
            self.logger.error(f"❌ Speech generation failed: {e}")
            return None
    
    def _clean_text_for_tts(self, text: str) -> str:
        """Nettoie le texte pour optimiser la synthèse vocale"""
        # Remplacer les abréviations courantes
        replacements = {
            "M.": "Monsieur",
            "Mme": "Madame", 
            "Dr": "Docteur",
            "€": "euros",
            "%": "pourcent",
            "&": "et",
            "@": "arobase"
        }
        
        text_clean = text
        for old, new in replacements.items():
            text_clean = text_clean.replace(old, new)
        
        # Supprimer les caractères problématiques
        text_clean = ''.join(c for c in text_clean if c.isprintable())
        
        return text_clean.strip()
    
    def _update_generation_stats(self, generation_time: float):
        """Met à jour les statistiques de génération"""
        current_avg = self.stats["avg_generation_time"]
        count = self.stats["total_generations"]
        
        # Moyenne mobile
        self.stats["avg_generation_time"] = (current_avg * (count - 1) + generation_time) / count
    
    def generate_contextual_response(self, response_text: str, context: str = "default") -> Optional[str]:
        """
        Génère une réponse contextuelle avec la voix clonée
        Optimisé pour les réponses aux questions hors-script
        
        Args:
            response_text: Texte de la réponse à générer
            context: Contexte pour adapter le ton (objection, clarification, etc.)
            
        Returns:
            Chemin vers le fichier audio généré
        """
        # Adapter la vitesse selon le contexte
        speed_mapping = {
            "objection": 0.9,      # Plus lent pour rassurer
            "clarification": 1.0,   # Normal
            "enthusiasm": 1.1,      # Plus rapide pour montrer l'enthousiasme
            "default": 1.0
        }
        
        speed = speed_mapping.get(context, 1.0)
        
        # Générer dans le dossier audio temporaire
        audio_dir = Path(__file__).parent.parent / "audio"
        temp_filename = f"contextual_response_{int(time.time())}.wav"
        output_path = audio_dir / temp_filename
        
        result = self.generate_speech(response_text, str(output_path), speed)
        
        if result:
            self.logger.info(f"🔄 Contextual response generated: {temp_filename}")
        
        return result
    
    def get_stats(self) -> Dict[str, Any]:
        """Retourne les statistiques du service"""
        stats = {
            "available": self.is_available,
            "voice_cloned": self.stats["voice_cloned"],
            "reference_duration": self.stats["reference_audio_duration"],
            "total_generations": self.stats["total_generations"],
            "avg_generation_time": self.stats["avg_generation_time"],
            "model_device": self.config["device"] if self.is_available else None
        }
        
        # Ajouter les informations d'embedding si disponibles
        if hasattr(self, 'use_embedding'):
            stats["embedding_available"] = self.use_embedding
            stats["embedding_path"] = str(self.embedding_path) if hasattr(self, 'embedding_path') else None
        
        if hasattr(self, 'voice_characteristics'):
            stats["voice_characteristics"] = self.voice_characteristics
        
        return stats

# Instance globale
voice_clone_service = VoiceCloneService()

def generate_dynamic_audio(text: str, context: str = "default") -> Optional[str]:
    """
    Fonction utilitaire pour générer rapidement un audio avec voix clonée
    
    Args:
        text: Texte à synthétiser
        context: Contexte pour adapter le ton
        
    Returns:
        Chemin vers le fichier audio ou None
    """
    return voice_clone_service.generate_contextual_response(text, context)

if __name__ == "__main__":
    # Test du service
    service = VoiceCloneService()
    
    if service.is_available:
        print("🎙️ Testing voice cloning service...")
        
        test_text = "C'est une excellente question. Notre solution génère effectivement un très bon retour sur investissement."
        result = service.generate_speech(test_text)
        
        if result:
            print(f"✅ Test successful: {result}")
            print(f"📊 Stats: {service.get_stats()}")
        else:
            print("❌ Test failed")
    else:
        print("❌ TTS service not available")