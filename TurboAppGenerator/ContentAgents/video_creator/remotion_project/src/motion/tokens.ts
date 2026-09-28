import type { SpringConfig } from "remotion";

/**
 * The motion system. Every animation in the kit uses these values,
 * so videos feel consistent. The agent picks presets by name; it never
 * writes raw spring numbers.
 */
export const springs = {
  // Confident, tiny overshoot. Default for most entrances.
  snappy: { damping: 18, stiffness: 180, mass: 0.6 },
  // No overshoot, smooth settle. Backgrounds, large surfaces, camera.
  gentle: { damping: 200, stiffness: 100, mass: 1 },
  // Playful overshoot. Use sparingly: one hero moment per scene.
  bouncy: { damping: 9, stiffness: 120, mass: 0.7 },
  // Weighty, slow start. Big numbers, charts, closing titles.
  heavy: { damping: 28, stiffness: 70, mass: 1.6 },
} satisfies Record<string, Partial<SpringConfig>>;

export type SpringPreset = keyof typeof springs;

/** Frames between siblings in a staggered group (at 30fps). */
export const stagger = { tight: 2, normal: 4, loose: 8 } as const;
export type StaggerPreset = keyof typeof stagger;

export type Theme = {
  bg: string;
  bgAlt: string;
  ink: string;
  muted: string;
  accent: string;
  accent2: string;
  fontDisplay: string;
  fontBody: string;
};

export const defaultTheme: Theme = {
  bg: "#0E1A2B",
  bgAlt: "#1A2E4A",
  ink: "#F1F4F8",
  muted: "#8EA1BC",
  accent: "#5B8CFF",
  accent2: "#FFB547",
  fontDisplay: "Sora, system-ui, sans-serif",
  fontBody: "Sora, system-ui, sans-serif",
};

/** Type scale in px for a 1920x1080 canvas. */
export const typeScale = { hero: 132, title: 88, heading: 60, body: 40, caption: 28 } as const;
export type TypeSize = keyof typeof typeScale;
