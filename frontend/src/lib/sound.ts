/**
 * Web Audio synthesised sound effects — no asset files, works fully offline.
 *
 * Every cue is generated on the fly from oscillators + filtered noise, so the
 * bundle ships zero binary audio. The single `sound` singleton is safe to import
 * anywhere; it lazily creates an AudioContext and unlocks it on the first user
 * gesture (browsers block audio until then). Mute state persists to
 * localStorage; `prefers-reduced-motion` is honoured as a sensible default-off.
 */

export type SoundName =
  | "deal"
  | "flip"
  | "chip"
  | "click"
  | "win"
  | "bigwin"
  | "lose"
  | "draw"
  | "ballSettle"
  | "check"
  | "fold"
  | "raise";

const MUTE_KEY = "casino.sound.muted";

function prefersReducedMotion(): boolean {
  return (
    typeof window !== "undefined" &&
    typeof window.matchMedia === "function" &&
    window.matchMedia("(prefers-reduced-motion: reduce)").matches
  );
}

function initialMuted(): boolean {
  if (typeof localStorage !== "undefined") {
    const stored = localStorage.getItem(MUTE_KEY);
    if (stored !== null) return stored === "1";
  }
  // No explicit choice yet: stay quiet for reduced-motion users.
  return prefersReducedMotion();
}

type Listener = (muted: boolean) => void;

class SoundManager {
  private ctx: AudioContext | null = null;
  private master: GainNode | null = null;
  private muted: boolean = initialMuted();
  private unlocked = false;
  private listeners = new Set<Listener>();

  constructor() {
    if (typeof window !== "undefined") {
      const unlock = () => this.unlock();
      window.addEventListener("pointerdown", unlock, { once: true });
      window.addEventListener("keydown", unlock, { once: true });
    }
  }

  /** Create/resume the AudioContext — must run inside a user-gesture handler. */
  unlock(): void {
    if (this.unlocked) return;
    try {
      const Ctx =
        window.AudioContext ||
        (window as unknown as { webkitAudioContext: typeof AudioContext }).webkitAudioContext;
      if (!Ctx) return;
      this.ctx = new Ctx();
      this.master = this.ctx.createGain();
      this.master.gain.value = 0.5;
      this.master.connect(this.ctx.destination);
      this.unlocked = true;
    } catch {
      /* audio unavailable — stay silent */
    }
  }

  isMuted(): boolean {
    return this.muted;
  }

  setMuted(muted: boolean): void {
    this.muted = muted;
    if (typeof localStorage !== "undefined") {
      localStorage.setItem(MUTE_KEY, muted ? "1" : "0");
    }
    this.listeners.forEach((l) => l(muted));
  }

  toggleMute(): boolean {
    this.setMuted(!this.muted);
    return this.muted;
  }

  subscribe(listener: Listener): () => void {
    this.listeners.add(listener);
    return () => this.listeners.delete(listener);
  }

  private ready(): AudioContext | null {
    if (this.muted) return null;
    if (!this.unlocked) this.unlock();
    const ctx = this.ctx;
    if (!ctx || !this.master) return null;
    if (ctx.state === "suspended") void ctx.resume();
    return ctx;
  }

  // ---- primitive synth voices -------------------------------------------

  private tone(
    ctx: AudioContext,
    freq: number,
    at: number,
    dur: number,
    type: OscillatorType,
    peak: number,
  ): void {
    const osc = ctx.createOscillator();
    const gain = ctx.createGain();
    osc.type = type;
    osc.frequency.setValueAtTime(freq, at);
    gain.gain.setValueAtTime(0.0001, at);
    gain.gain.exponentialRampToValueAtTime(peak, at + 0.012);
    gain.gain.exponentialRampToValueAtTime(0.0001, at + dur);
    osc.connect(gain).connect(this.master!);
    osc.start(at);
    osc.stop(at + dur + 0.02);
  }

  private noise(
    ctx: AudioContext,
    at: number,
    dur: number,
    filterFreq: number,
    peak: number,
    q = 0.7,
  ): void {
    const frames = Math.max(1, Math.floor(ctx.sampleRate * dur));
    const buffer = ctx.createBuffer(1, frames, ctx.sampleRate);
    const data = buffer.getChannelData(0);
    for (let i = 0; i < frames; i++) data[i] = Math.random() * 2 - 1;
    const src = ctx.createBufferSource();
    src.buffer = buffer;
    const filter = ctx.createBiquadFilter();
    filter.type = "bandpass";
    filter.frequency.value = filterFreq;
    filter.Q.value = q;
    const gain = ctx.createGain();
    gain.gain.setValueAtTime(peak, at);
    gain.gain.exponentialRampToValueAtTime(0.0001, at + dur);
    src.connect(filter).connect(gain).connect(this.master!);
    src.start(at);
    src.stop(at + dur + 0.02);
  }

