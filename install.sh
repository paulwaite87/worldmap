#!/bin/bash

# Exit immediately if a command exits with a non-zero status
set -e

# Styling variables
GREEN='\033[0;32m'
BLUE='\033[0;34m'
NC='\033[0m'

echo -e "${BLUE}=== WorldMap Quick Installer ===${NC}"

# 1. Check for prerequisites
if ! command -v docker >/dev/null 2>&1; then
    echo "Error: Docker is not installed. Please install Docker first."
    exit 1
fi

# 2. Setup installation directory
INSTALL_DIR="$HOME/worldmap"
echo -e "Setting up WorldMap in ${GREEN}${INSTALL_DIR}${NC}..."
mkdir -p "$INSTALL_DIR"
cd "$INSTALL_DIR"

# 3. Download the production docker-compose file
echo "Downloading configuration..."
# NOTE: Changed filename to match your new docker-compose.prod.yml
curl -fsSL https://raw.githubusercontent.com/paulwaite87/WorldMap/master/docker-compose.prod.yml -o docker-compose.yml

# 4. Start the system
echo -e "${BLUE}Starting WorldMap containers...${NC}"
# Use -f to ensure it specifically uses the downloaded file
docker compose -f docker-compose.yml up -d

echo -e "${GREEN}=== Installation Complete! ===${NC}"
echo "WorldMap is now running in the background."
