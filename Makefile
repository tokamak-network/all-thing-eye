# ATI Support Bot Commands

.PHONY: support support-bot webhook-server both weekly stop-weekly executor stop-executor help

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

# Start Weekly Output Bot
weekly:
	python3 scripts/weekly_output_bot.py

# Stop Weekly Output Bot
stop-weekly:
	@pkill -f "weekly_output_bot.py" 2>/dev/null || true
	@echo "Stopped weekly output bot"

# Start Claude Executor (polls AWS for approved tickets)
executor:
	python3 scripts/claude_executor.py

# Stop Claude Executor
stop-executor:
	@pkill -f "claude_executor.py" 2>/dev/null || true
	@echo "Stopped claude executor"

# Stop all
stop:
	@pkill -f "support_bot_socket.py" 2>/dev/null || true
	@pkill -f "claude_webhook_server.py" 2>/dev/null || true
	@echo "Stopped all bots"

# Help
help:
	@echo "Available commands:"
	@echo "  make support        - Start Support Bot (Socket Mode, legacy)"
	@echo "  make executor       - Start Claude Executor (polls AWS for approved tickets)"
	@echo "  make weekly         - Start Weekly Output Bot"
	@echo "  make stop-executor  - Stop Claude Executor"
	@echo "  make stop-weekly    - Stop Weekly Output Bot"
	@echo "  make stop           - Stop all bots"
