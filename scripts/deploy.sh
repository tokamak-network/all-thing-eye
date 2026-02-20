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
    
    # Note: Initial data collection is handled by data-collector service
    log_info "⏳ Initial data collection will start automatically..."
    log_info "   Monitor with: ./scripts/deploy.sh logs data-collector"
    
    log_info "✅ Initial deployment completed!"
    log_info "📍 Application is running at: http://$(curl -s ifconfig.me)"
    log_info ""
    log_info "Next steps:"
    log_info "  1. Monitor data collection: ./scripts/deploy.sh logs data-collector"
    log_info "  2. Check service status: ./scripts/deploy.sh status"
    log_info "  3. View web interface: http://$(curl -s ifconfig.me)"
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

# Backup database (MongoDB)
deploy_backup() {
    log_info "💾 Creating MongoDB backup..."
    BACKUP_DIR="backups/$(date +%Y%m%d_%H%M%S)"
    mkdir -p $BACKUP_DIR

    # For local MongoDB in docker-compose
    docker exec -it all-thing-eye-mongodb mongodump --out /data/backup
    docker cp all-thing-eye-mongodb:/data/backup $BACKUP_DIR/

    log_info "✅ Backup created: $BACKUP_DIR"
    log_info "   Note: For MongoDB Atlas, use automated backups in dashboard"
}

# Available services for selective build
ALL_SERVICES=("frontend" "backend" "data-collector" "weekly-bot")

# Build specific services
deploy_build() {
    local services=("$@")

    if [ ${#services[@]} -eq 0 ]; then
        # Interactive mode
        deploy_build_interactive
        return
    fi

    # Validate services
    for service in "${services[@]}"; do
        local valid=false
        for s in "${ALL_SERVICES[@]}"; do
            if [ "$service" == "$s" ]; then
                valid=true
                break
            fi
        done
        if [ "$valid" == false ]; then
            log_error "Unknown service: $service"
            log_info "Available services: ${ALL_SERVICES[*]}"
            exit 1
        fi
    done

    log_info "🏗️  Building services: ${services[*]}"
    docker-compose -f $COMPOSE_FILE up -d --build ${services[*]}

    if [ $? -eq 0 ]; then
        log_info "✅ Build completed!"

        # Reload nginx if backend was rebuilt (upstream IP may have changed)
        for service in "${services[@]}"; do
            if [ "$service" == "backend" ]; then
                log_info "🔄 Reloading nginx (backend upstream refreshed)..."
                docker-compose -f $COMPOSE_FILE restart nginx 2>/dev/null || true
                break
            fi
        done

        echo ""
        deploy_status
    else
        log_error "Build failed!"
        exit 1
    fi
}

# Interactive build selection
deploy_build_interactive() {
    echo ""
    log_info "🔧 Select services to build:"
    echo ""
    echo "  [1] frontend"
    echo "  [2] backend"
    echo "  [3] data-collector"
    echo "  [4] weekly-bot"
    echo "  [a] All services"
    echo "  [q] Quit"
    echo ""
    echo -n "Enter choice (e.g., 1 2 or a): "
    read -r choices

    if [ "$choices" == "q" ]; then
        log_info "Cancelled."
        exit 0
    fi

    if [ "$choices" == "a" ]; then
        deploy_build "${ALL_SERVICES[@]}"
        return
    fi

    local selected=()
    for choice in $choices; do
        case "$choice" in
            1) selected+=("frontend") ;;
            2) selected+=("backend") ;;
            3) selected+=("data-collector") ;;
            4) selected+=("weekly-bot") ;;
            *)
                log_warn "Invalid choice: $choice (skipped)"
                ;;
        esac
    done

    if [ ${#selected[@]} -eq 0 ]; then
        log_error "No valid services selected."
        exit 1
    fi

    echo ""
    log_info "Selected: ${selected[*]}"
    echo -n "Proceed? (y/n) "
    read -r confirm

    if [[ "$confirm" =~ ^[Yy]$ ]]; then
        deploy_build "${selected[@]}"
    else
        log_info "Cancelled."
        exit 0
    fi
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
    build)
        shift
        deploy_build "$@"
        ;;
    *)
        echo "Usage: $0 {init|update|restart|logs|stop|status|backup|build}"
        echo ""
        echo "Commands:"
        echo "  init              - Initial deployment (first time)"
        echo "  update            - Update to latest code and restart"
        echo "  restart           - Restart all services"
        echo "  logs [service]    - Show logs (optional: specify service name)"
        echo "  stop              - Stop all services"
        echo "  status            - Show service status"
        echo "  backup            - Backup databases"
        echo "  build [services]  - Build and deploy specific services"
        echo ""
        echo "Build examples:"
        echo "  $0 build                     # Interactive selection"
        echo "  $0 build frontend            # Build frontend only"
        echo "  $0 build frontend backend    # Build multiple services"
        echo "  $0 build frontend backend data-collector  # Build all"
        echo ""
        echo "Available services: frontend, backend, data-collector, weekly-bot"
        exit 1
        ;;
esac

