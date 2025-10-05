# -------------------------------------------
# start_dev.sh - Скрипт для запуска в dev режиме
# -------------------------------------------

#!/bin/bash
# start_dev.sh

echo "Starting News Aggregator in development mode..."

# Activate virtual environment
source venv/bin/activate

# Start infrastructure
docker-compose up -d postgres rabbitmq redis

# Wait for services
echo "Waiting for services to start..."
sleep 10

# Start services in separate terminals (if available)
if command -v gnome-terminal &> /dev/null; then
    # For GNOME
    gnome-terminal --tab --title="API" -- bash -c "source venv/bin/activate; python scripts/start_api.py; exec bash"
    gnome-terminal --tab --title="Telegram_Parser" -- bash -c "source venv/bin/activate; python scripts/start_telegram_parser.py; exec bash"
    gnome-terminal --tab --title="Outbox Relay" -- bash -c "source venv/bin/activate; python scripts/start_outbox_relay.py; exec bash"
elif command -v osascript &> /dev/null; then
    # For macOS
    osascript -e 'tell app "Terminal" to do script "cd '$PWD' && source venv/bin/activate && python scripts/start_api.py"'
    osascript -e 'tell app "Terminal" to do script "cd '$PWD' && source venv/bin/activate && python scripts/start_telegram_parser.py"'
    osascript -e 'tell app "Terminal" to do script "cd '$PWD' && source venv/bin/activate && python scripts/start_outbox_relay.py"'
else
    # Fallback: use tmux if available
    if command -v tmux &> /dev/null; then
        tmux new-session -d -s news-agg
        tmux send-keys -t news-agg "source venv/bin/activate && python scripts/start_api.py" Enter
        tmux new-window -t news-agg -n parser
        tmux send-keys -t news-agg:parser "source venv/bin/activate && python scripts/start_telegram_parser.py" Enter
        tmux new-window -t news-agg -n outbox
        tmux send-keys -t news-agg:outbox "source venv/bin/activate && python scripts/start_outbox_relay.py" Enter
        tmux attach -t news-agg
    else
        echo "Please start the following services manually in separate terminals:"
        echo "1. python scripts/start_api.py"
        echo "2. python scripts/start_telegram_parser.py"
        echo "3. python scripts/start_outbox_relay.py"
    fi
fi
