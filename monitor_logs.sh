#!/bin/bash
# Script pour monitorer tous les logs en temps réel

echo "================================================"
echo "📊 MONITORING DES LOGS EN TEMPS RÉEL"
echo "================================================"
echo ""
echo "Choisir le mode de monitoring streaming :"
echo "1) Robot ARI Streaming seulement"
echo "2) API FastAPI seulement"
echo "3) Batch Caller (gestionnaire campagnes)"
echo "4) Mode Split Screen (Robot + API + Batch)"
echo "5) Appels streaming uniquement (avec filtres)"
echo "6) Streaming services (Vosk + Ollama + Intent)"
echo "7) Tout avec Asterisk (mode complet)"
echo ""
read -p "Votre choix (1-7): " choice

case $choice in
    1)
        echo "🌊 Monitoring Robot ARI Streaming..."
        tail -f logs/robot_ari_console.log
        ;;
    2)
        echo "🌐 Monitoring API FastAPI..."
        tail -f logs/main.log
        ;;
    3)
        echo "📋 Monitoring Batch Caller (Campagnes)..."
        tail -f logs/batch_caller_console.log
        ;;
    4)
        echo "🔀 Mode Split Screen Streaming (Ctrl+C pour quitter)"
        # Utilise tmux si disponible
        if command -v tmux &> /dev/null; then
            tmux new-session \; \
                send-keys 'tail -f logs/robot_ari_console.log' C-m \; \
                split-window -h \; \
                send-keys 'tail -f logs/main.log' C-m \; \
                split-window -v \; \
                send-keys 'tail -f logs/batch_caller_console.log' C-m
        else
            # Alternative sans tmux
            echo "--- ROBOT ARI STREAMING ---" > /tmp/streaming_logs.txt
            tail -f logs/robot_ari_console.log >> /tmp/streaming_logs.txt &
            PID1=$!
            echo "--- API FASTAPI ---" >> /tmp/streaming_logs.txt
            tail -f logs/main.log >> /tmp/streaming_logs.txt &
            PID2=$!
            echo "--- BATCH CALLER ---" >> /tmp/streaming_logs.txt
            tail -f logs/batch_caller_console.log >> /tmp/streaming_logs.txt &
            PID3=$!
            tail -f /tmp/streaming_logs.txt
            # Clean up on exit
            trap "kill $PID1 $PID2 $PID3 2>/dev/null" EXIT
        fi
        ;;
    5)
        echo "📞 Monitoring Appels Streaming (avec filtres)..."
        tail -f logs/robot_ari_console.log | grep --color=always -E "(New call|Call ended|Playing|barge-in|transcription|Intent|AMD|Streaming|Lead|Not_interested)"
        ;;
    6)
        echo "🎤 Monitoring Services Streaming (Vosk + Ollama + Intent)..."
        tail -f logs/*.log | grep --color=always -E "(Vosk|Ollama|Intent|ASR|NLP|latency|confidence|speech_start|speech_end)"
        ;;
    7)
        echo "🔧 Mode Complet Streaming + Asterisk (besoin sudo)..."
        echo "Entrez le mot de passe sudo si demandé"
        # Ouvre 4 terminaux si possible
        gnome-terminal --tab --title="Robot Streaming" -- bash -c "tail -f logs/robot_ari_console.log; bash" \
                       --tab --title="API FastAPI" -- bash -c "tail -f logs/main.log; bash" \
                       --tab --title="Batch Caller" -- bash -c "tail -f logs/batch_caller_console.log; bash" \
                       --tab --title="Asterisk" -- bash -c "sudo tail -f /var/log/asterisk/full; bash" 2>/dev/null || \
        {
            echo "Affichage séquentiel streaming (pas de gnome-terminal)"
            tail -f logs/robot_ari_console.log &
            PID1=$!
            tail -f logs/main.log &
            PID2=$!
            tail -f logs/batch_caller_console.log &
            PID3=$!
            sudo tail -f /var/log/asterisk/full
            trap "kill $PID1 $PID2 $PID3 2>/dev/null" EXIT
        }
        ;;
    *)
        echo "❌ Choix invalide"
        exit 1
        ;;
esac