import React from "react";
import { interpolate, useCurrentFrame } from "remotion";
import {
  Settings, Cog, Wrench, RefreshCw,
  Car, Truck, Bus, Bike,
  Rocket, Lightbulb,
  Globe, TrendingUp, Target, ShieldCheck, Cloud, Smartphone, Laptop, Database, Zap,
  Store, Factory, Handshake, Warehouse, Users,
} from "lucide-react";
import { useSpringAt } from "../motion/useEnter";
import { typeScale } from "../motion/tokens";
import { useTheme } from "../motion/theme";

// A fixed name -> lucide component lookup -- the storyboard only ever
// carries a NAME (validated against this same list on the Python side
// before it ever reaches here); which icon that resolves to, and how it
// moves, is entirely this file's decision, never the LLM's.
export const ICON_NAMES = [
  "Settings", "Cog", "Wrench", "RefreshCw",
  "Car", "Truck", "Bus", "Bike",
  "Rocket", "Lightbulb",
  "Globe", "TrendingUp", "Target", "ShieldCheck", "Cloud", "Smartphone", "Laptop", "Database", "Zap",
  "Store", "Factory", "Handshake", "Warehouse", "Users",
] as const;

const ICON_COMPONENTS: Record<string, React.ComponentType<{ size?: number; color?: string; strokeWidth?: number }>> = {
  Settings, Cog, Wrench, RefreshCw,
  Car, Truck, Bus, Bike,
  Rocket, Lightbulb,
  Globe, TrendingUp, Target, ShieldCheck, Cloud, Smartphone, Laptop, Database, Zap,
  Store, Factory, Handshake, Warehouse, Users,
};

type IconMotionKind = "spin" | "drive" | "launch" | "pulse" | "float";
const ICON_MOTION: Record<string, IconMotionKind> = {
  Settings: "spin", Cog: "spin", Wrench: "spin", RefreshCw: "spin",
  Car: "drive", Truck: "drive", Bus: "drive", Bike: "drive",
  Rocket: "launch",
  Lightbulb: "pulse",
  Globe: "float", TrendingUp: "float", Target: "float", ShieldCheck: "float",
  Cloud: "float", Smartphone: "float", Laptop: "float", Database: "float", Zap: "float",
};

export type IconMotionProps = {
  icon: string; // one of ICON_NAMES -- falls back to Settings/float if not
  heading?: string;
  caption?: string;
  delay?: number;
  durationInFrames?: number; // scales the drive/launch travel distance
  color?: "ink" | "accent" | "accent2";
};

// A few short, fading horizontal streaks trailing an icon's direction of
// travel -- the classic 2D-motion-graphics "moving fast" cue, works behind
// any icon regardless of its own shape.
const SpeedLines: React.FC<{ offsetX: number; color: string }> = ({ offsetX, color }) => {
  const lines = [
    { dx: -70, dy: -18, w: 34, o: 0.5 },
    { dx: -90, dy: 0, w: 46, o: 0.35 },
    { dx: -68, dy: 18, w: 30, o: 0.45 },
  ];
  return (
    <>
      {lines.map((l, i) => (
        <div
          key={i}
          style={{
            position: "absolute", left: offsetX + l.dx - l.w, top: `calc(50% + ${l.dy}px)`, width: l.w, height: 4,
            borderRadius: 2, background: color, opacity: l.o,
          }}
        />
      ))}
    </>
  );
};

/** A single animated object/concept icon -- one visual noun, sparingly used. */
export const IconMotion: React.FC<IconMotionProps> = ({
  icon, heading, caption, delay = 0, durationInFrames = 90, color = "accent",
}) => {
  const frame = useCurrentFrame() - delay;
  const theme = useTheme();
  const springAt = useSpringAt();
  const popIn = springAt(delay, "snappy");
  const Icon = ICON_COMPONENTS[icon] ?? Settings;
  const motion = ICON_MOTION[icon] ?? "float";
  const iconColor = theme[color];

  // Each motion is a whole-icon transform (translate/rotate/scale) -- never
  // a sub-part animation, since an off-the-shelf icon has no separately
  // movable pieces.
  let transform = `scale(${popIn})`;
  let offsetX = 0;
  if (motion === "spin") {
    transform = `scale(${popIn}) rotate(${frame * 3}deg)`;
  } else if (motion === "drive") {
    offsetX = interpolate(frame, [15, durationInFrames - 10], [-260, 260], {
      extrapolateLeft: "clamp", extrapolateRight: "clamp",
    });
    const bounceY = Math.sin(frame / 4) * 3;
    transform = `scale(${popIn}) translateX(${offsetX}px) translateY(${bounceY}px)`;
  } else if (motion === "launch") {
    const riseY = interpolate(frame, [15, durationInFrames], [0, -140], { extrapolateLeft: "clamp", extrapolateRight: "clamp" });
    transform = `scale(${popIn}) translateY(${riseY}px) rotate(-8deg)`;
  } else if (motion === "pulse") {
    const pulse = 1 + Math.sin(frame / 10) * 0.12;
    transform = `scale(${popIn * pulse})`;
  } else {
    const floatY = Math.sin(frame / 20) * 8;
    const sway = Math.sin(frame / 34) * 4;
    transform = `scale(${popIn}) translateY(${floatY}px) rotate(${sway}deg)`;
  }

  return (
    <div style={{ display: "flex", flexDirection: "column", alignItems: "center", gap: 22, fontFamily: theme.fontBody }}>
      {heading && (
        <div style={{ fontSize: typeScale.heading, fontWeight: 700, color: theme.ink, textAlign: "center" }}>{heading}</div>
      )}
      <div style={{ position: "relative", width: 140, height: 140, display: "flex", alignItems: "center", justifyContent: "center" }}>
        {motion === "drive" && <SpeedLines offsetX={offsetX} color={iconColor} />}
        <div style={{ transform, transformOrigin: "center" }}>
          <Icon size={100} color={iconColor} strokeWidth={1.75} />
        </div>
      </div>
      {caption && (
        <div style={{ fontSize: typeScale.body, color: theme.muted, textAlign: "center" }}>{caption}</div>
      )}
    </div>
  );
};
