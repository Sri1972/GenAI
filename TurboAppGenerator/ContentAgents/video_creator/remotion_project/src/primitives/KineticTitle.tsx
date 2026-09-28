import React from "react";
import { interpolate } from "remotion";
import { useSpringAt } from "../motion/useEnter";
import { stagger as staggerTokens, typeScale, type SpringPreset, type StaggerPreset, type TypeSize } from "../motion/tokens";
import { useTheme } from "../motion/theme";

export type KineticTitleProps = {
  text: string;
  splitBy?: "word" | "char";
  effect?: "rise" | "blur" | "scale";
  size?: TypeSize;
  weight?: number;
  preset?: SpringPreset;
  stagger?: StaggerPreset;
  delay?: number;
  color?: "ink" | "accent" | "accent2" | "muted";
  align?: "left" | "center";
};

/**
 * Text that builds unit by unit.
 * rise:  each unit slides up out of a mask (editorial, confident)
 * blur:  each unit sharpens from blur while drifting in (cinematic)
 * scale: each unit pops from small (energetic; pair with "bouncy")
 */
export const KineticTitle: React.FC<KineticTitleProps> = ({
  text,
  splitBy = "word",
  effect = "rise",
  size = "title",
  weight = 700,
  preset = "snappy",
  stagger = "normal",
  delay = 0,
  color = "ink",
  align = "center",
}) => {
  const theme = useTheme();
  const springAt = useSpringAt();
  const px = typeScale[size];
  const step = staggerTokens[stagger] / (splitBy === "char" ? 2 : 1);
  const words = text.split(" ");
  let unitIndex = 0;

  return (
    <div
      style={{
        fontFamily: theme.fontDisplay,
        fontSize: px,
        fontWeight: weight,
        lineHeight: 1.08,
        letterSpacing: "-0.02em",
        color: theme[color],
        textAlign: align,
        display: "flex",
        flexWrap: "wrap",
        justifyContent: align === "center" ? "center" : "flex-start",
        columnGap: px * 0.28,
        maxWidth: 1600,
      }}
    >
      {words.map((word, wi) => {
        const units = splitBy === "char" ? word.split("") : [word];
        return (
          <span key={wi} style={{ display: "inline-flex", overflow: effect === "rise" ? "hidden" : "visible", paddingBottom: "0.08em" }}>
            {units.map((u, ui) => {
              const p = springAt(delay + unitIndex++ * step, preset);
              const o = interpolate(p, [0, 0.6], [0, 1], { extrapolateRight: "clamp" });
              let transform = "";
              let filter = "none";
              if (effect === "rise") transform = `translateY(${(1 - p) * 105}%)`;
              if (effect === "blur") {
                transform = `translateY(${(1 - p) * 0.25 * px}px)`;
                filter = `blur(${Math.max(0, 1 - p) * 16}px)`;
              }
              if (effect === "scale") transform = `scale(${interpolate(p, [0, 1], [0.4, 1])})`;
              return (
                <span key={ui} style={{ display: "inline-block", transform, filter, opacity: effect === "rise" ? 1 : o }}>
                  {u}
                </span>
              );
            })}
          </span>
        );
      })}
    </div>
  );
};
