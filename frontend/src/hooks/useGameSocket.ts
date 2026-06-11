import { useCallback, useEffect, useRef, useState } from "react";
import { mintWsTicket, wsBaseUrl } from "../services/api";
import type {
  TableStatePayload,
  WsAuthError,
  WsAuthOk,
  WsSeatActionMessage,
  WsStateMessage,
} from "../types/api";

type ConnectionStatus = "idle" | "connecting" | "connected" | "error";

export function useGameSocket(
  sessionId: string | null,
  tableId = "default",
  solo = false,
  botCount = 0,
  difficulty = "medium",
  minBet = 0,
) {
  const wsRef = useRef<WebSocket | null>(null);
  const [status, setStatus] = useState<ConnectionStatus>("idle");
  const [tableState, setTableState] = useState<TableStatePayload | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [retentionAlert, setRetentionAlert] = useState<string | null>(null);
  const [lastSeatAction, setLastSeatAction] = useState<WsSeatActionMessage["payload"] | null>(null);
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
      const ws = new WebSocket(`${wsBaseUrl()}/ws/tables/${table_id}`);
      wsRef.current = ws;

      ws.onopen = () => {
        ws.send(JSON.stringify({ type: "auth", ticket }));
      };

      ws.onmessage = (event) => {
        const data = JSON.parse(event.data) as
          | WsAuthOk
          | WsAuthError
          | WsStateMessage
          | WsSeatActionMessage
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
        if ("type" in data && data.type === "seat_action") {
          setLastSeatAction((data as WsSeatActionMessage).payload);
          return;
        }
        if ("type" in data && data.type === "state") {
          const payload = (data as WsStateMessage).payload;
          setTableState(payload);
          const r = payload.retention;
          if (r?.loss_refund) {
            setRetentionAlert(
              `Zwrot za pechową serię: +${Math.round(r.loss_refund_amount ?? 0)} Ż`,
            );
          } else if (r?.rescue) {
            setRetentionAlert(
              `Koło ratunkowe — doładowano +${Math.round(r.rescue_amount ?? 0)} Ż`,
            );
          }
          return;
        }
        if ("error" in data) {
          setError((data as { error: string }).error);
        }
      };

      ws.onerror = () => {
        setError("Nie udało się połączyć ze stołem");
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

  const placeBet = useCallback(
    (bet: number) => {
      if (!sessionId || !wsRef.current || wsRef.current.readyState !== WebSocket.OPEN) return;
      setError(null);
      wsRef.current.send(
        JSON.stringify({
          type: "place_bet",
          session_id: sessionId,
          bet,
          solo,
          bot_count: solo ? 0 : botCount,
          difficulty,
          min_bet: minBet,
        }),
      );
    },
    [sessionId, solo, botCount, difficulty, minBet],
  );

  const hit = useCallback(() => {
    wsRef.current?.send(JSON.stringify({ type: "action", action: "HIT" }));
  }, []);

  const stand = useCallback(() => {
    wsRef.current?.send(JSON.stringify({ type: "action", action: "STAND" }));
  }, []);

  const double = useCallback(() => {
    wsRef.current?.send(JSON.stringify({ type: "action", action: "DOUBLE" }));
  }, []);

  const split = useCallback(() => {
    wsRef.current?.send(JSON.stringify({ type: "action", action: "SPLIT" }));
  }, []);

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
    tableState,
    error,
    retentionAlert,
    lastSeatAction,
    clearRetentionAlert: () => setRetentionAlert(null),
    connect,
    disconnect,
    sit,
    placeBet,
    hit,
    stand,
    double,
    split,
  };
}
