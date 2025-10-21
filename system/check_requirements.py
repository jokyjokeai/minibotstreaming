#!/usr/bin/env python3
"""
Vérificateur de prérequis pour MiniBotPanel v2 avec TTS Voice Cloning
Vérifie que toutes les dépendances sont correctement installées
"""

import subprocess
import sys
import importlib
from pathlib import Path

def check_system_commands():
    """Vérifie les commandes système nécessaires"""
    print("🔧 Checking system commands...")
    
    commands = {
        "ffmpeg": "Audio processing",
        "sox": "Audio utilities", 
        "espeak": "TTS fallback",
        "python3": "Python interpreter",
        "pip3": "Python package manager",
        "git": "Version control",
        "curl": "HTTP client"
    }
    
    missing = []
    for cmd, desc in commands.items():
        try:
            result = subprocess.run([cmd, "--version"], capture_output=True, text=True)
            if result.returncode == 0:
                print(f"  ✅ {cmd} - {desc}")
            else:
                print(f"  ❌ {cmd} - {desc} (not found)")
                missing.append(cmd)
        except FileNotFoundError:
            print(f"  ❌ {cmd} - {desc} (not found)")
            missing.append(cmd)
    
    return missing

def check_python_packages():
    """Vérifie les packages Python nécessaires"""
    print("\n🐍 Checking Python packages...")
    
    packages = {
        "fastapi": "Web API framework",
        "uvicorn": "ASGI server",
        "vosk": "ASR engine",
        "ollama": "Local NLP",
        "sqlalchemy": "Database ORM",
        "psycopg2": "PostgreSQL driver",
        "numpy": "Numerical computing",
        "scipy": "Scientific computing",
        "librosa": "Audio analysis",
        "TTS": "Text-to-Speech with voice cloning",
        "torch": "PyTorch for ML/TTS",
        "transformers": "Transformer models",
        "websockets": "WebSocket support",
        "requests": "HTTP client"
    }
    
    missing = []
    for package, desc in packages.items():
        try:
            importlib.import_module(package)
            print(f"  ✅ {package} - {desc}")
        except ImportError:
            print(f"  ❌ {package} - {desc} (not installed)")
            missing.append(package)
    
    return missing

def check_tts_functionality():
    """Vérifie que TTS fonctionne correctement"""
    print("\n🎙️ Checking TTS functionality...")
    
    try:
        from TTS.api import TTS
        print("  ✅ TTS library imported successfully")
        
        # Test de liste des modèles
        try:
            models = TTS().list_models()
            if "tts_models/multilingual/multi-dataset/xtts_v2" in str(models):
                print("  ✅ XTTS v2 model available")
            else:
                print("  ⚠️ XTTS v2 model not found in available models")
        except Exception as e:
            print(f"  ⚠️ Could not list TTS models: {e}")
        
        return True
        
    except ImportError as e:
        print(f"  ❌ TTS not available: {e}")
        return False

def check_torch_device():
    """Vérifie la disponibilité GPU/CPU pour PyTorch"""
    print("\n🚀 Checking PyTorch device availability...")
    
    try:
        import torch
        print(f"  ✅ PyTorch version: {torch.__version__}")
        
        if torch.cuda.is_available():
            gpu_count = torch.cuda.device_count()
            current_device = torch.cuda.current_device()
            device_name = torch.cuda.get_device_name(current_device)
            print(f"  🚀 CUDA available - {gpu_count} GPU(s)")
            print(f"  🎯 Current device: {device_name}")
        else:
            print("  💻 CUDA not available, will use CPU")
            print("  💡 For better TTS performance, consider GPU setup")
        
        return True
        
    except ImportError:
        print("  ❌ PyTorch not available")
        return False

def check_project_structure():
    """Vérifie la structure du projet"""
    print("\n📂 Checking project structure...")
    
    current_dir = Path.cwd()
    required_paths = {
        "services/": "Services directory",
        "services/nlp_intent.py": "NLP intent service",
        "services/tts_voice_clone.py": "TTS voice cloning service",
        "audio/": "Audio files directory",
        "audio_texts.json": "Audio metadata",
        "prompts_config.json": "Dynamic prompts configuration",
        "requirements.txt": "Python dependencies",
        "start_system.sh": "System startup script",
        "system/install_hybrid.py": "Installation script"
    }
    
    missing = []
    for path, desc in required_paths.items():
        full_path = current_dir / path
        if full_path.exists():
            print(f"  ✅ {path} - {desc}")
        else:
            print(f"  ❌ {path} - {desc} (missing)")
            missing.append(path)
    
    return missing

def main():
    """Fonction principale de vérification"""
    print("🔍 MiniBotPanel v2 TTS Voice Cloning - Requirements Check")
    print("=" * 60)
    
    all_good = True
    
    # Vérifications
    missing_commands = check_system_commands()
    missing_packages = check_python_packages()
    tts_ok = check_tts_functionality()
    torch_ok = check_torch_device()
    missing_files = check_project_structure()
    
    # Résumé
    print("\n" + "=" * 60)
    print("📋 SUMMARY")
    print("=" * 60)
    
    if missing_commands:
        print(f"❌ Missing system commands: {', '.join(missing_commands)}")
        print("   Run: sudo apt-get install " + " ".join(missing_commands))
        all_good = False
    
    if missing_packages:
        print(f"❌ Missing Python packages: {', '.join(missing_packages)}")
        print("   Run: pip3 install " + " ".join(missing_packages))
        all_good = False
    
    if not tts_ok:
        print("❌ TTS system not functional")
        print("   Run: pip3 install TTS torch transformers")
        all_good = False
    
    if not torch_ok:
        print("❌ PyTorch not available")
        print("   Run: pip3 install torch torchaudio")
        all_good = False
    
    if missing_files:
        print(f"❌ Missing project files: {', '.join(missing_files)}")
        all_good = False
    
    if all_good:
        print("🎉 ALL REQUIREMENTS MET!")
        print("✅ System ready for MiniBotPanel v2 with TTS Voice Cloning")
        print("\n🚀 Next steps:")
        print("1. Run: ./start_system.sh")
        print("2. Test TTS: python3 services/tts_voice_clone.py")
        print("3. Launch campaign: python3 system/launch_campaign.py")
    else:
        print("⚠️ Some requirements are missing. Please install them before proceeding.")
        return 1
    
    return 0

if __name__ == "__main__":
    sys.exit(main())