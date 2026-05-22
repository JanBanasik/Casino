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
  const res = await fetch(path, { ...options, headers });
  if (!res.ok) {
    const body = await res.json().catch(() => ({}));
    throw new Error(body.detail ?? `Request failed (${res.status})`);
  }
  return res.json() as Promise<T>;
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
