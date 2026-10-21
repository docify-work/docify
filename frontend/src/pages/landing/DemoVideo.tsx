import { Player, type PlayerRef } from "@remotion/player";
import { useEffect, useRef } from "react";
import { FILM, FILM_DURATION } from "./remotion/config";
import { DocifyDemo } from "./remotion/DocifyDemo";

/**
 * The hero stage film (Remotion, lazy chunk). Plays only while visible (`active`), reports scene changes
 * (only when the chapter changes, not every frame) and can be asked to jump to a scene.
 */
export default function DemoVideo({ active, jump, onScene }: {
  active: boolean;
  jump: { scene: number; key: number };
  onScene: (scene: number) => void;
}) {
  const player = useRef<PlayerRef>(null);
  const current = useRef(0);

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
      const s = Math.min(3, Math.floor(e.detail.frame / FILM.scene));
      if (s !== current.current) {
        current.current = s;
        onScene(s);
      }
    };
    p.addEventListener("frameupdate", onFrame);
    return () => p.removeEventListener("frameupdate", onFrame);
  }, [onScene]);

  // External jump (chapter click). `key` changes on every click, so re-clicking replays the chapter.
  useEffect(() => {
    const p = player.current;
    if (!p || jump.key === 0) return;
    current.current = jump.scene;
    p.seekTo(jump.scene * FILM.scene);
    p.play();
  }, [jump]);

  return (
    <Player
      ref={player}
      component={DocifyDemo}
      durationInFrames={FILM_DURATION}
      fps={FILM.fps}
      compositionWidth={FILM.width}
      compositionHeight={FILM.height}
      autoPlay
      loop
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
