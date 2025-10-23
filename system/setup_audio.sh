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
TTS_GENERATED_SOURCE="$PROJECT_ROOT/tts_generated"
SCENARIOS_SOURCE="$PROJECT_ROOT/scenarios"
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

# 2. Conversion et copie intelligente MULTI-SOURCES
echo "🔄 Traitement des fichiers audio MULTI-SOURCES..."

# Fonction de traitement unifiée
process_audio_file() {
    local source_file="$1"
    local source_type="$2"
    
    if [ -f "$source_file" ]; then
        local filename=$(basename "$source_file")
        local target="$ASTERISK_SOUNDS/$filename"

        # Vérifier si le fichier source est plus récent
        if [ ! -f "$target" ] || [ "$source_file" -nt "$target" ]; then
            echo "   📝 Traitement de $filename ($source_type)..."

            # Conversion 16kHz pour optimisation streaming + AudioFork + Vosk
            if [ -z "$GAIN_PARAM" ]; then
                # Pas d'amplification, juste conversion 16kHz mono
                sox "$source_file" -r 16000 -c 1 "$target" 2>/dev/null
            else
                # Amplification + conversion 16kHz mono
                sox "$source_file" -r 16000 -c 1 "$target" $GAIN_PARAM 2>/dev/null
            fi

            if [ $? -eq 0 ]; then
                if [ -n "$GAIN_PARAM" ]; then
                    echo "   ✅ $filename converti (16000 Hz mono + $GAIN_LABEL) [$source_type]"
                else
                    echo "   ✅ $filename converti (16000 Hz mono) [$source_type]"
                fi
            else
                echo "   ⚠️  Erreur de conversion pour $filename [$source_type]"
            fi
        else
            echo "   ⏭️  $filename déjà à jour [$source_type]"
        fi
    fi
}

# 2a. Traitement fichiers audio de base (répertoire audio/)
echo "📁 Source: Fichiers audio de base..."
if [ -d "$AUDIO_SOURCE" ]; then
    file_count=0
    for wav in "$AUDIO_SOURCE"/*.wav; do
        if [ -f "$wav" ]; then
            process_audio_file "$wav" "BASE"
            file_count=$((file_count + 1))
        fi
    done
    echo "   💫 $file_count fichier(s) audio de base traité(s)"
else
    echo "   ⚠️  Répertoire audio/ non trouvé: $AUDIO_SOURCE"
fi

# 2b. Traitement fichiers TTS générés (répertoire tts_generated/)
echo "📁 Source: Fichiers TTS générés..."
if [ -d "$TTS_GENERATED_SOURCE" ]; then
    file_count=0
    for wav in "$TTS_GENERATED_SOURCE"/*.wav; do
        if [ -f "$wav" ]; then
            process_audio_file "$wav" "TTS_GEN"
            file_count=$((file_count + 1))
        fi
    done
    echo "   🎙️  $file_count fichier(s) TTS générés traité(s)"
else
    echo "   ℹ️  Répertoire tts_generated/ non trouvé (sera créé si nécessaire)"
    mkdir -p "$TTS_GENERATED_SOURCE"
fi

# 2c. Traitement fichiers TTS de scénarios (scenarios/*/audio/*.wav)
echo "📁 Source: Fichiers TTS de scénarios..."
if [ -d "$SCENARIOS_SOURCE" ]; then
    file_count=0
    # Rechercher tous les fichiers .wav dans les sous-dossiers de scénarios
    find "$SCENARIOS_SOURCE" -name "*.wav" -type f | while read scenario_wav; do
        if [ -f "$scenario_wav" ]; then
            # Extraire nom du scénario pour préfixer
            scenario_name=$(echo "$scenario_wav" | sed "s|$SCENARIOS_SOURCE/||" | cut -d'/' -f1)
            original_filename=$(basename "$scenario_wav")
            
            # Créer nom unique avec préfixe scénario
            prefixed_filename="${scenario_name}_${original_filename}"
            
            # Créer fichier temporaire avec le bon nom
            temp_file="/tmp/$prefixed_filename"
            cp "$scenario_wav" "$temp_file"
            
            process_audio_file "$temp_file" "SCENARIO_$scenario_name"
            
            # Nettoyer fichier temporaire
            rm -f "$temp_file"
            
            file_count=$((file_count + 1))
        fi
    done
    echo "   🎭 $file_count fichier(s) TTS de scénarios traité(s)"
else
    echo "   ℹ️  Répertoire scenarios/ non trouvé"
fi

# 3. Permissions
echo "🔐 Configuration des permissions..."
chown -R asterisk:asterisk "$ASTERISK_SOUNDS"
chmod -R 644 "$ASTERISK_SOUNDS"/*.wav
chmod 755 "$ASTERISK_SOUNDS"

# 4. Vérification
echo ""
echo "📊 Fichiers installés :"
ls -lh "$ASTERISK_SOUNDS"/*.wav 2>/dev/null | awk '{print "   " $9 " (" $5 ")"}'

# 5. Info sur audio_texts.json
echo ""
echo "💡 Note: audio_texts.json est généré par scenario_generator.py"
echo "   (utilisé pour le clonage vocal à partir des fichiers audio/)"

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
echo "✅ Configuration MULTI-SOURCES terminée !"
echo ""
echo "ℹ️  Notes importantes :"
echo "   • Fichiers installés dans : $ASTERISK_SOUNDS"
echo "   • Format optimisé : 16kHz mono WAV (AudioFork + Vosk + MixMonitor)"
echo "   • Utilisables avec : sound:minibot/[nom_fichier]"
echo "   • Réglage volume appliqué : $GAIN_LABEL"
echo ""
echo "📁 Sources audio traitées :"
echo "   • $AUDIO_SOURCE (audio de base)"
echo "   • $TTS_GENERATED_SOURCE (TTS générés)"
echo "   • $SCENARIOS_SOURCE (TTS scénarios avec préfixe)"
echo ""
echo "🔄 Pour modifier le volume :"
echo "   • Méthode rapide : sudo ./setup_audio.sh -f"
echo "   • Ou manuellement : rm -rf $ASTERISK_SOUNDS/*.wav puis relancer"
echo ""
echo "💡 Ce script est INTELLIGENT :"
echo "   • Recopie seulement les fichiers modifiés"
echo "   • Traite automatiquement TOUTES les sources audio"
echo "   • Compatible streaming temps réel + enregistrement complet"
echo ""
echo "🎯 Prochaines étapes recommandées :"
echo "   1. Vérifier : ls -la $ASTERISK_SOUNDS"
echo "   2. Créer scénario : python3 system/scenario_generator.py (génère audio_texts.json + TTS)"
echo "   3. Tester streaming : ./start_system.sh"
echo ""