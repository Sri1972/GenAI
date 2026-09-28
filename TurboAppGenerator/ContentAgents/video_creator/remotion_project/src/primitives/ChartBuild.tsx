import React from "react";
import { interpolate } from "remotion";
import { useSpringAt } from "../motion/useEnter";
import { stagger as staggerTokens, typeScale, type StaggerPreset } from "../motion/tokens";
import { useTheme } from "../motion/theme";

export type ChartBuildProps = {
  data: { label: string; value: number }[];
  highlight?: number;
  delay?: number;
  stagger?: StaggerPreset;
  height?: number;
  valueSuffix?: string;
};

/** Bar chart where the baseline draws first, then bars grow in sequence and values count up. */
export const ChartBuild: React.FC<ChartBuildProps> = ({
  data,
  highlight,
  delay = 0,
  stagger = "loose",
  height = 520,
  valueSuffix = "",
}) => {
  const theme = useTheme();
  const springAt = useSpringAt();
  const max = Math.max(...data.map((d) => d.value));
  const axis = springAt(delay, "gentle");
  const barWidth = Math.min(160, 1100 / data.length - 40);

  return (
    <div style={{ fontFamily: theme.fontBody, display: "flex", flexDirection: "column", alignItems: "center" }}>
      <div style={{ display: "flex", alignItems: "flex-end", gap: 40, height }}>
        {data.map((d, i) => {
          const p = springAt(delay + 8 + i * staggerTokens[stagger], "heavy");
          const isHi = i === highlight;
          const h = (d.value / max) * (height - 70) * p;
          return (
            <div key={i} style={{ display: "flex", flexDirection: "column", alignItems: "center", gap: 14 }}>
              <div
                style={{
                  fontSize: typeScale.caption,
                  fontWeight: 700,
                  color: isHi ? theme.accent2 : theme.ink,
                  opacity: interpolate(p, [0.4, 0.9], [0, 1], { extrapolateLeft: "clamp", extrapolateRight: "clamp" }),
                  fontVariantNumeric: "tabular-nums",
                }}
              >
                {Math.round(d.value * Math.min(p, 1)).toLocaleString("en-US")}
                {valueSuffix}
              </div>
              <div
                style={{
                  width: barWidth,
                  height: Math.max(0, h),
                  borderRadius: "10px 10px 2px 2px",
                  background: isHi
                    ? `linear-gradient(180deg, ${theme.accent2}, ${theme.accent2}AA)`
                    : `linear-gradient(180deg, ${theme.accent}, ${theme.accent}66)`,
                  boxShadow: isHi ? `0 0 60px ${theme.accent2}55` : "none",
                }}
              />
            </div>
          );
        })}
      </div>
      <div style={{ width: 1200 * axis, height: 3, background: theme.muted, opacity: 0.5, borderRadius: 2 }} />
      <div style={{ display: "flex", gap: 40, marginTop: 18 }}>
        {data.map((d, i) => (
          <div key={i} style={{ width: barWidth, textAlign: "center", fontSize: typeScale.caption * 0.85, color: theme.muted, opacity: axis }}>
            {d.label}
          </div>
        ))}
      </div>
    </div>
  );
};
