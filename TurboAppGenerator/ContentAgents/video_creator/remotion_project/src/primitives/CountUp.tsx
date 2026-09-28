import React from "react";
import { Easing, interpolate, useCurrentFrame } from "remotion";
import { useEnter } from "../motion/useEnter";
import { typeScale } from "../motion/tokens";
import { useTheme } from "../motion/theme";

export type CountUpProps = {
  to: number;
  from?: number;
  label?: string;
  prefix?: string;
  suffix?: string;
  decimals?: number;
  delay?: number;
  durationInFrames?: number;
  color?: "ink" | "accent" | "accent2";
};

/** A big number that counts up with an ease-out, plus a label that follows it in. */
export const CountUp: React.FC<CountUpProps> = ({
  to,
  from = 0,
  label,
  prefix = "",
  suffix = "",
  decimals = 0,
  delay = 0,
  durationInFrames = 45,
  color = "ink",
}) => {
  const frame = useCurrentFrame();
  const theme = useTheme();
  const enter = useEnter(delay, "heavy");
  const labelIn = useEnter(delay + 12, "snappy");
  const value = interpolate(frame - delay, [0, durationInFrames], [from, to], {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
    easing: Easing.out(Easing.cubic),
  });
  const formatted = value.toLocaleString("en-US", {
    minimumFractionDigits: decimals,
    maximumFractionDigits: decimals,
  });
  return (
    <div style={{ fontFamily: theme.fontDisplay, display: "flex", flexDirection: "column", alignItems: "flex-start" }}>
      <div
        style={{
          fontSize: typeScale.hero,
          fontWeight: 800,
          letterSpacing: "-0.03em",
          color: theme[color],
          fontVariantNumeric: "tabular-nums",
          transform: `translateY(${(1 - enter) * 40}px) scale(${0.9 + 0.1 * enter})`,
          opacity: Math.min(1, enter * 1.5),
        }}
      >
        {prefix}
        {formatted}
        {suffix}
      </div>
      {label && (
        <div
          style={{
            fontSize: typeScale.caption,
            color: theme.muted,
            fontWeight: 500,
            opacity: labelIn,
            transform: `translateY(${(1 - labelIn) * 16}px)`,
          }}
        >
          {label}
        </div>
      )}
    </div>
  );
};
