#!/usr/bin/env bash
# start-dev.sh — uruchamia cały stack developerski jedną komendą
set -e

CYAN='\033[0;36m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

# Katalog projektu — zawsze relatywnie do tego skryptu
ROOT_DIR="$(cd "$(dirname "$0")" && pwd)"

echo -e "${CYAN}🎰  Kasyno — dev stack${NC}"
echo "────────────────────────────────"

# 1. Baza danych + Redis
echo -e "${YELLOW}▶ Uruchamianie Postgres + Redis...${NC}"
docker compose -f "$ROOT_DIR/docker-compose.yml" up -d postgres redis

# Czekaj aż postgres będzie gotowy
echo -n "  Czekam na Postgres"
for i in $(seq 1 20); do
    if docker compose -f "$ROOT_DIR/docker-compose.yml" exec -T postgres pg_isready -U casino -d casino &>/dev/null; then
        echo -e " ${GREEN}✓${NC}"
        break
    fi
    echo -n "."
    sleep 1
done

# 2. Migracje
echo -e "${YELLOW}▶ Migracje bazy danych...${NC}"
(cd "$ROOT_DIR/backend" && uv run alembic upgrade head 2>&1 | tail -5)
echo -e "  ${GREEN}✓ Migracje zastosowane${NC}"

# Pułapka na Ctrl+C — zatrzymuje oba procesy
cleanup() {
    echo ""
    echo -e "${YELLOW}🛑 Zatrzymuję serwery...${NC}"
    [[ -n "$BACKEND_PID" ]] && kill "$BACKEND_PID" 2>/dev/null || true
    [[ -n "$FRONTEND_PID" ]] && kill "$FRONTEND_PID" 2>/dev/null || true
    wait 2>/dev/null || true
    echo -e "${GREEN}✅ Zatrzymano.${NC}"
    exit 0
}
trap cleanup INT TERM

# 3. Backend (subshell w tle — zmiana katalogu nie dotyka rodzica)
echo -e "${YELLOW}▶ Uruchamianie backendu (port 8000)...${NC}"
(cd "$ROOT_DIR/backend" && uv run uvicorn app.main:app --reload --host 0.0.0.0 --port 8000) &
BACKEND_PID=$!

# Krótka chwila żeby backend zdążył zaraportować błędy przy starcie
sleep 2
if ! kill -0 "$BACKEND_PID" 2>/dev/null; then
    echo -e "${RED}❌ Backend nie wystartował — sprawdź błędy wyżej.${NC}"
    exit 1
fi
echo -e "  ${GREEN}✓ Backend działa (PID $BACKEND_PID)${NC}"

# 4. Frontend (subshell w tle)
echo -e "${YELLOW}▶ Uruchamianie frontendu (port 5173)...${NC}"
(cd "$ROOT_DIR/frontend" && npm run dev) &
FRONTEND_PID=$!

sleep 2
if ! kill -0 "$FRONTEND_PID" 2>/dev/null; then
    echo -e "${RED}❌ Frontend nie wystartował — sprawdź błędy wyżej.${NC}"
    kill "$BACKEND_PID" 2>/dev/null || true
    exit 1
fi
echo -e "  ${GREEN}✓ Frontend działa (PID $FRONTEND_PID)${NC}"

echo ""
echo -e "${GREEN}════════════════════════════════${NC}"
echo -e "${GREEN}  ✅ Wszystko działa!${NC}"
echo -e "${GREEN}════════════════════════════════${NC}"
echo -e "  🖥  Frontend:  ${CYAN}http://localhost:5173${NC}"
echo -e "  🔧  Backend:   ${CYAN}http://localhost:8000${NC}"
echo -e "  📄  API docs:  ${CYAN}http://localhost:8000/docs${NC}"
echo ""
echo -e "  Naciśnij ${YELLOW}Ctrl+C${NC} aby zatrzymać wszystko."
echo ""

# Czekaj aż oba procesy skończą (lub Ctrl+C)
wait "$BACKEND_PID" "$FRONTEND_PID"
