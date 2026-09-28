import React from "react";
import { useCurrentFrame } from "remotion";
import { useSpringAt } from "../motion/useEnter";
import { typeScale, type SpringPreset } from "../motion/tokens";
import { useTheme } from "../motion/theme";

export type PeopleCrowdProps = {
  count?: number; // 1 = single mascot moment, 2-8 = a small crowd
  pose?: "wave" | "standing"; // only matters when count === 1
  heading?: string;
  caption?: string;
  delay?: number;
  preset?: SpringPreset;
};

/**
 * A single flat-design person: circle head, rounded torso/legs, one arm that
 * can wave. Abstract silhouette (ink for skin/limbs, theme accents for
 * outfit) rather than a literal skin tone, so it stays theme-driven like
 * every other primitive rather than baking in a fixed appearance.
 */
const FlatPerson: React.FC<{
  pose: "wave" | "standing";
  outfit: string;
  pants: string;
  ink: string;
  seedPhase: number;
  delay: number;
  preset: SpringPreset;
}> = ({ pose, outfit, pants, ink, seedPhase, delay, preset }) => {
  const frame = useCurrentFrame();
  const springAt = useSpringAt();
  const popIn = springAt(delay, preset);
  const bob = Math.sin(frame / 18 + seedPhase) * 4;
  // SVG rotate() sweeps clockwise for a positive angle -- the arm hangs down
  // by default (0deg), so raising it into a "hello" wave (up and outward)
  // needs a large clockwise sweep past "left" (90deg) toward "up" (180deg),
  // landing around 155deg, not a small angle that would swing it inward.
  const armAngle = pose === "wave" ? 155 + Math.sin(frame / 5 + seedPhase) * 12 : Math.sin(frame / 30 + seedPhase) * 4;

  return (
    <div style={{ transform: `translateY(${bob}px) scale(${popIn})`, transformOrigin: "bottom center" }}>
      {/* viewBox has extra left margin (-15) so the raised/waving arm has room to swing without clipping. */}
      <svg width="104" height="130" viewBox="-15 0 115 140">
        <rect x="52" y="95" width="14" height="40" rx="7" fill={pants} />
        <rect x="34" y="95" width="14" height="40" rx="7" fill={pants} />
        <rect x="30" y="40" width="40" height="58" rx="18" fill={outfit} />
        <rect x="70" y="46" width="14" height="40" rx="7" fill={ink} />
        {/* Pivot sits at the shoulder joint, not an arbitrary torso point, so
            the swing reads as a moving limb rather than the arm sliding sideways. */}
        <g transform={`rotate(${armAngle} 23 44)`}>
          <rect x="16" y="44" width="14" height="42" rx="7" fill={ink} />
        </g>
        <circle cx="50" cy="22" r="16" fill={ink} />
      </svg>
    </div>
  );
};

/** A small illustrated crowd (or single mascot) for a warm/human beat. */
export const PeopleCrowd: React.FC<PeopleCrowdProps> = ({
  count = 3,
  pose = "wave",
  heading,
  caption,
  delay = 0,
  preset = "snappy",
}) => {
  const theme = useTheme();
  const n = Math.min(Math.max(count, 1), 8);

  return (
    <div style={{ display: "flex", flexDirection: "column", alignItems: "center", gap: 22, fontFamily: theme.fontBody }}>
      {heading && (
        <div style={{ fontSize: typeScale.heading, fontWeight: 700, color: theme.ink, textAlign: "center" }}>{heading}</div>
      )}
      <div style={{ display: "flex", alignItems: "flex-end", gap: n > 4 ? 4 : 16 }}>
        {Array.from({ length: n }).map((_, i) => (
          <div key={i} style={{ marginBottom: i % 2 === 0 ? 0 : 12 }}>
            <FlatPerson
              pose={n === 1 ? pose : i % 3 === 0 ? "wave" : "standing"}
              outfit={i % 2 === 0 ? theme.accent : theme.accent2}
              pants={theme.bgAlt}
              ink={theme.ink}
              seedPhase={i * 1.3}
              delay={delay + i * 4}
              preset={preset}
            />
          </div>
        ))}
      </div>
      {caption && (
        <div style={{ fontSize: typeScale.body, color: theme.muted, textAlign: "center" }}>{caption}</div>
      )}
    </div>
  );
};
