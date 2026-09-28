import React from "react";
import { staticFile } from "remotion";
import { Gif } from "@remotion/gif";
import { useSpringAt } from "../motion/useEnter";
import { typeScale } from "../motion/tokens";
import { useTheme } from "../motion/theme";

export type AnimatedGifProps = {
  name: string; // a .gif filename (no extension) from video_creator/gifs/ -- see that folder's README
  heading?: string;
  caption?: string;
  delay?: number;
};

/**
 * Plays a real animated GIF, frame-accurately synced to this video's own
 * timeline via @remotion/gif (not a plain <img>, which would only ever show
 * the GIF's first frame during a Chromium-rendered capture). The GIF itself
 * is never bundled/sourced by this kit -- see video_creator/gifs/README.md;
 * this primitive only plays whatever the user has actually placed there.
 */
export const AnimatedGif: React.FC<AnimatedGifProps> = ({ name, heading, caption, delay = 0 }) => {
  const theme = useTheme();
  const springAt = useSpringAt();
  const popIn = springAt(delay, "snappy");

  return (
    <div style={{ display: "flex", flexDirection: "column", alignItems: "center", gap: 22, fontFamily: theme.fontBody }}>
      {heading && (
        <div style={{ fontSize: typeScale.heading, fontWeight: 700, color: theme.ink, textAlign: "center" }}>{heading}</div>
      )}
      <div style={{ transform: `scale(${popIn})`, transformOrigin: "center" }}>
        <Gif src={staticFile(`gifs/${name}.gif`)} width={280} height={280} fit="contain" />
      </div>
      {caption && (
        <div style={{ fontSize: typeScale.body, color: theme.muted, textAlign: "center" }}>{caption}</div>
      )}
    </div>
  );
};
