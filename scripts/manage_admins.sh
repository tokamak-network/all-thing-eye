#!/bin/bash

# Admin Address Management Script
# Easily add, remove, or list admin addresses for Web3 authentication

set -e

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Configuration
ENV_FILE=".env"
BACKUP_DIR="backups/env"

# Helper functions
log_info() {
    echo -e "${GREEN}[INFO]${NC} $1"
}

log_warn() {
    echo -e "${YELLOW}[WARN]${NC} $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

log_success() {
    echo -e "${GREEN}[✓]${NC} $1"
}

# Check if .env file exists
check_env_file() {
    if [ ! -f "$ENV_FILE" ]; then
        log_error ".env file not found!"
        log_info "Please create .env file first"
        exit 1
    fi
}

# Validate Ethereum address format
validate_address() {
    local address=$1
    
    # Check if starts with 0x
    if [[ ! $address =~ ^0x ]]; then
        log_error "Invalid address format: must start with 0x"
        return 1
    fi
    
    # Check if 42 characters (0x + 40 hex chars)
    if [ ${#address} -ne 42 ]; then
        log_error "Invalid address length: must be 42 characters (0x + 40 hex)"
        return 1
    fi
    
    # Check if hex characters
    if [[ ! $address =~ ^0x[0-9a-fA-F]{40}$ ]]; then
        log_error "Invalid address format: must contain only hexadecimal characters"
        return 1
    fi
    
    return 0
}

# Backup .env file
backup_env() {
    mkdir -p "$BACKUP_DIR"
    local backup_file="$BACKUP_DIR/env_backup_$(date +%Y%m%d_%H%M%S)"
    cp "$ENV_FILE" "$backup_file"
    log_info "Backup created: $backup_file"
}

# Get current admin addresses
get_admin_addresses() {
    if grep -q "^ADMIN_ADDRESSES=" "$ENV_FILE"; then
        grep "^ADMIN_ADDRESSES=" "$ENV_FILE" | cut -d'=' -f2 | tr -d '"' | tr -d "'"
    else
        echo ""
    fi
}

# List current admin addresses
list_admins() {
    check_env_file
    
    local addresses=$(get_admin_addresses)
    
    echo ""
    echo -e "${BLUE}════════════════════════════════════════════════════════${NC}"
    echo -e "${BLUE}             Current Admin Addresses${NC}"
    echo -e "${BLUE}════════════════════════════════════════════════════════${NC}"
    echo ""
    
    if [ -z "$addresses" ]; then
        log_warn "No admin addresses configured"
        echo ""
        log_info "Add your first admin with:"
        echo "  ./scripts/manage_admins.sh add 0xYourAddress"
        echo ""
    else
        IFS=',' read -ra ADDR_ARRAY <<< "$addresses"
        local count=1
        for addr in "${ADDR_ARRAY[@]}"; do
            # Trim whitespace
            addr=$(echo "$addr" | xargs)
            echo -e "  ${GREEN}[$count]${NC} $addr"
            ((count++))
        done
        echo ""
        echo -e "${BLUE}════════════════════════════════════════════════════════${NC}"
        echo -e "Total: ${GREEN}${#ADDR_ARRAY[@]}${NC} admin(s)"
    fi
    echo ""
}

# Add admin address
add_admin() {
    local new_address=$1
    
    if [ -z "$new_address" ]; then
        log_error "Address is required"
        echo "Usage: $0 add 0xYourAddress"
        exit 1
    fi
    
    check_env_file
    
    # Validate address
    if ! validate_address "$new_address"; then
        exit 1
    fi
    
    # Get current addresses
    local current_addresses=$(get_admin_addresses)
    
    # Check if address already exists
    if [[ ",$current_addresses," == *",$new_address,"* ]]; then
        log_warn "Address already exists: $new_address"
        exit 0
    fi
    
    # Backup before modification
    backup_env
    
    # Add new address
    if [ -z "$current_addresses" ]; then
        # First admin address
        if grep -q "^ADMIN_ADDRESSES=" "$ENV_FILE"; then
            # Line exists but empty
            sed -i.tmp "s|^ADMIN_ADDRESSES=.*|ADMIN_ADDRESSES=$new_address|" "$ENV_FILE"
        else
            # Line doesn't exist, add it
            echo "ADMIN_ADDRESSES=$new_address" >> "$ENV_FILE"
        fi
    else
        # Append to existing addresses
        local updated_addresses="$current_addresses,$new_address"
        sed -i.tmp "s|^ADMIN_ADDRESSES=.*|ADMIN_ADDRESSES=$updated_addresses|" "$ENV_FILE"
    fi
    
    # Remove temporary file
    rm -f "$ENV_FILE.tmp"
    
    log_success "Admin address added: $new_address"
    
    # Show updated list
    list_admins
    
    # Ask to restart services
    echo ""
    read -p "$(echo -e ${YELLOW}Restart services to apply changes? [y/N]: ${NC})" -n 1 -r
    echo ""
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        restart_services
    else
        log_warn "Changes will take effect after next restart"
        log_info "Run: ./scripts/deploy.sh restart"
    fi
}

# Remove admin address
remove_admin() {
    local remove_address=$1
    
    if [ -z "$remove_address" ]; then
        log_error "Address is required"
        echo "Usage: $0 remove 0xYourAddress"
        exit 1
    fi
    
    check_env_file
    
    # Validate address format
    if ! validate_address "$remove_address"; then
        exit 1
    fi
    
    # Get current addresses
    local current_addresses=$(get_admin_addresses)
    
    if [ -z "$current_addresses" ]; then
        log_error "No admin addresses configured"
        exit 1
    fi
    
    # Check if address exists
    if [[ ",$current_addresses," != *",$remove_address,"* ]]; then
        log_error "Address not found: $remove_address"
        exit 1
    fi
    
    # Backup before modification
    backup_env
    
    # Remove address
    IFS=',' read -ra ADDR_ARRAY <<< "$current_addresses"
    local new_addresses=""
    for addr in "${ADDR_ARRAY[@]}"; do
        addr=$(echo "$addr" | xargs)
        if [ "$addr" != "$remove_address" ]; then
            if [ -z "$new_addresses" ]; then
                new_addresses="$addr"
            else
                new_addresses="$new_addresses,$addr"
            fi
        fi
    done
    
    # Update .env file
    sed -i.tmp "s|^ADMIN_ADDRESSES=.*|ADMIN_ADDRESSES=$new_addresses|" "$ENV_FILE"
    rm -f "$ENV_FILE.tmp"
    
    log_success "Admin address removed: $remove_address"
    
    # Show updated list
    list_admins
    
    # Ask to restart services
    echo ""
    read -p "$(echo -e ${YELLOW}Restart services to apply changes? [y/N]: ${NC})" -n 1 -r
    echo ""
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        restart_services
    else
        log_warn "Changes will take effect after next restart"
        log_info "Run: ./scripts/deploy.sh restart"
    fi
}

# Restart services
restart_services() {
    log_info "Restarting services..."
    
    if [ -f "docker-compose.prod.yml" ]; then
        docker-compose -f docker-compose.prod.yml restart backend frontend
        log_success "Services restarted"
        log_info "Changes are now active"
    elif [ -f "docker-compose.yml" ]; then
        docker-compose restart backend frontend
        log_success "Services restarted"
        log_info "Changes are now active"
    else
        log_warn "docker-compose file not found"
        log_info "Please restart services manually"
    fi
}

# Show usage
show_usage() {
    cat << EOF

${BLUE}═══════════════════════════════════════════════════════════════${NC}
${BLUE}              Admin Address Management Tool${NC}
${BLUE}═══════════════════════════════════════════════════════════════${NC}

${GREEN}Usage:${NC}
  $0 <command> [arguments]

${GREEN}Commands:${NC}
  ${YELLOW}list${NC}                      List all current admin addresses
  ${YELLOW}add${NC} <address>             Add a new admin address
  ${YELLOW}remove${NC} <address>          Remove an admin address
  ${YELLOW}help${NC}                      Show this help message

${GREEN}Examples:${NC}
  # List current admins
  $0 list

  # Add new admin
  $0 add 0x1234567890123456789012345678901234567890

  # Remove admin
  $0 remove 0x1234567890123456789012345678901234567890

${GREEN}Notes:${NC}
  - Address must be a valid Ethereum address (0x + 40 hex characters)
  - Changes require service restart to take effect
  - Backup is automatically created before any modification
  - Backups are stored in: $BACKUP_DIR/

${GREEN}For more information:${NC}
  See docs/ADMIN_MANAGEMENT.md

${BLUE}═══════════════════════════════════════════════════════════════${NC}

EOF
}

# Main script
case "${1:-}" in
    list)
        list_admins
        ;;
    add)
        add_admin "$2"
        ;;
    remove)
        remove_admin "$2"
        ;;
    help|--help|-h)
        show_usage
        ;;
    *)
        show_usage
        exit 1
        ;;
esac

