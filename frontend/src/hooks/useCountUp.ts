import { useEffect, useRef, useState } from "react";

/**
 * Animates a number → `target` over `duration` ms with an ease-out curve.
 * Re-runs whenever `target` or `runKey` changes. By default it counts up from 0
 * (dramatic reveal); pass `fromPrevious` to count from the last settled value
 * instead (e.g. a pot that grows incrementally). Honours prefers-reduced-motion
 * by snapping straight to the target.
 */
export function useCountUp(
  target: number,
  runKey: unknown,
  duration = 700,
  fromPrevious = false,
): number {
  const [value, setValue] = useState(target);
  const frameRef = useRef<number | null>(null);
  const settledRef = useRef(target);

  useEffect(() => {
    const reduced =
      typeof window !== "undefined" &&
      typeof window.matchMedia === "function" &&
      window.matchMedia("(prefers-reduced-motion: reduce)").matches;

    if (reduced || duration <= 0 || !Number.isFinite(target)) {
      settledRef.current = target;
      setValue(target);
      return;
    }

    const start = performance.now();
    const from = fromPrevious ? settledRef.current : 0;
    settledRef.current = target;
    const tick = (now: number) => {
      const t = Math.min(1, (now - start) / duration);
      const eased = 1 - Math.pow(1 - t, 3); // ease-out cubic
      setValue(from + (target - from) * eased);
      if (t < 1) frameRef.current = requestAnimationFrame(tick);
      else setValue(target);
    };
    frameRef.current = requestAnimationFrame(tick);

    return () => {
      if (frameRef.current !== null) cancelAnimationFrame(frameRef.current);
    };
  }, [target, runKey, duration, fromPrevious]);

  return value;
}
