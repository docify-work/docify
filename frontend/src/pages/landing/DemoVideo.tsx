import { Player } from "@remotion/player";
import { DEMO, DEMO_DURATION } from "./remotion/config";
import { DocifyDemo } from "./remotion/DocifyDemo";

/** Loaded lazily (Remotion is ~100 kB): rendered only once the section is near the viewport. */
export default function DemoVideo() {
  return (
    <Player
      component={DocifyDemo}
      durationInFrames={DEMO_DURATION}
      fps={DEMO.fps}
      compositionWidth={DEMO.width}
      compositionHeight={DEMO.height}
      autoPlay
      loop
      initiallyMuted
      controls={false}
      clickToPlay={false}
      acknowledgeRemotionLicense
      style={{ width: "100%", aspectRatio: "16 / 9", borderRadius: 18 }}
    />
  );
}
