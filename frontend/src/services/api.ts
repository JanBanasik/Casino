import type {
  BonusGrantResponse,
  CheckoutResponse,
  DailyStatusResponse,
  GameConfigResponse,
  NotificationListResponse,
  PaymentConfigResponse,
  RoundHistoryResponse,
  SessionResponse,
  TokenResponse,
  WalletResponse,
  WithdrawResponse,
  WsTicketResponse,
} from "../types/api";

const TOKEN_KEY = "casino_token";

export function getToken(): string | null {
  return localStorage.getItem(TOKEN_KEY);
}

export function setToken(token: string): void {
  localStorage.setItem(TOKEN_KEY, token);
}

export function clearToken(): void {
  localStorage.removeItem(TOKEN_KEY);
}

async function apiFetch<T>(
  path: string,
  options: RequestInit = {},
  auth = false,
): Promise<T> {
  const headers = new Headers(options.headers);
  headers.set("Content-Type", "application/json");
  if (auth) {
    const token = getToken();
    if (!token) throw new Error("Not authenticated");
    headers.set("Authorization", `Bearer ${token}`);
  }

  let lastRes: Response | undefined;
  for (let attempt = 0; attempt < 2; attempt++) {
    const controller = new AbortController();
    const timer = setTimeout(() => controller.abort(), 8000);
    try {
      const res = await fetch(path, { ...options, headers, signal: controller.signal });
      lastRes = res;
      if (res.status < 500) {
        if (!res.ok) {
          const body = await res.json().catch(() => ({}));
          throw new Error(body.detail ?? `Request failed (${res.status})`);
        }
        return res.json() as Promise<T>;
      }
      // 5xx — retry once
    } catch (e) {
      if (attempt === 1) throw e;
      if (e instanceof Error && e.name !== "AbortError") throw e;
    } finally {
      clearTimeout(timer);
    }
  }

  // Both attempts returned 5xx
  const body = await lastRes!.json().catch(() => ({}));
  throw new Error(body.detail ?? `Request failed (${lastRes!.status})`);
}

export function register(username: string, email: string, password: string) {
  return apiFetch<TokenResponse>("/api/auth/register", {
    method: "POST",
    body: JSON.stringify({ username, email, password }),
  });
}

export function login(username: string, password: string) {
  return apiFetch<TokenResponse>("/api/auth/login", {
    method: "POST",
    body: JSON.stringify({ username, password }),
  });
}

export function getWallet() {
  return apiFetch<WalletResponse>("/api/wallet/me", {}, true);
}

export function getDailyStatus() {
  return apiFetch<DailyStatusResponse>("/api/wallet/daily", {}, true);
}

export function claimDaily() {
  return apiFetch<BonusGrantResponse>("/api/wallet/daily/claim", {
    method: "POST",
  }, true);
}

export function claimRescue() {
  return apiFetch<BonusGrantResponse>("/api/wallet/rescue", {
    method: "POST",
  }, true);
}

export function getHistory(limit = 25) {
  return apiFetch<RoundHistoryResponse>(`/api/sessions/history?limit=${limit}`, {}, true);
}

export function getNotifications() {
  return apiFetch<NotificationListResponse>("/api/notifications", {}, true);
}

export function ackNotification(id: string) {
  return apiFetch<{ acknowledged: boolean }>(`/api/notifications/${id}/ack`, {
    method: "POST",
  }, true);
}

export function getPaymentConfig() {
  return apiFetch<PaymentConfigResponse>("/api/payments/config", {}, true);
}

// Public, rarely-changing display config — fetched once and cached.
let _gameConfig: Promise<GameConfigResponse> | null = null;
export function getGameConfig() {
  if (!_gameConfig) {
    _gameConfig = apiFetch<GameConfigResponse>("/api/config/game").catch((e) => {
      _gameConfig = null; // allow retry on failure
      throw e;
    });
  }
  return _gameConfig;
}

export function buyChips(chips: number) {
  return apiFetch<CheckoutResponse>("/api/payments/checkout", {
    method: "POST",
    body: JSON.stringify({ chips }),
  }, true);
}

export function withdrawChips(chips: number, accountNumber: string) {
  return apiFetch<WithdrawResponse>("/api/payments/withdraw", {
    method: "POST",
    body: JSON.stringify({ chips, account_number: accountNumber }),
  }, true);
}

export function createSession(gameType = "blackjack") {
  return apiFetch<SessionResponse>("/api/sessions", {
    method: "POST",
    body: JSON.stringify({ game_type: gameType }),
  }, true);
}

export function mintWsTicket(sessionId: string, tableId = "default") {
  return apiFetch<WsTicketResponse>(`/api/sessions/${sessionId}/ws-ticket`, {
    method: "POST",
    body: JSON.stringify({ table_id: tableId }),
  }, true);
}

export function wsBaseUrl(): string {
  const proto = window.location.protocol === "https:" ? "wss:" : "ws:";
  return `${proto}//${window.location.host}`;
}

export function createPokerSession() {
  return apiFetch<SessionResponse>("/api/sessions", {
    method: "POST",
    body: JSON.stringify({ game_type: "poker" }),
  }, true);
}

export function createRouletteSession() {
  return apiFetch<SessionResponse>("/api/sessions", {
    method: "POST",
    body: JSON.stringify({ game_type: "roulette" }),
  }, true);
}

export interface RouletteBetRequest {
  bet_type: string;
  amount: number;
  number?: number;
  numbers?: number[];
  choice?: string;
}

export function rouletteSpin(session_id: string, bets: RouletteBetRequest[]) {
  return apiFetch<import('../types/api').RouletteSpinResult>("/api/roulette/spin", {
    method: "POST",
    body: JSON.stringify({ session_id, bets }),
  }, true);
}
