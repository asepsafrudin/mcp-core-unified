#!/bin/bash
# Setup Database untuk MCP Unified dengan Fallback Otomatis
# Priority: Docker -> Native -> Skip (tanpa database)

set -e

echo "🗄️  MCP Unified Database Setup dengan Fallback"
echo "==============================================="
echo ""
echo "Priority: Docker → Native → Skip (tanpa database)"
echo ""

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Check Docker availability
check_docker() {
    if command -v docker &> /dev/null && docker info &> /dev/null; then
        return 0
    else
        return 1
    fi
}

# Check OS for native install
check_os() {
    if [ -f /etc/os-release ]; then
        . /etc/os-release
        if [[ "$ID" == "ubuntu" || "$ID" == "debian" || "$ID" == "arch" ]]; then
            return 0
        fi
    fi
    return 1
}

# Setup dengan Docker
setup_docker() {
    echo -e "${GREEN}🐳 Mencoba setup dengan Docker...${NC}"
    
    # PostgreSQL
    echo "📦 Starting PostgreSQL container..."
    if ! docker run -d \
        --name mcp-postgres \
        -e POSTGRES_USER=aseps \
        -e POSTGRES_PASSWORD=secure123 \
        -e POSTGRES_DB=mcp \
        -p 5432:5432 \
        -v postgres_data:/var/lib/postgresql/data \
        --restart unless-stopped \
        postgres:15-alpine 2>/dev/null; then
        
        # Container mungkin sudah ada, coba restart
        echo -e "${YELLOW}⚠️  Container PostgreSQL sudah ada, mencoba restart...${NC}"
        docker restart mcp-postgres || return 1
    fi
    
    # Redis
    echo "📦 Starting Redis container..."
    if ! docker run -d \
        --name mcp-redis \
        -p 6379:6379 \
        -v redis_data:/data \
        --restart unless-stopped \
        redis:7-alpine 2>/dev/null; then
        
        echo -e "${YELLOW}⚠️  Container Redis sudah ada, mencoba restart...${NC}"
        docker restart mcp-redis || return 1
    fi
    
    # Wait for services
    echo "⏳ Menunggu database ready (10 detik)..."
    sleep 10
    
    # Test connections
    echo "🧪 Testing PostgreSQL connection..."
    if docker exec mcp-postgres pg_isready -U aseps > /dev/null 2>&1; then
        echo -e "${GREEN}✅ PostgreSQL ready${NC}"
    else
        echo -e "${YELLOW}⚠️  PostgreSQL belum ready, mungkin butuh waktu lebih...${NC}"
    fi
    
    echo "🧪 Testing Redis connection..."
    if docker exec mcp-redis redis-cli ping > /dev/null 2>&1; then
        echo -e "${GREEN}✅ Redis ready${NC}"
    else
        echo -e "${YELLOW}⚠️  Redis belum ready, mungkin butuh waktu lebih...${NC}"
    fi
    
    echo ""
    echo -e "${GREEN}✅ Docker setup berhasil!${NC}"
    echo "PostgreSQL: localhost:5432 (user: aseps, pass: secure123, db: mcp)"
    echo "Redis: localhost:6379"
    return 0
}

