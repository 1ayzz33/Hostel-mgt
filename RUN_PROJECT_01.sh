#!/usr/bin/env bash
# ==============================================================================
# PROJECT 01 - ONLINE HOSTEL FACILITIES MANAGEMENT REPORTING PLATFORM
# Auto-Run Script (Bash - macOS / Linux)
# Double-click or run: ./RUN_PROJECT_01.sh
# ==============================================================================

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

# --- Colors ---
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
CYAN='\033[0;36m'
NC='\033[0m'

echo ""
echo "================================================" -e
echo "  PROJECT 01 - ONLINE HOSTEL FACILITIES" -e
echo "               REPORTING PLATFORM" -e
echo "================================================" -e
echo ""

# --- Find Python ---
PYTHON_CMD=""
if command -v python3 &>/dev/null; then
    PYTHON_CMD="python3"
elif command -v python &>/dev/null; then
    PYTHON_CMD="python"
else
    echo -e "${RED}[X] Python not found. Install Python 3.10+ from https://python.org${NC}" >&2
    echo -e "${RED}      Enable 'Add Python to PATH' during install.${NC}" >&2
    read -p "Press Enter to exit"
    exit 1
fi
echo -e "${GREEN}[OK] Python: $PYTHON_CMD${NC}"
$PYTHON_CMD --version

# --- Seed database ---
echo -e "${YELLOW}[*] Seeding demo database...${NC}"
$PYTHON_CMD -m hostelhub.seed --reset 2>/dev/null || true
if [ $? -eq 0 ]; then
    echo -e "${GREEN}[OK] Demo database seeded${NC}"
else
    echo -e "${YELLOW}[!] Seed may have failed (continuing anyway)${NC}"
fi

# --- Launch server ---
echo -e "${YELLOW}[*] Starting HostelHub on http://127.0.0.1:8000...${NC}"
$PYTHON_CMD app.py &
SERVER_PID=$!

# Wait for server
sleep 2
if curl -s http://127.0.0.1:8000 >/dev/null 2>&1; then
    echo -e "${GREEN}[OK] HostelHub is ready at http://127.0.0.1:8000${NC}"
    open http://127.0.0.1:8000 2>/dev/null || xdg-open http://127.0.0.1:8000 2>/dev/null || true
else
    echo -e "${YELLOW}[!] Server may still be starting${NC}"
fi

echo ""
echo "================================================" -e
echo "  PROJECT 01 IS RUNNING!" -e
echo "  URL: http://127.0.0.1:8000" -e
echo "================================================" -e
echo ""
echo "  Demo accounts:" -e
echo "    Student : student@hostelhub.edu.ng / Student@123" -e
echo "    Staff   : grace.okafor@hostelhub.edu.ng / Staff@123" -e
echo "    Admin   : admin@hostelhub.edu.ng / Admin@123" -e
echo ""
echo "  Keep this window open. Press Ctrl+C to stop." -e
echo ""

trap 'echo ""; echo "Stopping server..."; kill $SERVER_PID 2>/dev/null; echo "Server stopped."; exit' INT TERM
wait $SERVER_PID