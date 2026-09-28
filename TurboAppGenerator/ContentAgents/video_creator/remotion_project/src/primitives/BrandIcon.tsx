import React from "react";
import { Img, staticFile, useCurrentFrame } from "remotion";
import { useSpringAt } from "../motion/useEnter";
import { typeScale } from "../motion/tokens";
import { useTheme } from "../motion/theme";

export type BrandIconProps = {
  provider: "aws" | "gcp" | "azure";
  icon: string; // a name from ContentAgents/icons/catalog.json for this provider
  heading?: string;
  caption?: string;
  delay?: number;
};

/**
 * A real cloud-provider service glyph (AWS/GCP/Azure's own official icon
 * SVGs, synced into public/icons/ -- see ContentAgents/icons/). Unlike
 * IconMotion, this is a fixed-color brand image, not a recolorable
 * single-stroke icon -- no theme tinting (that would look wrong on an
 * official logo), and a simpler motion set (pop-in + gentle float only --
 * IconMotion's spin/drive/launch motions are tied to lucide concepts like
 * gears/vehicles/rockets that don't apply to a generic service glyph).
 */
export const BrandIcon: React.FC<BrandIconProps> = ({ provider, icon, heading, caption, delay = 0 }) => {
  const frame = useCurrentFrame() - delay;
  const theme = useTheme();
  const springAt = useSpringAt();
  const popIn = springAt(delay, "snappy");
  const floatY = Math.sin(frame / 20) * 8;

  return (
    <div style={{ display: "flex", flexDirection: "column", alignItems: "center", gap: 22, fontFamily: theme.fontBody }}>
      {heading && (
        <div style={{ fontSize: typeScale.heading, fontWeight: 700, color: theme.ink, textAlign: "center" }}>{heading}</div>
      )}
      <div style={{ width: 140, height: 140, display: "flex", alignItems: "center", justifyContent: "center" }}>
        <div style={{ transform: `scale(${popIn}) translateY(${floatY}px)`, transformOrigin: "center" }}>
          <Img src={staticFile(`icons/${provider}/${icon}.svg`)} style={{ width: 110, height: 110 }} />
        </div>
      </div>
      {caption && (
        <div style={{ fontSize: typeScale.body, color: theme.muted, textAlign: "center" }}>{caption}</div>
      )}
    </div>
  );
};
