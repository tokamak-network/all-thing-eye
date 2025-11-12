#!/bin/bash

# All-Thing-Eye Deployment Script
# Usage: ./scripts/deploy.sh [init|update|restart|logs|stop]

set -e

COMPOSE_FILE="docker-compose.prod.yml"
PROJECT_NAME="all-thing-eye"

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

log_info() {
    echo -e "${GREEN}[INFO]${NC} $1"
}

log_warn() {
    echo -e "${YELLOW}[WARN]${NC} $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# Check if .env file exists
check_env() {
    if [ ! -f .env ]; then
        log_error ".env file not found!"
        log_info "Please create .env file with required environment variables"
        exit 1
    fi
}

# Initial deployment
deploy_init() {
    log_info "🚀 Starting initial deployment..."
    
    check_env
    
    # Create necessary directories
    log_info "📂 Creating directories..."
    mkdir -p data/databases data/logs/{nginx,backend,celery}
    mkdir -p nginx/ssl
    
    # Build and start containers
    log_info "🏗️  Building Docker images..."
    docker-compose -f $COMPOSE_FILE build
    
    log_info "🐳 Starting containers..."
    docker-compose -f $COMPOSE_FILE up -d
    
    # Wait for backend to be healthy
    log_info "⏳ Waiting for backend to be ready..."
    sleep 10
    
    # Collect initial data
    log_info "📊 Collecting initial data..."
    docker-compose -f $COMPOSE_FILE exec -T backend bash -c "
        python tests/test_github_plugin.py --last-week
        python tests/test_slack_plugin.py --last-week
        python tests/test_google_drive_plugin.py --days 7
        python tests/test_notion_plugin.py --days 7
    "
    
    log_info "✅ Initial deployment completed!"
    log_info "📍 Application is running at: http://$(curl -s ifconfig.me)"
}

# Update deployment
deploy_update() {
    log_info "🔄 Updating deployment..."
    
    # Pull latest code
    log_info "📥 Pulling latest code..."
    git pull origin main
    
    # Rebuild and restart
    log_info "🏗️  Rebuilding images..."
    docker-compose -f $COMPOSE_FILE build
    
    log_info "🔄 Restarting containers..."
    docker-compose -f $COMPOSE_FILE up -d
    
    log_info "✅ Update completed!"
}

# Restart services
deploy_restart() {
    log_info "🔄 Restarting services..."
    docker-compose -f $COMPOSE_FILE restart
    log_info "✅ Services restarted!"
}

# Show logs
deploy_logs() {
    SERVICE=${1:-}
    if [ -z "$SERVICE" ]; then
        docker-compose -f $COMPOSE_FILE logs -f --tail=100
    else
        docker-compose -f $COMPOSE_FILE logs -f --tail=100 $SERVICE
    fi
}

# Stop services
deploy_stop() {
    log_info "🛑 Stopping services..."
    docker-compose -f $COMPOSE_FILE down
    log_info "✅ Services stopped!"
}

# Show status
deploy_status() {
    log_info "📊 Service status:"
    docker-compose -f $COMPOSE_FILE ps
}

# Backup database
deploy_backup() {
    log_info "💾 Creating database backup..."
    BACKUP_DIR="backups/$(date +%Y%m%d_%H%M%S)"
    mkdir -p $BACKUP_DIR
    cp -r data/databases/* $BACKUP_DIR/
    log_info "✅ Backup created: $BACKUP_DIR"
}

# Main
case "${1:-}" in
    init)
        deploy_init
        ;;
    update)
        deploy_update
        ;;
    restart)
        deploy_restart
        ;;
    logs)
        deploy_logs $2
        ;;
    stop)
        deploy_stop
        ;;
    status)
        deploy_status
        ;;
    backup)
        deploy_backup
        ;;
    *)
        echo "Usage: $0 {init|update|restart|logs|stop|status|backup}"
        echo ""
        echo "Commands:"
        echo "  init     - Initial deployment (first time)"
        echo "  update   - Update to latest code and restart"
        echo "  restart  - Restart all services"
        echo "  logs     - Show logs (optional: specify service name)"
        echo "  stop     - Stop all services"
        echo "  status   - Show service status"
        echo "  backup   - Backup databases"
        exit 1
        ;;
esac

