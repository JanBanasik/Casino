# Następne kroki (po MVP backendu)

Ten dokument to backlog zespołowy: co warto zrobić po obecnym stanie repozytorium (FastAPI, PostgreSQL, Redis, Blackjack WS, podstawowy retention). Powiązanie z architekturą MVP: [backend-mvp-architecture.md](backend-mvp-architecture.md).

## Priorytet P0 — domknięcie pionu „działa end-to-end”

1. **Frontend (React + TypeScript + Vite)** — zgodnie z [README.md](../README.md)
   - Logowanie / rejestracja → zapis tokenu (np. `localStorage` na MVP).
   - Ekran portfela: `GET /api/wallet/me`, `POST /api/wallet/deposit`.
   - Utworzenie sesji: `POST /api/sessions`.
   - Stół: WebSocket `ws://<host>/ws/tables/{table_id}?token=<JWT>` z komunikatami:
     - `{"type":"new_round","session_id":"<uuid>","bet":10}`
     - `{"type":"action","action":"HIT"|"STAND"}`
   - Obsługa `payload.retention` (bonus po 3 przegranych) w UI.
2. **README — sekcja „Uruchomienie”** — `docker compose`, `make install` / `make migrate` / `make dev`, porty **15432** (Postgres) i **16379** (Redis), przykładowy flow curl lub link do `docs/`.

## Priorytet P1 — jakość i zaufanie do zmian

3. **CI (np. GitHub Actions)** — job: `make lint`, `make test`; opcjonalnie migracja Alembic na serwisach `postgres` + `redis` w tle.
4. **Testy API** — `httpx.AsyncClient` + pełny `app` z lifespanem; marker `@pytest.mark.integration` dla testów wymagających żywego Dockera (reszta bez sieci).
5. **Sekrety i konfiguracja** — `JWT_SECRET_KEY` tylko z zmiennych środowiskowych w środowiskach innych niż dev; plik `.env` nie commitowany (wzór w `backend/.env.example`).

## Priorytet P2 — produkt gry i UX

6. **Blackjack — reguły rozszerzone** (według potrzeb dydaktycznych): double, split, insurance; spójna semantyka wypłat w API i komunikatach WS.
7. **Stół wieloosobowy / pokoje** — jeśli wychodzicie poza „jeden gracz na `table_id`”: autoryzacja pokoju, broadcast do wielu połączeń, ewentualnie Redis Pub/Sub.
8. **OpenAPI / typy** — generacja klienta TS z `openapi.json` albo utrzymanie ręcznych typów zsynchronizowanych z Pydantic.

## Priorytet P3 — RL i kolejne gry

9. **Integracja modeli RL** — podmiana stubu w `ml_inference` na wytrenowany agent (Q-table / eksport z `rl_training`); konfiguracja trudności per stół.
10. **Poker** — silnik w `engine/`, osobny przepływ WS lub wspólny protokół wiadomości z polem `game`.

## Priorytet P4 — produkcja (później)

11. **Bezpieczeństwo WS** — krótkotrwałe tokeny stołu zamiast długiego JWT w query (mniejsze ryzyko wycieku w logach / Referrer).
12. **Observability** — structured logging, metryki, health zależności (DB/Redis).
13. **Wdrożenie** — Dockerfile backendu, orchestracja, backup Postgres.

---

## Sugerowany podział na sprinty (2 tygodnie)

| Sprint | Cel |
|--------|-----|
| 1 | Frontend: auth + portfel + sesja + jeden ekran stołu z WS |
| 2 | CI + testy API/integration + README uruchomienia |
| 3 | Ulepszenia blackjacka lub start pokojów wieloosobowych |
| 4 | RL / druga gra — według zakresu projektu |

Ostatnia aktualizacja: 2026-04-23.
