import { useEffect, useRef } from "react";

interface Particle {
  x: number;
  y: number;
  vx: number;
  vy: number;
  rot: number;
  vr: number;
  size: number;
  color: string;
  life: number;
}

const COLORS = ["#f0d060", "#d4af37", "#2ecc87", "#eef5f1", "#9a7b1a"];

/**
 * Lightweight canvas confetti. Fires a fresh burst each time `fireKey` changes
 * to a new truthy value. `big` raises particle count + spread for jackpot wins.
 * Renders nothing (and never animates) when the user prefers reduced motion.
 */
export default function ConfettiBurst({ fireKey, big = false }: { fireKey: number; big?: boolean }) {
  const canvasRef = useRef<HTMLCanvasElement | null>(null);
  const rafRef = useRef<number | null>(null);

  useEffect(() => {
    if (!fireKey) return;
    const reduced =
      typeof window !== "undefined" &&
      typeof window.matchMedia === "function" &&
      window.matchMedia("(prefers-reduced-motion: reduce)").matches;
    if (reduced) return;

    const canvas = canvasRef.current;
    if (!canvas) return;
    const ctx = canvas.getContext("2d");
    if (!ctx) return;

    const W = (canvas.width = window.innerWidth);
    const H = (canvas.height = window.innerHeight);
    const originX = W / 2;
    const originY = H * 0.42;
    const count = big ? 160 : 70;
    const spread = big ? 9 : 6;

    const particles: Particle[] = Array.from({ length: count }, () => {
      const angle = Math.random() * Math.PI * 2;
      const speed = Math.random() * spread + 2;
      return {
        x: originX,
        y: originY,
        vx: Math.cos(angle) * speed,
        vy: Math.sin(angle) * speed - 4,
        rot: Math.random() * Math.PI,
        vr: (Math.random() - 0.5) * 0.3,
        size: Math.random() * 6 + 4,
        color: COLORS[Math.floor(Math.random() * COLORS.length)],
        life: 1,
      };
    });

    const gravity = 0.16;
    const drag = 0.992;
    let stopped = false;

    const render = () => {
      ctx.clearRect(0, 0, W, H);
      let alive = false;
      for (const p of particles) {
        if (p.life <= 0) continue;
        alive = true;
        p.vx *= drag;
        p.vy = p.vy * drag + gravity;
        p.x += p.vx;
        p.y += p.vy;
        p.rot += p.vr;
        p.life -= 0.009;
        ctx.save();
        ctx.translate(p.x, p.y);
        ctx.rotate(p.rot);
        ctx.globalAlpha = Math.max(0, p.life);
        ctx.fillStyle = p.color;
        ctx.fillRect(-p.size / 2, -p.size / 2, p.size, p.size * 0.6);
        ctx.restore();
      }
      if (alive && !stopped) {
        rafRef.current = requestAnimationFrame(render);
      } else {
        ctx.clearRect(0, 0, W, H);
      }
    };
    rafRef.current = requestAnimationFrame(render);

    return () => {
      stopped = true;
      if (rafRef.current !== null) cancelAnimationFrame(rafRef.current);
      ctx.clearRect(0, 0, W, H);
    };
  }, [fireKey, big]);

  return <canvas ref={canvasRef} className="confetti-canvas" aria-hidden="true" />;
}