# Setup Native
setup_native() {
    echo -e "${GREEN}🔧 Fallback ke Native Install...${NC}"
    
    if [ -f /etc/os-release ]; then
        . /etc/os-release
        OS=$ID
    else
        echo -e "${RED}❌ Cannot detect OS${NC}"
        return 1
    fi
    
    echo "OS terdeteksi: $OS"
    
    if [ "$OS" = "ubuntu" ] || [ "$OS" = "debian" ]; then
        echo "📦 Installing PostgreSQL & Redis..."
        sudo apt-get update -qq
        sudo apt-get install -y -qq postgresql postgresql-contrib redis-server || return 1
        
        # Start services
        sudo service postgresql start
        sudo service redis-server start
        
        # Create database user
        echo "🗄️  Setting up PostgreSQL user..."
        sudo -u postgres psql -c "CREATE USER aseps WITH PASSWORD 'secure123';" 2>/dev/null || echo "User sudah ada"
        sudo -u postgres psql -c "CREATE DATABASE mcp OWNER aseps;" 2>/dev/null || echo "Database sudah ada"
        sudo -u postgres psql -c "GRANT ALL PRIVILEGES ON DATABASE mcp TO aseps;"
        
        # Configure PostgreSQL untuk local connection
        sudo sed -i 's/scram-sha-256/trust/g' /etc/postgresql/*/main/pg_hba.conf 2>/dev/null || true
        sudo service postgresql restart
        
    elif [ "$OS" = "arch" ]; then
        echo "📦 Installing PostgreSQL & Redis (Arch)..."
        sudo pacman -S --noconfirm postgresql redis || return 1
        
        # Init PostgreSQL
        sudo -u postgres initdb -D /var/lib/postgres/data 2>/dev/null || true
        
        # Start services
        sudo systemctl start postgresql
        sudo systemctl start redis
        
        # Setup database
        sudo -u postgres psql -c "CREATE USER aseps WITH PASSWORD 'secure123';" 2>/dev/null || true
        sudo -u postgres psql -c "CREATE DATABASE mcp OWNER aseps;" 2>/dev/null || true
    else
        echo -e "${RED}❌ OS tidak didukung untuk native install${NC}"
        return 1
    fi
    
    echo -e "${GREEN}✅ Native setup berhasil!${NC}"
    return 0
}

# Fallback: Tanpa database
setup_skip() {
    echo -e "${YELLOW}⚠️  Fallback: Menjalankan tanpa database${NC}"
    echo ""
    echo "Server MCP Unified tetap bisa berjalan tanpa database."
    echo "Fitur yang tersedia:"
    echo "  ✅ File operations (read_file, write_file, list_dir)"
    echo "  ✅ Shell execution (run_shell)"
    echo "  ✅ Workspace management"
    echo "  ✅ Remote tools"
    echo ""
    echo "Fitur yang disabled:"
    echo "  ❌ Memory save/search"
    echo "  ❌ Working memory cache"
    echo ""
    echo "Untuk mengaktifkan fitur memory, install database nanti dengan:"
    echo "  ./setup_database.sh"
    return 0
}

# Main logic dengan fallback
main() {
    # Coba Docker dulu
    if check_docker; then
        echo -e "${GREEN}✅ Docker tersedia${NC}"
        if setup_docker; then
            SETUP_SUCCESS=true
        else
            echo -e "${YELLOW}⚠️  Docker setup gagal, mencoba fallback...${NC}"
            SETUP_SUCCESS=false
        fi
    else
        echo -e "${YELLOW}⚠️  Docker tidak tersedia${NC}"
        SETUP_SUCCESS=false
    fi
    
    # Fallback ke Native jika Docker gagal
    if [ "$SETUP_SUCCESS" != "true" ]; then
        if check_os; then
            if setup_native; then
                SETUP_SUCCESS=true
            else
                echo -e "${YELLOW}⚠️  Native setup gagal${NC}"
                SETUP_SUCCESS=false
            fi
        else
            echo -e "${YELLOW}⚠️  OS tidak didukung untuk native install${NC}"
            SETUP_SUCCESS=false
        fi
    fi
    
    # Final fallback: Skip (tanpa database)
    if [ "$SETUP_SUCCESS" != "true" ]; then
        setup_skip
    fi
    
    # Summary
    echo ""
    echo "================================"
    echo "📝 Summary:"
    echo "================================"
    
    if [ "$SETUP_SUCCESS" = "true" ]; then
        echo -e "${GREEN}✅ Database berhasil di-setup!${NC}"
        echo ""
        echo "Environment variables (sudah di .env):"
        echo "  POSTGRES_USER=aseps"
        echo "  POSTGRES_PASSWORD=secure123"
        echo "  POSTGRES_SERVER=localhost"
        echo "  POSTGRES_DB=mcp"
        echo "  REDIS_URL=redis://localhost:6379/0"
        echo ""
        echo "Command untuk restart server:"
        echo "  cd /home/aseps/MCP/mcp-unified && ./run.sh"
    else
        echo -e "${YELLOW}⚠️  Berjalan tanpa database${NC}"
        echo ""
        echo "Server tetap berfungsi dengan fitur dasar."
        echo "Command:"
        echo "  cd /home/aseps/MCP/mcp-unified && ./run.sh"
    fi
    
    echo ""
    echo "================================"
}

# Run main
main
