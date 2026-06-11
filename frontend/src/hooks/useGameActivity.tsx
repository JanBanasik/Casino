import {
  createContext,
  useContext,
  useEffect,
  useMemo,
  useState,
  type ReactNode,
} from "react";

interface GameActivityValue {
  /** True only while a round/hand/spin is actively in progress. */
  roundActive: boolean;
  setRoundActive: (active: boolean) => void;
}

const GameActivityContext = createContext<GameActivityValue | null>(null);

export function GameActivityProvider({ children }: { children: ReactNode }) {
  const [roundActive, setRoundActive] = useState(false);
  const value = useMemo(() => ({ roundActive, setRoundActive }), [roundActive]);
  return (
    <GameActivityContext.Provider value={value}>
      {children}
    </GameActivityContext.Provider>
  );
}

const NOOP = () => {};

export function useGameActivity(): GameActivityValue {
  return useContext(GameActivityContext) ?? { roundActive: false, setRoundActive: NOOP };
}

/** Mirror a page's "round in progress" flag into the shared context; reset on unmount. */
export function useReportRoundActivity(active: boolean) {
  const { setRoundActive } = useGameActivity();
  useEffect(() => {
    setRoundActive(active);
  }, [active, setRoundActive]);
  useEffect(() => () => setRoundActive(false), [setRoundActive]);
}
