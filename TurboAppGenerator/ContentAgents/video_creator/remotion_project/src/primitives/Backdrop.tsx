import React from "react";
import { AbsoluteFill, useCurrentFrame } from "remotion";
import { noise3D } from "@remotion/noise";
import { useTheme } from "../motion/theme";

/**
 * Living background: gradient, slow noise-driven light blobs, faint grid.
 * Layers move at different speeds (parallax) so the frame has depth.
 *
 * The blobs used to be solid circles with `filter: blur(140px)` -- a full
 * canvas-sized CSS blur recomputed every single frame, confirmed (via a
 * real A/B render) to be the single largest per-frame rendering cost in
 * this whole kit. A radial-gradient blob bakes the same soft falloff
 * directly into the fill (no post-process filter needed at all) for a
 * visually similar result at a fraction of the cost.
 */
export const Backdrop: React.FC<{ seed?: string; intensity?: number }> = ({
  seed = "bg",
  intensity = 1,
}) => {
  const frame = useCurrentFrame();
  const theme = useTheme();
  const blobs = [
    { x: 0.2, y: 0.25, r: 700, color: theme.accent, speed: 0.004 },
    { x: 0.8, y: 0.7, r: 800, color: theme.accent2, speed: 0.003 },
    { x: 0.6, y: 0.15, r: 500, color: theme.bgAlt, speed: 0.006 },
  ];
  return (
    <AbsoluteFill style={{ background: `radial-gradient(120% 90% at 30% 20%, ${theme.bgAlt} 0%, ${theme.bg} 60%)` }}>
      {blobs.map((b, i) => {
        const dx = noise3D(seed, i, 0, frame * b.speed) * 160;
        const dy = noise3D(seed, 0, i, frame * b.speed) * 120;
        return (
          <div
            key={i}
            style={{
              position: "absolute",
              left: `calc(${b.x * 100}% - ${b.r / 2}px)`,
              top: `calc(${b.y * 100}% - ${b.r / 2}px)`,
              width: b.r,
              height: b.r,
              borderRadius: "50%",
              background: `radial-gradient(circle, ${b.color} 0%, transparent 70%)`,
              opacity: 0.4 * intensity,
              transform: `translate(${dx}px, ${dy}px)`,
            }}
          />
        );
      })}
      {/* Grid drifts slower than blobs: parallax */}
      <AbsoluteFill
        style={{
          backgroundImage: `linear-gradient(${theme.ink}0A 1px, transparent 1px), linear-gradient(90deg, ${theme.ink}0A 1px, transparent 1px)`,
          backgroundSize: "96px 96px",
          backgroundPosition: `${-frame * 0.15}px ${-frame * 0.1}px`,
          maskImage: "radial-gradient(70% 70% at 50% 50%, black, transparent)",
        }}
      />
    </AbsoluteFill>
  );
};
