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
  has_split?: boolean;
  hands?: string[][];
  hand_bets?: number[];
  active_hand_index?: number;
  hand_results?: (string | null)[];
}

export interface LobbySeatPayload {
  seat_index: number;
  display_name: string;
  avatar_key: string;
  is_human: boolean;
}

export interface TableStatePayload {
  table_phase?: string;
  phase: string;
  player_hand: string[];
  player_hands?: string[][] | null;
  active_hand_index?: number | null;
  dealer_hand: string[];
  dealer_hidden_count: number;
  bet: number;
  message?: string | null;
  active_seat_index?: number | null;
  human_seat_index?: number;
  my_seat_index?: number | null;
  round_in_progress?: boolean;
  waiting_for_round?: boolean;
  lobby_seats?: (LobbySeatPayload | null)[];
  seats?: SeatStatePayload[];
  retention?: BonusPayload;
}

export type Difficulty = "easy" | "medium" | "hard";

export interface BonusPayload {
  loss_refund?: boolean;
  loss_refund_amount?: number;
  rescue?: boolean;
  rescue_amount?: number;
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

export interface PokerSeatPayload {
  seat_index: number;
  display_name: string;
  avatar_key: string;
  is_human: boolean;
  hole_cards: string[];  // ["??", "??"] if hidden
  chips: number;
  bet_phase: number;
  bet_total: number;
  status: "active" | "folded" | "all_in" | "finished" | "empty";
  result: string | null;
  payout: number;
}

export interface PokerStatePayload {
  table_phase: string;
  phase: "waiting" | "pre_flop" | "flop" | "turn" | "river" | "showdown" | "finished";
  community_cards: string[];
  hole_cards: string[];
  pot: number;
  current_bet: number;
  min_raise: number;
  active_seat_index: number | null;
  dealer_seat_index: number;
  human_seat_index: number | null;
  small_blind: number;
  big_blind: number;
  message: string | null;
  seats: PokerSeatPayload[];
  lobby_seats?: (LobbySeatPayload | null)[];
  my_seat_index?: number | null;
  round_in_progress?: boolean;
  waiting_for_round?: boolean;
}

export interface RoulettePayoutItem {
  bet_type: string;
  amount: number;
  payout: number;
  won: boolean;
}

export interface RouletteSpinResult {
  result: number;
  color: "red" | "black" | "green";
  payouts: RoulettePayoutItem[];
  total_payout: number;
  net: number;
  new_balance: number;
  bonus?: BonusPayload | null;
}

export interface DailyStatusResponse {
  available: boolean;
  streak: number;
  next_amount: number;
  next_available_at: string | null;
}

export interface BonusGrantResponse {
  granted: boolean;
  amount: number;
  balance: number;
  message?: string | null;
  streak?: number | null;
}

export interface RoundHistoryItem {
  id: string;
  game_type: string;
  result: string;
  bet_amount: number;
  payout_amount: number;
  net: number;
  created_at: string;
}

export interface RoundHistoryResponse {
  rounds: RoundHistoryItem[];
}

export interface NotificationItem {
  id: string;
  kind: string;
  title: string;
  body: string;
  amount: number;
  created_at: string;
}

export interface NotificationListResponse {
  notifications: NotificationItem[];
}

export interface GameConfigResponse {
  win_multiplier_easy: number;
  win_multiplier_medium: number;
  win_multiplier_hard: number;
}

export interface PaymentConfigResponse {
  stripe_enabled: boolean;
  publishable_key: string;
  currency: string;
  chips_per_currency_unit: number;
  withdraw_min_chips: number;
}

export interface CheckoutResponse {
  url: string | null;
  simulated: boolean;
  balance: number | null;
  amount_minor: number;
  currency: string;
}

export interface WithdrawResponse {
  chips: number;
  amount_minor: number;
  currency: string;
  status: string;
  balance: number;
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
