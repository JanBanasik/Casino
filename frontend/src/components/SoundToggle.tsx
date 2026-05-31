import { useEffect, useState } from "react";
import { sound } from "../lib/sound";

/** Small mute/unmute control for table chrome; reflects the global sound state. */
export default function SoundToggle() {
  const [muted, setMuted] = useState(sound.isMuted());

  useEffect(() => sound.subscribe(setMuted), []);

  return (
    <button
      type="button"
      className={`sound-toggle ${muted ? "sound-toggle--muted" : ""}`}
      onClick={() => sound.toggleMute()}
      aria-label={muted ? "Włącz dźwięk" : "Wycisz dźwięk"}
      title={muted ? "Włącz dźwięk" : "Wycisz dźwięk"}
    >
      {muted ? "🔇" : "🔊"}
    </button>
  );
}
