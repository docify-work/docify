import { Player, type PlayerRef } from "@remotion/player";
import { useEffect, useRef } from "react";
import { FILM, FILM_DURATION } from "./remotion/config";
import { DocifyDemo } from "./remotion/DocifyDemo";

/** The hero stage film (Remotion, lazy chunk). Loops, and plays only while visible (`active`). */
export default function DemoVideo({ active }: { active: boolean }) {
  const player = useRef<PlayerRef>(null);

  useEffect(() => {
    const p = player.current;
    if (!p) return;
    if (active) p.play();
    else p.pause();
  }, [active]);

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
