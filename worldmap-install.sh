#!/bin/bash

# Exit immediately if a command exits with a non-zero status
set -e

# Styling variables
GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
NC='\033[0m'

echo -e "${BLUE}=== WorldMap Quick Installer ===${NC}"

# Determine installation directory
TARGET_DIR="${1:-$HOME/worldmap}"
INSTALL_DIR=$(realpath "$TARGET_DIR")
mkdir -p "$INSTALL_DIR"
cd "$INSTALL_DIR"

# Check for prerequisites
if ! command -v docker >/dev/null 2>&1; then
    echo "Error: Docker is not installed."
    exit 1
fi

# Download and setup configuration
echo "Downloading configuration templates..."
mkdir -p config

# Fetch templates from repository
curl -fsSL https://raw.githubusercontent.com/paulwaite87/worldmap/refs/heads/master/docker-compose-prod.yml -o docker-compose.yml
curl -fsSL https://raw.githubusercontent.com/paulwaite87/worldmap/refs/heads/master/config/worldmap.conf.example -o config/worldmap.conf

# Fetch and setup .env
if [ ! -f .env ]; then
    curl -fsSL https://raw.githubusercontent.com/paulwaite87/worldmap/refs/heads/master/.env.tmpl -o .env
    echo -e "${YELLOW}Template .env created. Please edit it to add your API keys.${NC}"
fi

# Download the wallpaper daemon scripts
echo "Setting up wallpaper daemon..."
curl -fsSL https://raw.githubusercontent.com/paulwaite87/worldmap/refs/heads/master/wallpaper_update_daemon.py -o wallpaper_update_daemon.py
curl -fsSL https://raw.githubusercontent.com/paulwaite87/worldmap/refs/heads/master/wallpaper_update.sh -o wallpaper_update.sh
chmod +x wallpaper_update.sh

# Create the 'worldmap' control script
echo "Creating control script..."
cat << 'EOF' > worldmap.sh
#!/bin/bash
case "$1" in
    start) docker compose up -d ;;
    stop) docker compose down ;;
    restart) docker compose restart ;;
    logs) docker compose logs -f ;;
    status) docker compose ps ;;
    map-start) nohup ./wallpaper_update.sh > wallpaper.log 2>&1 & echo "Daemon started (logs: wallpaper.log)" ;;
    map-stop) pkill -f wallpaper_update_daemon.py && echo "Daemon stopped" ;;
    *) echo "Usage: worldmap {start|stop|restart|logs|status|map-start|map-stop}" ;;esac
EOF
chmod +x worldmap.sh

# Start the system
echo -e "${BLUE}Starting World Map...${NC}"
./worldmap.sh start

echo -e "${GREEN}=== Installation Complete! ===${NC}"
echo "System initialized. Please update your settings:"
echo "API Keys: ${GREEN}$INSTALL_DIR/.env${NC}"
echo "Configuration: ${GREEN}$INSTALL_DIR/config/worldmap.conf${NC}"
echo "   Web UI: http://localhost:8180/"
echo "Use ${GREEN}$INSTALL_DIR/worldmap.sh${NC} to manage the system."
echo ""