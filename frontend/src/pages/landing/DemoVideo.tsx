import { Player, type PlayerRef } from "@remotion/player";
import { useEffect, useRef } from "react";
import { FILM, FILM_DURATION, STAGE } from "./remotion/config";
import { DocifyDemo } from "./remotion/DocifyDemo";

/**
 * The hero film (Remotion, lazy chunk). Plays only while visible (`active`), reports scene changes
 * (only when the chapter changes, not every frame) and can be asked to jump to a scene.
 *
 * "full": the headline intro plays once, then the 4 scenes loop (we seek back to the end of the intro).
 * "stage": scenes only (mobile), plain loop.
 */
export default function DemoVideo({ variant, active, jump, onScene, onReady }: {
  variant: "full" | "stage";
  active: boolean;
  jump: { scene: number; key: number };
  onScene: (scene: number) => void;
  onReady?: () => void;
}) {
  const player = useRef<PlayerRef>(null);
  const current = useRef(0);
  const full = variant === "full";
  const offset = full ? FILM.intro : 0;

  useEffect(() => onReady?.(), [onReady]);

  useEffect(() => {
    const p = player.current;
    if (!p) return;
    if (active) p.play();
    else p.pause();
  }, [active]);

  useEffect(() => {
    const p = player.current;
    if (!p) return;
    const onFrame = (e: { detail: { frame: number } }) => {
      const s = Math.min(3, Math.max(0, Math.floor((e.detail.frame - offset) / FILM.scene)));
      if (s !== current.current) {
        current.current = s;
        onScene(s);
      }
    };
    // Loop the scenes only — the headline intro never replays.
    const onEnded = () => {
      p.seekTo(offset);
      p.play();
    };
    p.addEventListener("frameupdate", onFrame);
    p.addEventListener("ended", onEnded);
    return () => {
      p.removeEventListener("frameupdate", onFrame);
      p.removeEventListener("ended", onEnded);
    };
  }, [onScene, offset]);

  // External jump (chapter click). `key` changes on every click, so re-clicking replays the chapter.
  useEffect(() => {
    const p = player.current;
    if (!p || jump.key === 0) return;
    current.current = jump.scene;
    p.seekTo(offset + jump.scene * FILM.scene + 1);
    p.play();
  }, [jump, offset]);

  return (
    <Player
      ref={player}
      component={DocifyDemo}
      inputProps={{ variant }}
      durationInFrames={full ? FILM_DURATION : FILM.scene * 4}
      fps={FILM.fps}
      compositionWidth={full ? FILM.width : STAGE.width}
      compositionHeight={full ? FILM.height : STAGE.height}
      autoPlay
      initiallyMuted
      controls={false}
      clickToPlay={false}
      doubleClickToFullscreen={false}
      spaceKeyToPlayOrPause={false}
      acknowledgeRemotionLicense
      style={{ width: "100%", height: "100%" }}
    />
  );
}
