import { spring, useCurrentFrame, useVideoConfig } from "remotion";
import { springs, type SpringPreset } from "./tokens";

/**
 * Spring progress (0 -> 1, may overshoot slightly) starting at `delay` frames.
 * The building block for every entrance in the kit.
 */
export const useEnter = (delay = 0, preset: SpringPreset = "snappy") => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();
  return spring({ frame: frame - delay, fps, config: springs[preset] });
};

/** Returns a function so staggered children can each get their own spring. */
export const useSpringAt = () => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();
  return (delay: number, preset: SpringPreset = "snappy") =>
    spring({ frame: frame - delay, fps, config: springs[preset] });
};
