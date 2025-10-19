#!/bin/bash

# Script de nettoyage automatique des enregistrements
# Supprime les fichiers WAV de plus de X jours dans /var/spool/asterisk/recording/ et assembled_audio/

# Détecter automatiquement le répertoire du script
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"

# ============================================================
# CONFIGURATION
# ============================================================
RECORDING_DIR="/var/spool/asterisk/recording"
ASSEMBLED_AUDIO_DIR="$PROJECT_ROOT/assembled_audio"
TRANSCRIPTS_DIR="$PROJECT_ROOT/transcripts"
DAYS_TO_KEEP=7  # Nombre de jours à conserver (modifiable)
LOG_FILE="$PROJECT_ROOT/logs/cleanup.log"

# ============================================================
# FONCTIONS
# ============================================================
log_message() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] $1" | tee -a "$LOG_FILE"
}

# ============================================================
# NETTOYAGE
# ============================================================
log_message "🧹 Starting cleanup of recordings older than $DAYS_TO_KEEP days..."

# Compter les fichiers avant nettoyage
BEFORE_COUNT=$(find "$RECORDING_DIR" -name "*.wav" -type f 2>/dev/null | wc -l)
BEFORE_SIZE=$(du -sh "$RECORDING_DIR" 2>/dev/null | awk '{print $1}')

log_message "📊 Before cleanup: $BEFORE_COUNT files, total size: $BEFORE_SIZE"

# Supprimer les fichiers de plus de X jours
DELETED_COUNT=$(find "$RECORDING_DIR" -name "*.wav" -type f -mtime +$DAYS_TO_KEEP 2>/dev/null | wc -l)

if [ "$DELETED_COUNT" -gt 0 ]; then
    find "$RECORDING_DIR" -name "*.wav" -type f -mtime +$DAYS_TO_KEEP -delete 2>/dev/null
    log_message "🗑️  Deleted $DELETED_COUNT old recording(s)"
else
    log_message "✅ No old recordings to delete"
fi

# Compter les fichiers après nettoyage
AFTER_COUNT=$(find "$RECORDING_DIR" -name "*.wav" -type f 2>/dev/null | wc -l)
AFTER_SIZE=$(du -sh "$RECORDING_DIR" 2>/dev/null | awk '{print $1}')

log_message "📊 After cleanup: $AFTER_COUNT files, total size: $AFTER_SIZE"

# Calculer l'espace libéré (approximatif)
if [ "$DELETED_COUNT" -gt 0 ]; then
    log_message "💾 Space saved: ~$((DELETED_COUNT * 81)) KB"
fi

# ============================================================
# NETTOYAGE ASSEMBLED AUDIO
# ============================================================
log_message "🧹 Cleaning assembled audio files older than $DAYS_TO_KEEP days..."

ASSEMBLED_BEFORE_COUNT=$(find "$ASSEMBLED_AUDIO_DIR" -name "*.wav" -type f 2>/dev/null | wc -l)
ASSEMBLED_BEFORE_SIZE=$(du -sh "$ASSEMBLED_AUDIO_DIR" 2>/dev/null | awk '{print $1}')

log_message "📊 Before cleanup: $ASSEMBLED_BEFORE_COUNT assembled audio files, total size: $ASSEMBLED_BEFORE_SIZE"

ASSEMBLED_DELETED_COUNT=$(find "$ASSEMBLED_AUDIO_DIR" -name "*.wav" -type f -mtime +$DAYS_TO_KEEP 2>/dev/null | wc -l)

if [ "$ASSEMBLED_DELETED_COUNT" -gt 0 ]; then
    find "$ASSEMBLED_AUDIO_DIR" -name "*.wav" -type f -mtime +$DAYS_TO_KEEP -delete 2>/dev/null
    log_message "🗑️  Deleted $ASSEMBLED_DELETED_COUNT old assembled audio file(s)"
else
    log_message "✅ No old assembled audio files to delete"
fi

ASSEMBLED_AFTER_COUNT=$(find "$ASSEMBLED_AUDIO_DIR" -name "*.wav" -type f 2>/dev/null | wc -l)
ASSEMBLED_AFTER_SIZE=$(du -sh "$ASSEMBLED_AUDIO_DIR" 2>/dev/null | awk '{print $1}')

log_message "📊 After cleanup: $ASSEMBLED_AFTER_COUNT files, total size: $ASSEMBLED_AFTER_SIZE"

# ============================================================
# NETTOYAGE TRANSCRIPTS
# ============================================================
log_message "🧹 Cleaning transcript files older than $DAYS_TO_KEEP days..."

TRANSCRIPT_BEFORE_COUNT=$(find "$TRANSCRIPTS_DIR" -name "transcript_*.json" -o -name "transcript_*.txt" -type f 2>/dev/null | wc -l)

TRANSCRIPT_DELETED_COUNT=$(find "$TRANSCRIPTS_DIR" \( -name "transcript_*.json" -o -name "transcript_*.txt" \) -type f -mtime +$DAYS_TO_KEEP 2>/dev/null | wc -l)

if [ "$TRANSCRIPT_DELETED_COUNT" -gt 0 ]; then
    find "$TRANSCRIPTS_DIR" \( -name "transcript_*.json" -o -name "transcript_*.txt" \) -type f -mtime +$DAYS_TO_KEEP -delete 2>/dev/null
    log_message "🗑️  Deleted $TRANSCRIPT_DELETED_COUNT old transcript file(s)"
else
    log_message "✅ No old transcript files to delete"
fi

TRANSCRIPT_AFTER_COUNT=$(find "$TRANSCRIPTS_DIR" -name "transcript_*.json" -o -name "transcript_*.txt" -type f 2>/dev/null | wc -l)

log_message "📊 After cleanup: $TRANSCRIPT_AFTER_COUNT transcript files"

# ============================================================
# RÉSUMÉ FINAL
# ============================================================
TOTAL_DELETED=$((DELETED_COUNT + ASSEMBLED_DELETED_COUNT + TRANSCRIPT_DELETED_COUNT))
log_message "🎉 Total files deleted: $TOTAL_DELETED (Recordings: $DELETED_COUNT, Assembled: $ASSEMBLED_DELETED_COUNT, Transcripts: $TRANSCRIPT_DELETED_COUNT)"
log_message "✅ Cleanup completed successfully"
log_message "============================================================"

exit 0
