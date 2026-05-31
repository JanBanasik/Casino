import type {
  SessionResponse,
  TokenResponse,
  WalletResponse,
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

export function deposit(amount: number) {
  return apiFetch<WalletResponse>("/api/wallet/deposit", {
    method: "POST",
    body: JSON.stringify({ amount }),
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
