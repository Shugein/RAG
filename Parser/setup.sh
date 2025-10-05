#!/bin/bash

# setup.sh - Основной скрипт установки
# Запустите: chmod +x setup.sh && ./setup.sh

set -e  # Exit on error

echo "🚀 News Aggregator Setup Script"
echo "================================"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Check Python version
echo -e "${YELLOW}Checking Python version...${NC}"
if command -v python3.11 &> /dev/null; then
    PYTHON_CMD=python3.11
elif command -v python3 &> /dev/null; then
    PYTHON_VERSION=$(python3 --version | cut -d' ' -f2 | cut -d'.' -f1,2)
    if [ "$PYTHON_VERSION" = "3.11" ] || [ "$PYTHON_VERSION" = "3.10" ]; then
        PYTHON_CMD=python3
    else
        echo -e "${RED}Python 3.10+ required. Found: $PYTHON_VERSION${NC}"
        exit 1
    fi
else
    echo -e "${RED}Python not found. Please install Python 3.10+${NC}"
    exit 1
fi

echo -e "${GREEN}Using Python: $($PYTHON_CMD --version)${NC}"

# Check Docker
echo -e "${YELLOW}Checking Docker...${NC}"
if ! command -v docker &> /dev/null; then
    echo -e "${RED}Docker not found. Please install Docker first.${NC}"
    exit 1
fi

if ! command -v docker-compose &> /dev/null; then
    echo -e "${RED}docker-compose not found. Please install docker-compose first.${NC}"
    exit 1
fi

echo -e "${GREEN}Docker found: $(docker --version)${NC}"

# Create project structure
echo -e "${YELLOW}Creating project structure...${NC}"
mkdir -pParser.src/{api,core,services,utils}
mkdir -pParser.src/api/endpoints
mkdir -pParser.src/services/{telegram_parser,enricher,outbox,storage}
mkdir -p config
mkdir -p scripts
mkdir -p docker
mkdir -p migrations/versions
mkdir -p tests/fixtures
mkdir -p sessions
mkdir -p models

# Create __init__.py files
touchParser.src/__init__.py
touchParser.src/api/__init__.py
touchParser.src/api/endpoints/__init__.py
touchParser.src/core/__init__.py
touchParser.src/services/__init__.py
touchParser.src/services/telegram_parser/__init__.py
touchParser.src/services/enricher/__init__.py
touchParser.src/services/outbox/__init__.py
touchParser.src/services/storage/__init__.py
touchParser.src/utils/__init__.py

echo -e "${GREEN}Project structure created${NC}"

# Create virtual environment
echo -e "${YELLOW}Creating virtual environment...${NC}"
$PYTHON_CMD -m venv venv
source venv/bin/activate

# Upgrade pip
pip install --upgrade pip

# Check if requirements.txt exists
if [ ! -f requirements.txt ]; then
    echo -e "${YELLOW}Creating requirements.txt...${NC}"
    cat > requirements.txt << 'EOF'
# Core
python-dotenv==1.0.0
pydantic==2.5.0
pydantic-settings==2.1.0

# Database
sqlalchemy==2.0.23
asyncpg==0.29.0
alembic==1.13.0
psycopg2-binary==2.9.9

# Telegram
telethon==1.34.0
cryptg==0.4.0

# Web framework
fastapi==0.108.0
uvicorn[standard]==0.25.0
httpx==0.26.0

# Message queue
aio-pika==9.4.0

# Cache
redis==5.0.1

# NLP & NER
natasha==1.6.0
pymorphy3==1.2.1
pymorphy3-dicts-ru==2.4.417150.4580142

# Images
pillow==10.1.0
imagehash==4.3.1

# Monitoring & Logging
prometheus-client==0.19.0
structlog==24.1.0
python-json-logger==2.0.7

# Utilities
pyyaml==6.0.1
python-dateutil==2.8.2
aiofiles==23.2.1
tenacity==8.2.3
EOF
fi

# Install Python dependencies
echo -e "${YELLOW}Installing Python dependencies...${NC}"
pip install -r requirements.txt

# Create .env file if not exists
if [ ! -f .env ]; then
    echo -e "${YELLOW}Creating .env file...${NC}"
    cat > .env << 'EOF'
# Database
DATABASE_URL=postgresql+asyncpg://newsuser:newspass@localhost:5432/newsdb

# RabbitMQ
RABBITMQ_URL=amqp://admin:admin123@localhost:5672/

# Redis
REDIS_URL=redis://localhost:6379/0

# Telegram (get from https://my.telegram.org)
TELETHON_API_ID=YOUR_API_ID
TELETHON_API_HASH=YOUR_API_HASH
TELETHON_SESSION_NAME=news_parser
TELETHON_PHONE=+79999999999

# Algopack API
ALGOPACK_API_KEY=YOUR_ALGOPACK_KEY
ALGOPACK_BASE_URL=https://api.algopack.com/v1

# Logging
LOG_LEVEL=INFO
LOG_FORMAT=json
EOF
    echo -e "${RED}Please edit .env file and add your credentials!${NC}"
fi

# Create docker-compose.yml if not exists
if [ ! -f docker-compose.yml ]; then
    echo -e "${YELLOW}Creating docker-compose.yml...${NC}"
    # Copy from artifacts or download
fi

# Start infrastructure
echo -e "${YELLOW}Starting infrastructure services...${NC}"
docker-compose up -d postgres rabbitmq redis

echo -e "${YELLOW}Waiting for services to start...${NC}"
sleep 15

# Initialize database
echo -e "${YELLOW}Initializing database...${NC}"
alembic init migrations 2>/dev/null || true

# Update alembic.ini
sed -i.bak 's|sqlalchemy.url = .*|sqlalchemy.url = postgresql://newsuser:newspass@localhost:5432/newsdb|' alembic.ini

# Create initial migration
echo -e "${YELLOW}Creating database migrations...${NC}"
alembic revision --autogenerate -m "Initial migration" || true
alembic upgrade head

echo -e "${GREEN}✅ Setup complete!${NC}"
echo ""
echo "Next steps:"
echo "1. Edit .env file with your Telegram and Algopack credentials"
echo "2. Run: source venv/bin/activate"
echo "3. Run: python scripts/load_sources.py"
echo "4. Run: python scripts/start_telegram_parser.py"
echo ""
echo "For full system start:"
echo "  docker-compose up -d"
echo ""
echo "API documentation will be available at:"
echo "  http://localhost:8000/docs"