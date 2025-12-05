#!/bin/bash

# All-Thing-Eye Docker Services Rebuild Script
# Usage: ./scripts/rebuild-services.sh [options]

set -e  # Exit on error

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Default values
COMPOSE_FILE="docker-compose.prod.yml"
NO_CACHE=false
SERVICES=""

# Function to print colored output
print_info() {
    echo -e "${BLUE}ℹ️  $1${NC}"
}

print_success() {
    echo -e "${GREEN}✅ $1${NC}"
}

print_warning() {
    echo -e "${YELLOW}⚠️  $1${NC}"
}

print_error() {
    echo -e "${RED}❌ $1${NC}"
}

# Function to show usage
show_usage() {
    cat << EOF
Usage: ./scripts/rebuild-services.sh [OPTIONS]

Rebuild and restart Docker services for All-Thing-Eye project.

OPTIONS:
    -f, --frontend          Rebuild only frontend service
    -b, --backend           Rebuild only backend service
    -a, --all               Rebuild all services (default)
    -n, --no-cache          Build without using cache
    -d, --down              Stop and remove containers before rebuild
    -h, --help              Show this help message

EXAMPLES:
    # Rebuild both frontend and backend
    ./scripts/rebuild-services.sh

    # Rebuild only frontend
    ./scripts/rebuild-services.sh --frontend

    # Rebuild only backend
    ./scripts/rebuild-services.sh --backend

    # Rebuild all with no cache
    ./scripts/rebuild-services.sh --all --no-cache

    # Stop containers, then rebuild
    ./scripts/rebuild-services.sh --down --all

EOF
}

# Parse command line arguments
STOP_FIRST=false

while [[ $# -gt 0 ]]; do
    case $1 in
        -f|--frontend)
            SERVICES="$SERVICES frontend"
            shift
            ;;
        -b|--backend)
            SERVICES="$SERVICES backend"
            shift
            ;;
        -a|--all)
            SERVICES=""
            shift
            ;;
        -n|--no-cache)
            NO_CACHE=true
            shift
            ;;
        -d|--down)
            STOP_FIRST=true
            shift
            ;;
        -h|--help)
            show_usage
            exit 0
            ;;
        *)
            print_error "Unknown option: $1"
            show_usage
            exit 1
            ;;
    esac
done

# If no services specified, rebuild both frontend and backend
if [ -z "$SERVICES" ]; then
    SERVICES="frontend backend"
fi

# Trim whitespace
SERVICES=$(echo $SERVICES | xargs)

print_info "Starting rebuild process..."
print_info "Services to rebuild: $SERVICES"

# Stop containers first if requested
if [ "$STOP_FIRST" = true ]; then
    print_warning "Stopping and removing existing containers..."
    docker-compose -f $COMPOSE_FILE down
    print_success "Containers stopped and removed"
fi

# Build command
BUILD_CMD="docker-compose -f $COMPOSE_FILE build"

if [ "$NO_CACHE" = true ]; then
    BUILD_CMD="$BUILD_CMD --no-cache"
    print_warning "Building without cache (this may take longer)..."
fi

BUILD_CMD="$BUILD_CMD $SERVICES"

# Execute build
print_info "Building services..."
print_info "Command: $BUILD_CMD"
eval $BUILD_CMD

if [ $? -eq 0 ]; then
    print_success "Build completed successfully"
else
    print_error "Build failed"
    exit 1
fi

# Start services
print_info "Starting services..."
docker-compose -f $COMPOSE_FILE up -d $SERVICES

if [ $? -eq 0 ]; then
    print_success "Services started successfully"
else
    print_error "Failed to start services"
    exit 1
fi

# Show running containers
print_info "Running containers:"
docker-compose -f $COMPOSE_FILE ps

print_success "Rebuild complete! 🎉"
print_info "You can check logs with: docker-compose -f $COMPOSE_FILE logs -f $SERVICES"
