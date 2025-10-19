#!/bin/bash

# Script de configuration audio - À exécuter UNE FOIS ou après modification des fichiers
# Usage: sudo ./setup_audio.sh [-f|--force]
# Option -f : Force le retraitement de tous les fichiers (utile pour changer l'amplification)

FORCE_REPROCESS=false

# Analyser les arguments
if [ "$1" = "-f" ] || [ "$1" = "--force" ]; then
    FORCE_REPROCESS=true
fi

echo "========================================="
echo "  CONFIGURATION AUDIO POUR ASTERISK"
echo "========================================="

# Détecter automatiquement le répertoire du script
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"

AUDIO_SOURCE="$PROJECT_ROOT/audio"
ASTERISK_SOUNDS="/var/lib/asterisk/sounds/minibot"

# Si force, supprimer les fichiers traités
if [ "$FORCE_REPROCESS" = true ]; then
    echo ""
    echo "🔄 Mode FORCE : Suppression des fichiers existants..."
    rm -f "$ASTERISK_SOUNDS"/*.wav 2>/dev/null
    echo "   ✅ Fichiers supprimés, retraitement forcé"
fi

# Menu d'amplification
echo ""
echo "🔊 RÉGLAGE VOLUME AUDIO"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""
echo "Choisissez le niveau de volume :"
echo ""
echo "  📉 RÉDUCTION (si audio trop fort) :"
echo "     -3) -10 dB (réduction forte)"
echo "     -2) -6 dB  (réduction notable)"
echo "     -1) -3 dB  (réduction légère)"
echo ""
echo "  ⚖️  AUCUN CHANGEMENT :"
echo "      0) Volume original (pas de modification)"
echo ""
echo "  📈 AUGMENTATION (si audio trop faible) :"
echo "      1) +3 dB  (👍 Recommandé - augmentation légère et sûre)"
echo "      2) +6 dB  (augmentation notable)"
echo "      3) +8 dB  (augmentation forte)"
echo "      4) +10 dB (augmentation très forte, risque de saturation)"
echo ""
echo "  🎚️  AUTO :"
echo "      5) Normalisation automatique (volume max sans saturation)"
echo ""
echo -n "Votre choix [-3 à 5] (défaut: 1): "
read GAIN_CHOICE

# Valeur par défaut
GAIN_CHOICE=${GAIN_CHOICE:-1}

# Définir le paramètre sox selon le choix
case $GAIN_CHOICE in
    -3)
        GAIN_PARAM="vol -10dB"
        GAIN_LABEL="-10 dB (réduction forte)"
        ;;
    -2)
        GAIN_PARAM="vol -6dB"
        GAIN_LABEL="-6 dB (réduction notable)"
        ;;
    -1)
        GAIN_PARAM="vol -3dB"
        GAIN_LABEL="-3 dB (réduction légère)"
        ;;
    0)
        GAIN_PARAM=""
        GAIN_LABEL="Aucune modification"
        ;;
    1)
        GAIN_PARAM="vol 3dB"
        GAIN_LABEL="+3 dB (recommandé)"
        ;;
    2)
        GAIN_PARAM="vol 6dB"
        GAIN_LABEL="+6 dB"
        ;;
    3)
        GAIN_PARAM="vol 8dB"
        GAIN_LABEL="+8 dB"
        ;;
    4)
        GAIN_PARAM="vol 10dB"
        GAIN_LABEL="+10 dB"
        ;;
    5)
        GAIN_PARAM="norm"
        GAIN_LABEL="Normalisation auto"
        ;;
    *)
        echo "⚠️  Choix invalide, utilisation de +3 dB par défaut"
        GAIN_PARAM="vol 3dB"
        GAIN_LABEL="+3 dB (recommandé)"
        ;;
esac

echo ""
echo "✅ Réglage volume sélectionné: $GAIN_LABEL"
echo ""

# 1. Créer le répertoire minibot s'il n'existe pas
echo "📁 Création du répertoire $ASTERISK_SOUNDS..."
mkdir -p "$ASTERISK_SOUNDS"

# 2. Conversion et copie intelligente
echo "🔄 Traitement des fichiers audio..."
for wav in "$AUDIO_SOURCE"/*.wav; do
    if [ -f "$wav" ]; then
        filename=$(basename "$wav")
        target="$ASTERISK_SOUNDS/$filename"

        # Vérifier si le fichier source est plus récent
        if [ ! -f "$target" ] || [ "$wav" -nt "$target" ]; then
            echo "   📝 Traitement de $filename..."

            # Toujours utiliser sox pour permettre l'amplification
            # Même si déjà en 8000 Hz, on peut appliquer le gain
            if [ -z "$GAIN_PARAM" ]; then
                # Pas d'amplification, juste conversion
                sox "$wav" -r 8000 -c 1 "$target" 2>/dev/null
            else
                # Amplification + conversion
                sox "$wav" -r 8000 -c 1 "$target" $GAIN_PARAM 2>/dev/null
            fi

            if [ $? -eq 0 ]; then
                if [ -n "$GAIN_PARAM" ]; then
                    echo "   ✅ $filename converti (8000 Hz + $GAIN_LABEL)"
                else
                    echo "   ✅ $filename converti (8000 Hz)"
                fi
            else
                echo "   ⚠️  Erreur de conversion pour $filename"
            fi
        else
            echo "   ⏭️  $filename déjà à jour"
        fi
    fi
done

# 3. Permissions
echo "🔐 Configuration des permissions..."
chown -R asterisk:asterisk "$ASTERISK_SOUNDS"
chmod -R 644 "$ASTERISK_SOUNDS"/*.wav
chmod 755 "$ASTERISK_SOUNDS"

# 4. Vérification
echo ""
echo "📊 Fichiers installés :"
ls -lh "$ASTERISK_SOUNDS"/*.wav 2>/dev/null | awk '{print "   " $9 " (" $5 ")"}'

# 5. Transcription automatique avec Whisper et mise à jour audio_texts.json
echo ""
echo "🎤 Transcription automatique des fichiers audio avec Whisper..."
python3 << 'EOF'
import json
import subprocess
import os
import sys
from pathlib import Path

# Détecter le répertoire du projet (2 niveaux au-dessus de ce script)
# Ce script Python est intégré dans system/setup_audio.sh
project_root = os.path.dirname(os.path.dirname(os.path.abspath(sys.argv[0])))

# Configuration
audio_dir = os.path.join(project_root, "audio")
output_file = os.path.join(project_root, "audio_texts.json")

# Importer le service Whisper
sys.path.insert(0, project_root)

def remove_hallucination_repetitions(text):
    """Détecte et supprime les répétitions hallucinées par Whisper"""
    if not text:
        return text

    # Séparer en phrases (par points, virgules, etc.)
    sentences = [s.strip() for s in text.replace('?', '.').replace('!', '.').split('.') if s.strip()]

    if len(sentences) <= 1:
        return text

    # Détecter si la même phrase est répétée plusieurs fois
    if len(set(sentences)) == 1 and len(sentences) >= 3:
        # Toutes les phrases sont identiques et répétées 3+ fois = hallucination
        print(f"      ⚠️  Hallucination détectée: phrase répétée {len(sentences)} fois")
        return sentences[0] + '.'

    # Détecter si la première phrase est répétée consécutivement
    if len(sentences) >= 2:
        first_sentence = sentences[0]
        repetition_count = 1
        for sentence in sentences[1:]:
            if sentence == first_sentence:
                repetition_count += 1
            else:
                break

        if repetition_count >= 3:
            # La phrase est répétée 3+ fois consécutivement = hallucination
            print(f"      ⚠️  Hallucination détectée: début répété {repetition_count} fois")
            # Garder seulement la première occurrence + le reste
            return first_sentence + '. ' + '. '.join(sentences[repetition_count:])

    return text

try:
    from services.whisper_service import whisper_service

    audio_texts = {}

    for wav_file in sorted(Path(audio_dir).glob("*.wav")):
        filename = wav_file.stem  # Sans extension (.wav)

        print(f"   🎤 Transcription de {filename}.wav...")

        # Transcription avec Whisper (français)
        result = whisper_service.transcribe(str(wav_file), language="fr")
        text = result.get("text", "").strip()

        # Nettoyer les hallucinations de répétition (post-traitement)
        text = remove_hallucination_repetitions(text)

        # Durée du fichier avec soxi
        duration_result = subprocess.run(
            ["soxi", "-D", str(wav_file)],
            capture_output=True,
            text=True
        )
        duration = float(duration_result.stdout.strip()) if duration_result.returncode == 0 else 0.0

        audio_texts[filename] = {
            "file": f"{filename}.wav",
            "duration": round(duration, 1),
            "text": text
        }

        print(f"      ✅ Texte: {text[:60]}{'...' if len(text) > 60 else ''}")

    # Sauvegarder dans audio_texts.json
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(audio_texts, f, indent=2, ensure_ascii=False)

    print(f"\n   ✅ audio_texts.json mis à jour avec {len(audio_texts)} fichiers")

except ImportError:
    print("   ⚠️  Whisper non disponible, transcription ignorée")
    print("   💡 Exécutez ce script après avoir démarré le système une première fois")
except Exception as e:
    print(f"   ⚠️  Erreur lors de la transcription: {e}")
    print("   💡 Continuez, vous pourrez transcrire manuellement")

EOF

# 6. Correction des permissions (évite les problèmes si lancé en sudo)
echo ""
echo "🔐 Correction des permissions..."

# Récupérer l'utilisateur réel (même si lancé en sudo)
if [ -n "$SUDO_USER" ]; then
    REAL_USER="$SUDO_USER"
else
    REAL_USER="$USER"
fi

# Corriger les permissions des logs créés par le script Python
chown -R "$REAL_USER:$REAL_USER" "$PROJECT_ROOT/logs/" 2>/dev/null || true
echo "   ✅ Permissions corrigées pour $REAL_USER"

echo ""
echo "✅ Configuration terminée !"
echo ""
echo "ℹ️  Notes importantes :"
echo "   • Les fichiers sont dans : $ASTERISK_SOUNDS"
echo "   • Utilisables avec : sound:minibot/[nom_fichier]"
echo "   • Réglage volume appliqué : $GAIN_LABEL"
echo "   • audio_texts.json automatiquement généré avec transcriptions Whisper"
echo ""
echo "🔄 Pour modifier le volume :"
echo "   • Méthode rapide : sudo ./setup_audio.sh -f"
echo "   • Ou manuellement : rm -rf $ASTERISK_SOUNDS/*.wav puis relancer"
echo ""
echo "💡 Ce script est INTELLIGENT : il ne recopie que les fichiers modifiés"
echo ""