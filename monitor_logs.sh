#!/bin/bash
# Script pour monitorer tous les logs en temps réel

echo "================================================"
echo "📊 MONITORING DES LOGS EN TEMPS RÉEL"
echo "================================================"
echo ""
echo "Choisir le mode de monitoring :"
echo "1) Robot ARI seulement"
echo "2) FastAPI seulement"
echo "3) Les deux en parallèle (split screen)"
echo "4) Robot avec filtre (appels uniquement)"
echo "5) Tout avec Asterisk (besoin sudo)"
echo ""
read -p "Votre choix (1-5): " choice

case $choice in
    1)
        echo "📞 Monitoring Robot ARI..."
        tail -f logs/robot_ari_console.log
        ;;
    2)
        echo "🌐 Monitoring FastAPI..."
        tail -f logs/fastapi_console.log
        ;;
    3)
        echo "🔀 Mode Split Screen (Ctrl+C pour quitter)"
        # Utilise tmux si disponible
        if command -v tmux &> /dev/null; then
            tmux new-session \; \
                send-keys 'tail -f logs/robot_ari_console.log' C-m \; \
                split-window -h \; \
                send-keys 'tail -f logs/fastapi_console.log' C-m
        else
            # Alternative sans tmux
            echo "--- ROBOT ARI ---" > /tmp/combined_logs.txt
            tail -f logs/robot_ari_console.log >> /tmp/combined_logs.txt &
            PID1=$!
            echo "--- FASTAPI ---" >> /tmp/combined_logs.txt
            tail -f logs/fastapi_console.log >> /tmp/combined_logs.txt &
            PID2=$!
            tail -f /tmp/combined_logs.txt
            # Clean up on exit
            trap "kill $PID1 $PID2 2>/dev/null" EXIT
        fi
        ;;
    4)
        echo "📞 Monitoring Appels Uniquement..."
        tail -f logs/robot_ari_console.log | grep --color=always -E "(New call|Call ended|Playing|Recording|Transcription|Sentiment|AMD)"
        ;;
    5)
        echo "🔧 Mode Complet avec Asterisk (besoin sudo)..."
        echo "Entrez le mot de passe sudo si demandé"
        # Ouvre 3 terminaux si possible
        gnome-terminal --tab --title="Robot ARI" -- bash -c "tail -f logs/robot_ari_console.log; bash" \
                       --tab --title="FastAPI" -- bash -c "tail -f logs/fastapi_console.log; bash" \
                       --tab --title="Asterisk" -- bash -c "sudo tail -f /var/log/asterisk/full; bash" 2>/dev/null || \
        {
            echo "Affichage séquentiel (pas de gnome-terminal)"
            tail -f logs/robot_ari_console.log &
            PID1=$!
            tail -f logs/fastapi_console.log &
            PID2=$!
            sudo tail -f /var/log/asterisk/full
            trap "kill $PID1 $PID2 2>/dev/null" EXIT
        }
        ;;
    *)
        echo "❌ Choix invalide"
        exit 1
        ;;
esac