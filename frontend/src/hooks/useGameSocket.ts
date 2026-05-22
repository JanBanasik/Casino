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
) {
  const wsRef = useRef<WebSocket | null>(null);
  const [status, setStatus] = useState<ConnectionStatus>("idle");
  const [tableState, setTableState] = useState<TableStatePayload | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [retentionAlert, setRetentionAlert] = useState<string | null>(null);
  const [lastSeatAction, setLastSeatAction] = useState<WsSeatActionMessage["payload"] | null>(null);

  const disconnect = useCallback(() => {
    wsRef.current?.close();
    wsRef.current = null;
    setStatus("idle");
  }, []);

  const connect = useCallback(async () => {
    if (!sessionId) return;
    disconnect();
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
          | { error: string };

        if ("type" in data && data.type === "auth_ok") {
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
          setLastSeatAction(data.payload);
          return;
        }
        if ("type" in data && data.type === "state") {
          setTableState(data.payload);
          if (data.payload.retention?.bad_beat_bonus) {
            setRetentionAlert(
              `Szczęście się odwraca! +${data.payload.retention.amount} żetonów`,
            );
          }
          return;
        }
        if ("error" in data) {
          setError(data.error);
        }
      };

      ws.onerror = () => {
        setError("Nie udało się połączyć ze stołem");
        setStatus("error");
      };

      ws.onclose = () => {
        setStatus((s) => (s === "error" ? s : "idle"));
      };
    } catch (e) {
      setError(e instanceof Error ? e.message : "Połączenie nie powiodło się");
      setStatus("error");
    }
  }, [sessionId, tableId, disconnect]);

  useEffect(() => () => disconnect(), [disconnect]);

  const newRound = useCallback(
    (bet: number) => {
      if (!sessionId || !wsRef.current || wsRef.current.readyState !== WebSocket.OPEN) return;
      wsRef.current.send(
        JSON.stringify({
          type: "new_round",
          session_id: sessionId,
          bet,
          solo,
          bot_count: solo ? 0 : botCount,
        }),
      );
    },
    [sessionId, solo, botCount],
  );

  const hit = useCallback(() => {
    wsRef.current?.send(JSON.stringify({ type: "action", action: "HIT" }));
  }, []);

  const stand = useCallback(() => {
    wsRef.current?.send(JSON.stringify({ type: "action", action: "STAND" }));
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
    newRound,
    hit,
    stand,
  };
}
