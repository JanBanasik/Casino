export interface SeatStatePayload {
  seat_index: number;
  display_name: string;
  avatar_key: string;
  is_human: boolean;
  hand: string[];
  bet: number;
  status: string;
  result?: string | null;
  payout?: number;
}

export interface TableStatePayload {
  phase: string;
  player_hand: string[];
  dealer_hand: string[];
  dealer_hidden_count: number;
  bet: number;
  message?: string | null;
  active_seat_index?: number | null;
  human_seat_index?: number;
  seats?: SeatStatePayload[];
  retention?: {
    bad_beat_bonus?: boolean;
    amount?: number;
  };
}

export interface WsStateMessage {
  type: "state";
  payload: TableStatePayload;
}

export interface WsSeatActionMessage {
  type: "seat_action";
  payload: {
    seat_index: number;
    action: string;
    display_name: string;
  };
}

export interface WsAuthOk {
  type: "auth_ok";
}

export interface WsAuthError {
  type: "auth_error";
  error: string;
}

export interface WsErrorMessage {
  error: string;
}

export interface TokenResponse {
  access_token: string;
  token_type: string;
}

export interface WalletResponse {
  balance: number;
  retention_level: number;
}

export interface SessionResponse {
  id: string;
  game_type: string;
  started_at: string;
}

export interface WsTicketResponse {
  ticket: string;
  table_id: string;
  expires_in: number;
}
