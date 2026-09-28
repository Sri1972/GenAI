import React from "react";
import { AbsoluteFill, Easing, interpolate, useCurrentFrame } from "remotion";

export type CameraMove = {
  from?: number; // start scale
  to?: number; // end scale
  driftX?: number; // px over the scene
  driftY?: number;
  rotate?: number; // degrees over the scene
};

/**
 * Slow, continuous camera move over the whole scene. Makes static layouts feel
 * filmed rather than placed. Keep it subtle: 1.0 -> 1.06-1.1.
 */
export const CameraPush: React.FC<
  CameraMove & { durationInFrames: number; children: React.ReactNode }
> = ({ from = 1, to = 1.07, driftX = 0, driftY = -20, rotate = 0, durationInFrames, children }) => {
  const frame = useCurrentFrame();
  const t = interpolate(frame, [0, durationInFrames], [0, 1], {
    extrapolateRight: "clamp",
    easing: Easing.inOut(Easing.sin),
  });
  return (
    <AbsoluteFill
      style={{
        transform: `translate(${driftX * t}px, ${driftY * t}px) scale(${from + (to - from) * t}) rotate(${rotate * t}deg)`,
        transformOrigin: "50% 50%",
      }}
    >
      {children}
    </AbsoluteFill>
  );
};