  // ---- public cues ------------------------------------------------------

  play(name: SoundName): void {
    const ctx = this.ready();
    if (!ctx) return;
    const t = ctx.currentTime;
    switch (name) {
      case "deal":
        this.noise(ctx, t, 0.12, 2600, 0.18, 1.2);
        break;
      case "flip":
        this.noise(ctx, t, 0.09, 3400, 0.16, 1.5);
        this.tone(ctx, 520, t + 0.02, 0.06, "triangle", 0.05);
        break;
      case "chip":
        this.tone(ctx, 1180, t, 0.05, "triangle", 0.12);
        this.tone(ctx, 1480, t + 0.04, 0.06, "triangle", 0.1);
        break;
      case "click":
        this.tone(ctx, 880, t, 0.04, "square", 0.06);
        break;
      case "check":
        this.noise(ctx, t, 0.1, 320, 0.22, 0.9);
        this.tone(ctx, 160, t, 0.09, "sine", 0.12);
        break;
      case "fold":
        this.noise(ctx, t, 0.22, 1400, 0.12, 0.6);
        break;
      case "raise":
        this.tone(ctx, 1180, t, 0.05, "triangle", 0.1);
        this.tone(ctx, 1480, t + 0.05, 0.05, "triangle", 0.1);
        this.tone(ctx, 1760, t + 0.1, 0.06, "triangle", 0.09);
        break;
      case "draw":
        this.tone(ctx, 392, t, 0.22, "sine", 0.12);
        break;
      case "lose":
        this.tone(ctx, 392, t, 0.22, "sine", 0.12);
        this.tone(ctx, 294, t + 0.16, 0.34, "sine", 0.12);
        break;
      case "win": {
        const notes = [523.25, 659.25, 783.99]; // C5 E5 G5
        notes.forEach((f, i) => this.tone(ctx, f, t + i * 0.1, 0.26, "triangle", 0.13));
        break;
      }
      case "bigwin": {
        const notes = [523.25, 659.25, 783.99, 1046.5]; // C5 E5 G5 C6
        notes.forEach((f, i) => this.tone(ctx, f, t + i * 0.09, 0.34, "triangle", 0.14));
        // sparkle tail
        for (let i = 0; i < 6; i++) {
          this.tone(ctx, 1320 + Math.random() * 900, t + 0.4 + i * 0.05, 0.12, "sine", 0.06);
        }
        break;
      }
      case "ballSettle":
        this.noise(ctx, t, 0.06, 5200, 0.14, 2);
        this.noise(ctx, t + 0.09, 0.05, 4200, 0.1, 2);
        this.tone(ctx, 740, t + 0.14, 0.05, "triangle", 0.07);
        break;
    }
  }

  /** Looping whirr for the roulette spin. Returns a stop function. */
  startSpin(): () => void {
    const ctx = this.ready();
    if (!ctx) return () => undefined;
    const t = ctx.currentTime;
    const frames = Math.floor(ctx.sampleRate * 1.0);
    const buffer = ctx.createBuffer(1, frames, ctx.sampleRate);
    const data = buffer.getChannelData(0);
    for (let i = 0; i < frames; i++) data[i] = Math.random() * 2 - 1;
    const src = ctx.createBufferSource();
    src.buffer = buffer;
    src.loop = true;
    const filter = ctx.createBiquadFilter();
    filter.type = "bandpass";
    filter.frequency.value = 1800;
    filter.Q.value = 1.4;
    const gain = ctx.createGain();
    gain.gain.setValueAtTime(0.0001, t);
    gain.gain.linearRampToValueAtTime(0.08, t + 0.3);
    src.connect(filter).connect(gain).connect(this.master!);
    src.start(t);
    let stopped = false;
    return () => {
      if (stopped) return;
      stopped = true;
      const now = ctx.currentTime;
      gain.gain.cancelScheduledValues(now);
      gain.gain.setValueAtTime(gain.gain.value, now);
      gain.gain.linearRampToValueAtTime(0.0001, now + 0.25);
      src.stop(now + 0.3);
    };
  }
}

export const sound = new SoundManager();
