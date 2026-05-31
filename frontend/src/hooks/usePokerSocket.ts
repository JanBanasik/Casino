import { useCallback, useEffect, useRef, useState } from "react";
import { mintWsTicket, wsBaseUrl } from "../services/api";
import type {
  PokerStatePayload,
  WsAuthError,
  WsAuthOk,
} from "../types/api";

type ConnectionStatus = "idle" | "connecting" | "connected" | "error";

interface WsPokerStateMessage {
  type: "state";
  payload: PokerStatePayload;
}

interface WsPokerActionMessage {
  type: "action_result";
  payload: {
    seat_index: number;
    action: string;
    display_name: string;
  };
}

export function usePokerSocket(
  sessionId: string | null,
  tableId = "default",
  botCount = 3,
) {
  const wsRef = useRef<WebSocket | null>(null);
  const [status, setStatus] = useState<ConnectionStatus>("idle");
  const [pokerState, setPokerState] = useState<PokerStatePayload | null>(null);
  const [error, setError] = useState<string | null>(null);
  const reconnectAttemptRef = useRef(0);
  const reconnectTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  const disconnect = useCallback(() => {
    if (reconnectTimerRef.current) {
      clearTimeout(reconnectTimerRef.current);
      reconnectTimerRef.current = null;
    }
    reconnectAttemptRef.current = 0;
    wsRef.current?.close();
    wsRef.current = null;
    setStatus("idle");
  }, []);

  const connect = useCallback(async () => {
    if (!sessionId) return;
    if (reconnectTimerRef.current) {
      clearTimeout(reconnectTimerRef.current);
      reconnectTimerRef.current = null;
    }
    wsRef.current?.close();
    wsRef.current = null;
    setError(null);
    setStatus("connecting");

    try {
      const { ticket, table_id } = await mintWsTicket(sessionId, tableId);
      const ws = new WebSocket(`${wsBaseUrl()}/ws/poker/${table_id}`);
      wsRef.current = ws;

      ws.onopen = () => {
        ws.send(JSON.stringify({ type: "auth", ticket }));
      };

      ws.onmessage = (event) => {
        const data = JSON.parse(event.data) as
          | WsAuthOk
          | WsAuthError
          | WsPokerStateMessage
          | WsPokerActionMessage
          | { type: "ping" }
          | { error: string };

        if ("type" in data && data.type === "ping") {
          ws.send(JSON.stringify({ type: "pong" }));
          return;
        }
        if ("type" in data && data.type === "auth_ok") {
          reconnectAttemptRef.current = 0;
          setStatus("connected");
          return;
        }
        if ("type" in data && data.type === "auth_error") {
          setError("Sesja wygasła — odśwież stół");
          setStatus("error");
          ws.close();
          return;
        }
        if ("type" in data && data.type === "state") {
          setPokerState((data as WsPokerStateMessage).payload);
          return;
        }
        if ("error" in data) {
          setError((data as { error: string }).error);
        }
      };

      ws.onerror = () => {
        setError("Nie udało się połączyć ze stołem pokerowym");
        setStatus("error");
      };

      ws.onclose = () => {
        setStatus((s) => {
          if (s === "error") return s;
          const attempt = reconnectAttemptRef.current++;
          if (attempt >= 5) {
            setError("Utracono połączenie ze stołem");
            return "error";
          }
          const delay = Math.min(1000 * 2 ** attempt, 30_000);
          reconnectTimerRef.current = setTimeout(() => connect(), delay);
          return "connecting";
        });
      };
    } catch (e) {
      setError(e instanceof Error ? e.message : "Połączenie nie powiodło się");
      setStatus("error");
    }
  }, [sessionId, tableId]);

  useEffect(() => () => {
    if (reconnectTimerRef.current) clearTimeout(reconnectTimerRef.current);
    wsRef.current?.close();
  }, []);

  const sit = useCallback(
    (seatIndex: number) => {
      if (!sessionId || !wsRef.current || wsRef.current.readyState !== WebSocket.OPEN) return;
      setError(null);
      wsRef.current.send(
        JSON.stringify({
          type: "sit",
          session_id: sessionId,
          seat_index: seatIndex,
        }),
      );
    },
    [sessionId],
  );

  const startHand = useCallback(
    (buyIn: number, bots: number) => {
      if (!sessionId || !wsRef.current || wsRef.current.readyState !== WebSocket.OPEN) return;
      setError(null);
      wsRef.current.send(
        JSON.stringify({
          type: "start_hand",
          session_id: sessionId,
          buy_in: buyIn,
          bot_count: bots ?? botCount,
        }),
      );
    },
    [sessionId, botCount],
  );

  const action = useCallback(
    (act: string, amount?: number) => {
      if (!wsRef.current || wsRef.current.readyState !== WebSocket.OPEN) return;
      wsRef.current.send(
        JSON.stringify({ type: "action", action: act, amount }),
      );
    },
    [],
  );

  const fold = useCallback(() => action("FOLD"), [action]);
  const check = useCallback(() => action("CHECK"), [action]);
  const call = useCallback(() => action("CALL"), [action]);
  const raise = useCallback((amount: number) => action("RAISE", amount), [action]);

  const statusLabel =
    status === "connected"
      ? "Stół na żywo"
      : status === "connecting"
        ? "Łączenie ze stołem…"
        : status === "error"
          ? "Brak połączenia"
          : "Offline";

  return {
    status,
    statusLabel,
    pokerState,
    error,
    connect,
    disconnect,
    sit,
    startHand,
    fold,
    check,
    call,
    raise,
  };
}
