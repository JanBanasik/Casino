# Architektura MVP backendu

Ten dokument uzupełnia [README.md](../README.md) o widok wdrożeniowy i modułowy backendu FastAPI (stan na MVP).

## C4 — kontenery (MVP)

```mermaid
flowchart LR
    client[FutureClient]
    api[FastAPI_API]
    pg[(PostgreSQL)]
    redis[(Redis)]
    client -->|"HTTP_REST"| api
    client -->|"WebSocket"| api
    api --> pg
    api --> redis
```

- **PostgreSQL**: użytkownicy, portfele, transakcje, sesje gier, rundy (w tym `ai_actions` jako JSON).
- **Redis**: gorący stan stołu pod kluczem `table:{table_id}:state` (TTL z konfiguracji).
- **REST**: `/api/health`, `/api/auth/*`, `/api/wallet/*`, `/api/sessions/*`.
- **WebSocket**: `/ws/tables/{table_id}?token=...` — wiadomości JSON (`new_round`, `action`).

## Moduły backendu

```mermaid
flowchart TB
    apiLayer[api]
    servicesLayer[services]
    engineLayer[engine]
    dbLayer[db]
    schemasLayer[schemas]
    mlLayer[ml_inference]
    apiLayer --> servicesLayer
    servicesLayer --> engineLayer
    servicesLayer --> dbLayer
    servicesLayer --> redisState[Redis_via_schemas]
    servicesLayer --> mlLayer
    schemasLayer --> engineLayer
```

- **engine**: czysta logika Blackjacka (bez FastAPI).
- **services**: `WalletService`, `GameRoundService`, `RetentionService` (3 przegrane z rzędu → bonus).
- **ml_inference**: interfejs polityk bota; MVP — heurystyka krupiera w silniku + placeholder pod RL.
- **schemas**: `RedisTableState` — walidacja stanu zapisywanego w Redis.

## Sekwencja — nowa runda przez WebSocket

```mermaid
sequenceDiagram
    participant C as Client
    participant WS as FastAPI_WS
    participant S as GameRoundService
    participant PG as PostgreSQL
    participant R as Redis

    C->>WS: new_round session_id bet
    WS->>S: new_round
    S->>PG: verify session wallet bet txn
    S->>S: engine new_round_state
    alt instant_finish
        S->>PG: round win payout retention
        S-->>C: state payload
    else continue_hand
        S->>R: SET table state TTL
        S->>PG: COMMIT bet
        S-->>C: state payload
    end
```

## Uwagi bezpieczeństwa (MVP)

- Token JWT w query WebSocketa jest wygodny na etapie prototypu; w produkcji rozważ krótkotrwałe tokeny stołu lub pierwszą wiadomość połączenia zamiast logowania tokenem w URL (ryzyko wycieku przez Referrer / logi proxy).

## Porty developerskie (docker-compose)

Domyślnie Postgres nasłuchuje na hoście na porcie **15432**, Redis na **16379**, żeby uniknąć kolizji z lokalnymi usługami na 5432/6379.
