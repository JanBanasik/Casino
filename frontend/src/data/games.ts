export interface GameInfo {
  id: string;
  name: string;
  category: "live" | "cards" | "coming";
  description: string;
  minBet: number;
  playersOnline: number;
  imageGradient: string;
  available: boolean;
  route?: string;
}

export const GAMES: GameInfo[] = [
  {
    id: "blackjack",
    name: "Blackjack",
    category: "live",
    description: "Klasyczny blackjack z krupierem na żywo — graj solo lub przy pełnym stole.",
    minBet: 10,
    playersOnline: 128,
    imageGradient: "linear-gradient(135deg, #0d4a2e 0%, #1a6b45 50%, #0a2818 100%)",
    available: true,
    route: "/stoły",
  },
  {
    id: "blackjack-vip",
    name: "Blackjack VIP",
    category: "live",
    description: "Salon wysokich stawek z doświadczonym krupierem.",
    minBet: 50,
    playersOnline: 34,
    imageGradient: "linear-gradient(135deg, #3d2e0a 0%, #6b5a1a 50%, #2a2008 100%)",
    available: true,
    route: "/stoły",
  },
  {
    id: "poker",
    name: "Texas Hold'em",
    category: "cards",
    description: "Poker wieloosobowy — wkrótce.",
    minBet: 20,
    playersOnline: 0,
    imageGradient: "linear-gradient(135deg, #1a1a3e 0%, #2d2d6b 50%, #12122a 100%)",
    available: false,
  },
  {
    id: "roulette",
    name: "Ruletka",
    category: "coming",
    description: "Europejska ruletka na żywo — wkrótce.",
    minBet: 5,
    playersOnline: 0,
    imageGradient: "linear-gradient(135deg, #3e0a0a 0%, #6b1a1a 50%, #2a0808 100%)",
    available: false,
  },
];

export interface LiveTable {
  id: string;
  name: string;
  game: "blackjack";
  minBet: number;
  maxBet: number;
  seatsTotal: number;
  seatsTaken: number;
  dealerName: string;
  dealerLevel: "standard" | "hard" | "vip";
  featured?: boolean;
}

export const LIVE_TABLES: LiveTable[] = [
  {
    id: "table-emerald",
    name: "Stół Szmaragd",
    game: "blackjack",
    minBet: 10,
    maxBet: 500,
    seatsTotal: 7,
    seatsTaken: 4,
    dealerName: "Krupier Marek",
    dealerLevel: "standard",
    featured: true,
  },
  {
    id: "table-gold",
    name: "Stół Złoty",
    game: "blackjack",
    minBet: 25,
    maxBet: 2000,
    seatsTotal: 7,
    seatsTaken: 6,
    dealerName: "Krupier Anna",
    dealerLevel: "hard",
    featured: true,
  },
  {
    id: "table-vip",
    name: "Salon VIP",
    game: "blackjack",
    minBet: 100,
    maxBet: 10000,
    seatsTotal: 5,
    seatsTaken: 2,
    dealerName: "Krupier Tomasz",
    dealerLevel: "vip",
  },
  {
    id: "table-classic",
    name: "Stół Klasyczny",
    game: "blackjack",
    minBet: 5,
    maxBet: 200,
    seatsTotal: 7,
    seatsTaken: 5,
    dealerName: "Krupier Kasia",
    dealerLevel: "standard",
  },
  {
    id: "default",
    name: "Stół Startowy",
    game: "blackjack",
    minBet: 10,
    maxBet: 1000,
    seatsTotal: 7,
    seatsTaken: 3,
    dealerName: "Krupier Piotr",
    dealerLevel: "standard",
  },
];

export const PLAYER_NAMES = [
  "Alex_K",
  "Marta99",
  "JanekW",
  "Ola_P",
  "Kris77",
  "Ewa_M",
];

export const AVATAR_COLORS = [
  "#c41e3a",
  "#1a6b4a",
  "#2563eb",
  "#9a7b1a",
  "#7c3aed",
  "#0891b2",
];

export function avatarColor(key: string): string {
  let hash = 0;
  for (let i = 0; i < key.length; i++) hash = key.charCodeAt(i) + ((hash << 5) - hash);
  return AVATAR_COLORS[Math.abs(hash) % AVATAR_COLORS.length];
}

/** Seat positions on ellipse: 7 slots, index 3 = bottom center (human) */
export const SEAT_COUNT = 7;
export const HUMAN_SEAT_SLOT = 3;

export function seatPosition(index: number): { x: number; y: number; rotate: number } {
  const count = SEAT_COUNT;
  const angle = (index / count) * 360 - 90;
  const rad = (angle * Math.PI) / 180;
  const rx = 42;
  const ry = 38;
  return {
    x: 50 + rx * Math.cos(rad),
    y: 50 + ry * Math.sin(rad),
    rotate: angle + 90,
  };
}
