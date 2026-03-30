#!/bin/bash
# Setup Ollama + SQLCoder for Local SQL Generation

GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
BLUE='\033[0;34m'
NC='\033[0m'

echo -e "${BLUE}🧠 Ollama + SQLCoder Setup${NC}"
echo "============================"
echo ""

# Check if Ollama is installed
check_ollama() {
    if command -v ollama &> /dev/null; then
        return 0
    else
        return 1
    fi
}

# Install Ollama
install_ollama() {
    echo -e "${YELLOW}📦 Installing Ollama...${NC}"
    
    # Download and install
    curl -fsSL https://ollama.com/install.sh | sh
    
    if [ $? -eq 0 ]; then
        echo -e "${GREEN}✅ Ollama installed successfully${NC}"
        return 0
    else
        echo -e "${RED}❌ Failed to install Ollama${NC}"
        return 1
    fi
}

# Setup swap memory for safety
setup_swap() {
    echo ""
    echo -e "${YELLOW}💾 Setting up swap memory...${NC}"
    
    # Check existing swap
    EXISTING_SWAP=$(free -m | awk '/^Swap:/{print $2}')
    
    if [ "$EXISTING_SWAP" -gt 0 ]; then
        echo -e "${GREEN}✅ Swap already exists: ${EXISTING_SWAP}MB${NC}"
        return 0
    fi
    
    # Create 4GB swap
    echo "Creating 4GB swap file..."
    sudo fallocate -l 4G /swapfile
    sudo chmod 600 /swapfile
    sudo mkswap /swapfile
    sudo swapon /swapfile
    
    # Make permanent
    echo '/swapfile none swap sw 0 0' | sudo tee -a /etc/fstab
    
    echo -e "${GREEN}✅ Swap created successfully${NC}"
}

# Pull SQLCoder model
pull_model() {
    echo ""
    echo -e "${YELLOW}🤖 Pulling SQLCoder:7b-q4_0 model...${NC}"
    echo -e "${BLUE}   This may take 5-15 minutes depending on your internet...${NC}"
    echo ""
    
    ollama pull sqlcoder:7b-q4_0
    
    if [ $? -eq 0 ]; then
        echo ""
        echo -e "${GREEN}✅ SQLCoder model pulled successfully${NC}"
        return 0
    else
        echo -e "${RED}❌ Failed to pull SQLCoder model${NC}"
        return 1
    fi
}

# Test model
test_model() {
    echo ""
    echo -e "${YELLOW}🧪 Testing SQLCoder model...${NC}"
    
    # Simple test query
    RESULT=$(ollama run sqlcoder:7b-q4_0 "Generate SQL: SELECT count of users" 2>&1)
    
    if echo "$RESULT" | grep -q "SELECT"; then
        echo -e "${GREEN}✅ Model test successful${NC}"
        echo "   Sample output: $(echo $RESULT | head -c 50)..."
        return 0
    else
        echo -e "${YELLOW}⚠️  Model test inconclusive (may still work)${NC}"
        return 1
    fi
}

# Create systemd service (optional)
setup_service() {
    echo ""
    read -p "Create systemd service for Ollama? (y/N): " -n 1 -r
    echo
    
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        echo -e "${YELLOW}🔧 Creating systemd service...${NC}"
        
        cat << 'EOF' | sudo tee /etc/systemd/system/ollama.service
[Unit]
Description=Ollama Service
After=network-online.target

[Service]
ExecStart=/usr/local/bin/ollama serve
User=ollama
Group=ollama
Restart=always
RestartSec=3

[Install]
WantedBy=default.target
EOF
        
        # Create user if not exists
        sudo useradd -r -s /bin/false ollama 2>/dev/null || true
        
        sudo systemctl daemon-reload
        sudo systemctl enable ollama
        
        echo -e "${GREEN}✅ Service created${NC}"
        echo "   Start: sudo systemctl start ollama"
        echo "   Stop:  sudo systemctl stop ollama"
    fi
}

# Update bot config
update_config() {
    echo ""
    echo -e "${YELLOW}📝 Updating bot configuration...${NC}"
    
    ENV_FILE="/home/aseps/MCP/.env"
    
    if [ -f "$ENV_FILE" ]; then
        # Backup
        cp "$ENV_FILE" "${ENV_FILE}.backup.$(date +%Y%m%d_%H%M%S)"
        
        # Add Ollama config if not exists
        if ! grep -q "OLLAMA_URL" "$ENV_FILE"; then
            echo "" >> "$ENV_FILE"
            echo "# Ollama Configuration" >> "$ENV_FILE"
            echo "OLLAMA_URL=http://localhost:11434" >> "$ENV_FILE"
            echo "OLLAMA_MODEL=sqlcoder:7b-q4_0" >> "$ENV_FILE"
            echo "USE_HYBRID_SQL=true" >> "$ENV_FILE"
            echo -e "${GREEN}✅ Config updated${NC}"
        else
            echo -e "${GREEN}✅ Config already exists${NC}"
        fi
    else
        echo -e "${YELLOW}⚠️  Root .env not found. Please create /home/aseps/MCP/.env manually.${NC}"
    fi
}

# Main setup
main() {
    echo -e "${BLUE}System Info:${NC}"
    echo "  CPU: $(grep 'model name' /proc/cpuinfo | head -1 | cut -d':' -f2 | xargs)"
    echo "  RAM: $(free -h | awk '/^Mem:/{print $2}')"
    echo "  OS:  $(lsb_release -d | cut -f2)"
    echo ""
    
    # Step 1: Check/Install Ollama
    if check_ollama; then
        echo -e "${GREEN}✅ Ollama already installed${NC}"
        OLLAMA_VERSION=$(ollama --version)
        echo "   Version: $OLLAMA_VERSION"
    else
        install_ollama || exit 1
    fi
    
    # Step 2: Setup swap
    setup_swap
    
    # Step 3: Start Ollama service
    echo ""
    echo -e "${YELLOW}🚀 Starting Ollama service...${NC}"
    ollama serve &
    OLLAMA_PID=$!
    
    # Wait for service
    sleep 3
    
    # Step 4: Pull model
    pull_model || {
        echo -e "${RED}❌ Model pull failed${NC}"
        kill $OLLAMA_PID 2>/dev/null
        exit 1
    }
    
    # Step 5: Test model
    test_model
    
    # Step 6: Setup service
    setup_service
    
    # Step 7: Update config
    update_config
    
    # Cleanup
    kill $OLLAMA_PID 2>/dev/null
    
    echo ""
    echo -e "${GREEN}🎉 Setup Complete!${NC}"
    echo ""
    echo "Next steps:"
    echo "  1. Start Ollama: ollama serve"
    echo "  2. Start SQL Bot legacy service: ./run_sql_bot.sh"
    echo ""
    echo "Commands:"
    echo "  ollama list          - List models"
    echo "  ollama run sqlcoder  - Test model"
    echo "  ./run_sql_bot.sh     - Start SQL bot legacy service"
}

# Run main
main
