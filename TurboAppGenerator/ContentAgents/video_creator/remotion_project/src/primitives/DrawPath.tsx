import React, { useMemo } from "react";
import { Easing, interpolate, useCurrentFrame } from "remotion";
import { evolvePath, getLength, getPointAtLength } from "@remotion/paths";
import { useTheme } from "../motion/theme";

export type DrawPathProps = {
  d: string; // SVG path data in a 1000x600 viewBox
  delay?: number;
  durationInFrames?: number;
  strokeWidth?: number;
  color?: "accent" | "accent2" | "ink";
  showHead?: boolean; // glowing dot that rides the leading edge
  nodes?: { at: number; label: string }[]; // labels that appear as the line passes (at: 0-1 along the path)
};

/** An SVG line that draws itself, optionally with a glowing head and labels that pop as it passes. */
export const DrawPath: React.FC<DrawPathProps> = ({
  d,
  delay = 0,
  durationInFrames = 50,
  strokeWidth = 6,
  color = "accent",
  showHead = true,
  nodes = [],
}) => {
  const frame = useCurrentFrame();
  const theme = useTheme();
  const length = useMemo(() => getLength(d), [d]);
  const progress = interpolate(frame - delay, [0, durationInFrames], [0, 1], {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
    easing: Easing.inOut(Easing.cubic),
  });
  const { strokeDasharray, strokeDashoffset } = evolvePath(progress, d);
  const head = getPointAtLength(d, Math.max(0.01, progress * length)) ?? { x: 0, y: 0 };
  const c = theme[color];

  return (
    <svg viewBox="0 0 1000 600" style={{ width: "100%", maxWidth: 1400, height: "auto", overflow: "visible" }}>
      <path d={d} fill="none" stroke={theme.muted} strokeOpacity={0.15} strokeWidth={strokeWidth} strokeLinecap="round" />
      <path
        d={d}
        fill="none"
        stroke={c}
        strokeWidth={strokeWidth}
        strokeLinecap="round"
        strokeDasharray={strokeDasharray}
        strokeDashoffset={strokeDashoffset}
        style={{ filter: `drop-shadow(0 0 12px ${c})` }}
      />
      {showHead && progress > 0 && progress < 1 && <circle cx={head.x} cy={head.y} r={strokeWidth * 2.2} fill={c} style={{ filter: `drop-shadow(0 0 16px ${c})` }} />}
      {nodes.map((n, i) => {
        const pt = getPointAtLength(d, n.at * length) ?? { x: 0, y: 0 };
        const shown = interpolate(progress, [n.at - 0.02, n.at + 0.06], [0, 1], { extrapolateLeft: "clamp", extrapolateRight: "clamp" });
        return (
          <g key={i} opacity={shown} transform={`translate(${pt.x} ${pt.y}) scale(${0.6 + 0.4 * shown})`}>
            <circle r={14} fill={theme.bg} stroke={c} strokeWidth={4} />
            <text y={-34} textAnchor="middle" fill={theme.ink} fontSize={36} fontWeight={600} fontFamily={theme.fontBody}>
              {n.label}
            </text>
          </g>
        );
      })}
    </svg>
  );
};
