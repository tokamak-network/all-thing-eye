# ATI Support Bot Commands

.PHONY: support support-bot webhook-server both help

# Start Combined Server (Recommended)
support:
	python3 scripts/support_bot_combined.py

# Start Support Bot (Socket Mode) - standalone
support-bot:
	python3 scripts/support_bot_socket.py

# Start Claude Webhook Server
webhook-server:
	python3 scripts/claude_webhook_server.py

# Start both (in background + foreground)
both:
	@echo "Starting webhook server in background..."
	@python3 scripts/claude_webhook_server.py &
	@sleep 2
	@echo "Starting support bot..."
	@python3 scripts/support_bot_socket.py

# Stop all
stop:
	@pkill -f "support_bot_socket.py" 2>/dev/null || true
	@pkill -f "claude_webhook_server.py" 2>/dev/null || true
	@echo "Stopped all bots"

# Help
help:
	@echo "Available commands:"
	@echo "  make support-bot    - Start Slack bot (Socket Mode)"
	@echo "  make webhook-server - Start Claude webhook server"
	@echo "  make both           - Start both servers"
	@echo "  make stop           - Stop all bots"
