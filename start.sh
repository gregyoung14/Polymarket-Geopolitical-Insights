#!/bin/bash
set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

echo -e "${BLUE}╔══════════════════════════════════════════════════════════════╗${NC}"
echo -e "${BLUE}║              🚀 Polymarket Insights Setup & Launch Script               ║${NC}"
echo -e "${BLUE}╚══════════════════════════════════════════════════════════════╝${NC}"
echo ""

# Get script directory
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BACKEND_DIR="$SCRIPT_DIR/backend"
EXTENSION_DIR="$SCRIPT_DIR/chrome-extension"

# Parse arguments
DEV_MODE=false
if [[ "$1" == "--dev" ]]; then
    DEV_MODE=true
    echo -e "${YELLOW}📦 Running in DEVELOPMENT mode${NC}"
else
    echo -e "${GREEN}📦 Running in PRODUCTION mode${NC}"
fi
echo ""

# ============================================================================
# Step 1: Check and install dependencies via Homebrew
# ============================================================================
echo -e "${BLUE}[1/5] Checking system dependencies...${NC}"

# Check for Homebrew
if ! command -v brew &> /dev/null; then
    echo -e "${RED}❌ Homebrew not found. Please install it first:${NC}"
    echo -e "   /bin/bash -c \"\$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)\""
    exit 1
fi
echo -e "${GREEN}✓ Homebrew found${NC}"

# Check and install bun
if ! command -v bun &> /dev/null; then
    echo -e "${YELLOW}📥 Installing bun...${NC}"
    brew install oven-sh/bun/bun
else
    echo -e "${GREEN}✓ bun found ($(bun --version))${NC}"
fi

# Check and install uv
if ! command -v uv &> /dev/null; then
    echo -e "${YELLOW}📥 Installing uv...${NC}"
    brew install uv
else
    echo -e "${GREEN}✓ uv found ($(uv --version 2>&1 | head -1))${NC}"
fi

# Check and install tmux
if ! command -v tmux &> /dev/null; then
    echo -e "${YELLOW}📥 Installing tmux...${NC}"
    brew install tmux
else
    echo -e "${GREEN}✓ tmux found${NC}"
fi

echo ""

# ============================================================================
# Step 2: Install Python dependencies
# ============================================================================
echo -e "${BLUE}[2/5] Installing Python dependencies...${NC}"
cd "$BACKEND_DIR"

# Create venv and install deps with uv
if [ ! -d ".venv" ]; then
    echo -e "${YELLOW}📥 Creating Python virtual environment...${NC}"
    uv venv
fi

echo -e "${YELLOW}📥 Installing Python packages...${NC}"
uv pip install -e .

# Check for .env file
if [ ! -f ".env" ]; then
    echo -e "${YELLOW}⚠️  No .env file found in backend directory${NC}"
    echo -e "${YELLOW}   Create one with your API keys:${NC}"
    echo -e "   GROK_API_KEY=your_key_here"
    echo -e "   X_BEARER_TOKEN=your_token_here"
fi

echo -e "${GREEN}✓ Python dependencies installed${NC}"
echo ""

# ============================================================================
# Step 3: Install JavaScript dependencies
# ============================================================================
echo -e "${BLUE}[3/5] Installing JavaScript dependencies...${NC}"
cd "$EXTENSION_DIR"

echo -e "${YELLOW}📥 Installing npm packages with bun...${NC}"
bun install

echo -e "${GREEN}✓ JavaScript dependencies installed${NC}"
echo ""

# ============================================================================
# Step 4: Build or run based on mode
# ============================================================================
if [ "$DEV_MODE" = true ]; then
    # ========================================================================
    # DEV MODE: Run both services in tmux split
    # ========================================================================
    echo -e "${BLUE}[4/5] Starting development servers in tmux...${NC}"
    
    SESSION_NAME="polymarket-insights-dev"
    
    # Kill existing session if it exists
    tmux kill-session -t "$SESSION_NAME" 2>/dev/null || true
    
    # Create new tmux session with backend
    tmux new-session -d -s "$SESSION_NAME" -n "servers" -c "$BACKEND_DIR"
    
    # Start backend in left pane
    tmux send-keys -t "$SESSION_NAME" "cd $BACKEND_DIR && source .venv/bin/activate && echo '🐍 Starting Backend...' && uv run python prediction_server.py" Enter
    
    # Split horizontally and start frontend in right pane
    tmux split-window -h -t "$SESSION_NAME" -c "$EXTENSION_DIR"
    tmux send-keys -t "$SESSION_NAME" "cd $EXTENSION_DIR && echo '⚛️  Starting Frontend Dev Server...' && bun run dev" Enter
    
    # Select left pane
    tmux select-pane -t "$SESSION_NAME:0.0"
    
    echo ""
    echo -e "${GREEN}╔══════════════════════════════════════════════════════════════╗${NC}"
    echo -e "${GREEN}║                    🎉 Development Ready!                     ║${NC}"
    echo -e "${GREEN}╚══════════════════════════════════════════════════════════════╝${NC}"
    echo ""
    echo -e "${BLUE}Services running in tmux session: ${YELLOW}$SESSION_NAME${NC}"
    echo -e "  • Backend:   ${GREEN}http://localhost:8000${NC}"
    echo -e "  • Extension: ${GREEN}Hot-reloading enabled${NC}"
    echo ""
    echo -e "${YELLOW}Commands:${NC}"
    echo -e "  • Attach to session:  ${BLUE}tmux attach -t $SESSION_NAME${NC}"
    echo -e "  • Switch panes:       ${BLUE}Ctrl+B then arrow keys${NC}"
    echo -e "  • Detach:             ${BLUE}Ctrl+B then D${NC}"
    echo -e "  • Kill session:       ${BLUE}tmux kill-session -t $SESSION_NAME${NC}"
    echo ""
    echo -e "${YELLOW}Chrome Extension:${NC}"
    echo -e "  1. Open ${BLUE}chrome://extensions${NC}"
    echo -e "  2. Enable 'Developer mode'"
    echo -e "  3. Click 'Load unpacked' → select ${BLUE}$EXTENSION_DIR/dist/chrome${NC}"
    echo ""
    
    # Attach to session
    tmux attach -t "$SESSION_NAME"
    
else
    # ========================================================================
    # PRODUCTION MODE: Build extension and run backend
    # ========================================================================
    echo -e "${BLUE}[4/5] Building Chrome extension...${NC}"
    cd "$EXTENSION_DIR"
    bun run build
    echo -e "${GREEN}✓ Chrome extension built${NC}"
    echo -e "  Output: $EXTENSION_DIR/dist/chrome"
    echo ""
    
    echo -e "${BLUE}[5/5] Starting backend server...${NC}"
    cd "$BACKEND_DIR"
    
    echo ""
    echo -e "${GREEN}╔══════════════════════════════════════════════════════════════╗${NC}"
    echo -e "${GREEN}║                    🎉 Production Ready!                      ║${NC}"
    echo -e "${GREEN}╚══════════════════════════════════════════════════════════════╝${NC}"
    echo ""
    echo -e "${YELLOW}Chrome Extension:${NC}"
    echo -e "  1. Open ${BLUE}chrome://extensions${NC}"
    echo -e "  2. Enable 'Developer mode'"
    echo -e "  3. Click 'Load unpacked' → select ${BLUE}$EXTENSION_DIR/dist/chrome${NC}"
    echo ""
    echo -e "${YELLOW}Starting backend server...${NC}"
    echo ""
    
    # Run backend server
    source .venv/bin/activate
    uv run python prediction_server.py
fi

