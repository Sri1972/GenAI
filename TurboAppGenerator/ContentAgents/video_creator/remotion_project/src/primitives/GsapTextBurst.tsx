import React from "react";
import { random } from "remotion";
import { useGsapTimeline } from "../motion/useGsapTimeline";
import { typeScale, type TypeSize } from "../motion/tokens";
import { useTheme } from "../motion/theme";

export type GsapTextBurstProps = {
  text: string;
  size?: TypeSize;
  delay?: number;
  underline?: boolean;
};

/**
 * Showcase of the GSAP bridge: characters scatter in with rotation and elastic
 * settle, then an underline sweeps across. Use for one closing or hero line.
 */
export const GsapTextBurst: React.FC<GsapTextBurstProps> = ({ text, size = "hero", delay = 0, underline = true }) => {
  const theme = useTheme();
  const scope = useGsapTimeline((tl) => {
    tl.from(".char", {
      yPercent: (i: number) => rand(`y${i}`, -160, 160),
      xPercent: (i: number) => rand(`x${i}`, -80, 80),
      rotation: (i: number) => rand(`r${i}`, -90, 90),
      scale: 0.2,
      opacity: 0,
      duration: 0.9,
      ease: "back.out(2.2)",
      stagger: { each: 0.025, from: "center" },
    });
    if (underline) tl.from(".underline", { scaleX: 0, transformOrigin: "left center", duration: 0.6, ease: "power3.inOut" }, "-=0.35");
  }, delay);

  return (
    <div ref={scope} style={{ display: "inline-flex", flexDirection: "column", alignItems: "center", fontFamily: theme.fontDisplay }}>
      <div style={{ fontSize: typeScale[size], fontWeight: 800, letterSpacing: "-0.03em", color: theme.ink, whiteSpace: "pre" }}>
        {text.split("").map((ch, i) => (
          <span key={i} className="char" style={{ display: "inline-block" }}>
            {ch === " " ? "\u00A0" : ch}
          </span>
        ))}
      </div>
      {underline && <div className="underline" style={{ width: "100%", height: 10, borderRadius: 5, background: theme.accent2, marginTop: 8 }} />}
    </div>
  );
};

// Deterministic randomness: Remotion's seeded random, never Math.random.
const rand = (key: string, min: number, max: number) => min + random(key) * (max - min);
