import React from "react";
import { interpolate } from "remotion";
import { useSpringAt } from "../motion/useEnter";
import { stagger as staggerTokens, typeScale, type SpringPreset, type StaggerPreset } from "../motion/tokens";
import { useTheme } from "../motion/theme";

export type StaggerListProps = {
  items: string[];
  delay?: number;
  stagger?: StaggerPreset;
  preset?: SpringPreset;
  highlight?: number; // index to emphasise with the accent
};

/** Bullet points that slide in one after another, each with a marker line that grows. */
export const StaggerList: React.FC<StaggerListProps> = ({
  items,
  delay = 0,
  stagger = "loose",
  preset = "snappy",
  highlight,
}) => {
  const theme = useTheme();
  const springAt = useSpringAt();
  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 28, fontFamily: theme.fontBody }}>
      {items.map((item, i) => {
        const p = springAt(delay + i * staggerTokens[stagger] * 1.5, preset);
        const isHi = i === highlight;
        return (
          <div
            key={i}
            style={{
              display: "flex",
              alignItems: "center",
              gap: 28,
              opacity: interpolate(p, [0, 0.5], [0, 1], { extrapolateRight: "clamp" }),
              transform: `translateX(${(1 - p) * -60}px)`,
            }}
          >
            <div
              style={{
                width: 48 * Math.min(p, 1.2),
                height: 6,
                borderRadius: 3,
                background: isHi ? theme.accent2 : theme.accent,
              }}
            />
            <span style={{ fontSize: typeScale.body, fontWeight: isHi ? 700 : 500, color: isHi ? theme.ink : theme.muted }}>
              {item}
            </span>
          </div>
        );
      })}
    </div>
  );
};
