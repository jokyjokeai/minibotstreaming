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

            # Conversion 16kHz pour optimisation streaming
            # Compatible AudioFork + Vosk + qualité supérieure
            if [ -z "$GAIN_PARAM" ]; then
                # Pas d'amplification, juste conversion 16kHz
                sox "$wav" -r 16000 -c 1 "$target" 2>/dev/null
            else
                # Amplification + conversion 16kHz
                sox "$wav" -r 16000 -c 1 "$target" $GAIN_PARAM 2>/dev/null
            fi

            if [ $? -eq 0 ]; then
                if [ -n "$GAIN_PARAM" ]; then
                    echo "   ✅ $filename converti (16000 Hz + $GAIN_LABEL)"
                else
                    echo "   ✅ $filename converti (16000 Hz)"
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

# 5. Génération basique audio_texts.json (sans transcription)
echo ""
echo "📝 Génération de audio_texts.json..."
python3 << EOF
import json
import subprocess
import os
from pathlib import Path

# Récupérer PROJECT_ROOT depuis la variable d'environnement passée par bash
project_root = "$PROJECT_ROOT"

# Configuration
audio_dir = os.path.join(project_root, "audio")
output_file = os.path.join(project_root, "audio_texts.json")

audio_texts = {}

for wav_file in sorted(Path(audio_dir).glob("*.wav")):
    filename = wav_file.stem  # Sans extension (.wav)

    print(f"   📝 Traitement de {filename}.wav...")

    # Durée du fichier avec soxi
    try:
        duration_result = subprocess.run(
            ["soxi", "-D", str(wav_file)],
            capture_output=True,
            text=True
        )
        duration = float(duration_result.stdout.strip()) if duration_result.returncode == 0 else 0.0
    except:
        duration = 0.0

    audio_texts[filename] = {
        "file": f"{filename}.wav",
        "duration": round(duration, 1),
        "text": f"[Audio {filename} - Transcription via streaming en temps réel]"
    }

    print(f"      ✅ Durée: {duration:.1f}s")

# Sauvegarder dans audio_texts.json
with open(output_file, 'w', encoding='utf-8') as f:
    json.dump(audio_texts, f, indent=2, ensure_ascii=False)

print(f"\n   ✅ audio_texts.json créé avec {len(audio_texts)} fichiers")
print("   💡 Transcriptions seront générées en temps réel via Vosk durant les appels")

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
echo "   • Format optimisé : 16kHz mono WAV (streaming)"
echo "   • Utilisables avec : sound:minibot/[nom_fichier]"
echo "   • Réglage volume appliqué : $GAIN_LABEL"
echo "   • audio_texts.json généré (transcriptions temps réel via Vosk)"
echo ""
echo "🔄 Pour modifier le volume :"
echo "   • Méthode rapide : sudo ./setup_audio.sh -f"
echo "   • Ou manuellement : rm -rf $ASTERISK_SOUNDS/*.wav puis relancer"
echo ""
echo "💡 Ce script est INTELLIGENT : il ne recopie que les fichiers modifiés"
echo ""