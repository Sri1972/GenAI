import { z } from "zod";

const preset = z.enum(["snappy", "gentle", "bouncy", "heavy"]);
const staggerP = z.enum(["tight", "normal", "loose"]);
const size = z.enum(["hero", "title", "heading", "body", "caption"]);

const kineticTitle = z.object({
  type: z.literal("kineticTitle"),
  text: z.string(),
  splitBy: z.enum(["word", "char"]).optional(),
  effect: z.enum(["rise", "blur", "scale"]).optional(),
  size: size.optional(),
  weight: z.number().optional(),
  preset: preset.optional(),
  stagger: staggerP.optional(),
  delay: z.number().optional(),
  color: z.enum(["ink", "accent", "accent2", "muted"]).optional(),
  align: z.enum(["left", "center"]).optional(),
});

const staggerList = z.object({
  type: z.literal("staggerList"),
  items: z.array(z.string()).min(1).max(6),
  delay: z.number().optional(),
  stagger: staggerP.optional(),
  preset: preset.optional(),
  highlight: z.number().optional(),
});

const countUp = z.object({
  type: z.literal("countUp"),
  to: z.number(),
  from: z.number().optional(),
  label: z.string().optional(),
  prefix: z.string().optional(),
  suffix: z.string().optional(),
  decimals: z.number().optional(),
  delay: z.number().optional(),
  durationInFrames: z.number().optional(),
  color: z.enum(["ink", "accent", "accent2"]).optional(),
});

const chartBuild = z.object({
  type: z.literal("chartBuild"),
  data: z.array(z.object({ label: z.string(), value: z.number() })).min(2).max(8),
  highlight: z.number().optional(),
  delay: z.number().optional(),
  stagger: staggerP.optional(),
  height: z.number().optional(),
  valueSuffix: z.string().optional(),
});

const drawPath = z.object({
  type: z.literal("drawPath"),
  d: z.string(),
  delay: z.number().optional(),
  durationInFrames: z.number().optional(),
  strokeWidth: z.number().optional(),
  color: z.enum(["accent", "accent2", "ink"]).optional(),
  showHead: z.boolean().optional(),
  nodes: z.array(z.object({ at: z.number().min(0).max(1), label: z.string() })).optional(),
});

const gsapTextBurst = z.object({
  type: z.literal("gsapTextBurst"),
  text: z.string().max(40),
  size: size.optional(),
  delay: z.number().optional(),
  underline: z.boolean().optional(),
});

const peopleCrowd = z.object({
  type: z.literal("peopleCrowd"),
  count: z.number().min(1).max(8).optional(),
  pose: z.enum(["wave", "standing"]).optional(),
  heading: z.string().optional(),
  caption: z.string().optional(),
  delay: z.number().optional(),
  preset: preset.optional(),
});

const diagramNode = z.object({ label: z.string(), icon: z.string(), caption: z.string().optional() });

const iconMotion = z.object({
  type: z.literal("iconMotion"),
  icon: z.string(),
  heading: z.string().optional(),
  caption: z.string().optional(),
  delay: z.number().optional(),
  durationInFrames: z.number().optional(),
  color: z.enum(["ink", "accent", "accent2"]).optional(),
});

const diagramFlow = z.object({
  type: z.literal("diagramFlow"),
  nodes: z.array(diagramNode).min(2).max(5),
  heading: z.string().optional(),
  delay: z.number().optional(),
});

const brandIcon = z.object({
  type: z.literal("brandIcon"),
  provider: z.enum(["aws", "gcp", "azure"]),
  icon: z.string(),
  heading: z.string().optional(),
  caption: z.string().optional(),
  delay: z.number().optional(),
});

const animatedGif = z.object({
  type: z.literal("animatedGif"),
  name: z.string(),
  heading: z.string().optional(),
  caption: z.string().optional(),
  delay: z.number().optional(),
});

export const elementSchema = z.discriminatedUnion("type", [
  kineticTitle,
  staggerList,
  countUp,
  chartBuild,
  drawPath,
  gsapTextBurst,
  peopleCrowd,
  iconMotion,
  brandIcon,
  animatedGif,
  diagramFlow,
]);

export const transitionSchema = z.object({
  type: z.enum(["none", "fade", "slide", "wipe", "flip"]),
  direction: z.enum(["from-left", "from-right", "from-top", "from-bottom"]).optional(),
  durationInFrames: z.number().optional(),
});

export const sceneSchema = z.object({
  id: z.string(),
  durationInFrames: z.number().min(30),
  layout: z.enum(["center", "stack", "split", "row"]).default("center"),
  camera: z
    .union([
      z.literal(false),
      z.object({
        from: z.number().optional(),
        to: z.number().optional(),
        driftX: z.number().optional(),
        driftY: z.number().optional(),
        rotate: z.number().optional(),
      }),
    ])
    .optional(),
  motionBlur: z.boolean().optional(),
  transitionIn: transitionSchema.optional(),
  elements: z.array(elementSchema).min(1),
  // Written by video_creator/run.py's synthesize_narration AFTER the
  // storyboard is finalized -- never something the agent decides or sees
  // as a field to fill; the file lives in remotion_project/public/narration/.
  narrationFile: z.string().optional(),
});

export const storyboardSchema = z.object({
  fps: z.number().default(30),
  // 720p, not 1080p -- Backdrop's blurred-blob parallax background and
  // Grain's per-frame feTurbulence filter both cost roughly proportional to
  // pixel area; 1080p measured at ~1.3-1.5 fps on real content (a 45s video
  // took 15-20 minutes to render). Still fully watchable for informal/
  // internal video use.
  width: z.number().default(1280),
  height: z.number().default(720),
  theme: z
    .object({
      bg: z.string(),
      bgAlt: z.string(),
      ink: z.string(),
      muted: z.string(),
      accent: z.string(),
      accent2: z.string(),
      fontDisplay: z.string(),
      fontBody: z.string(),
    })
    .partial()
    .optional(),
  // Confirmed by direct A/B render timing: grain alone adds ~40% to render
  // time (a full-screen procedural noise filter recomputed every frame) --
  // off by default; only worth the cost for a genuinely cinematic brief.
  grain: z.boolean().default(false),
  scenes: z.array(sceneSchema).min(1),
});

export type Storyboard = z.infer<typeof storyboardSchema>;
export type Scene = z.infer<typeof sceneSchema>;
export type Element = z.infer<typeof elementSchema>;

export const TRANSITION_DEFAULT_FRAMES = 18;

export const transitionFrames = (scene: Scene, index: number) =>
  index === 0 || !scene.transitionIn || scene.transitionIn.type === "none"
    ? 0
    : scene.transitionIn.durationInFrames ?? TRANSITION_DEFAULT_FRAMES;

/** Transitions overlap adjacent scenes, so they shorten the total. */
export const totalDuration = (sb: Storyboard) =>
  sb.scenes.reduce((sum, s, i) => sum + s.durationInFrames - transitionFrames(s, i), 0);

/** Frame where each scene starts in the final video (used by the keyframe critique loop). */
export const sceneStarts = (sb: Storyboard) => {
  let t = 0;
  return sb.scenes.map((s, i) => {
    t -= transitionFrames(s, i);
    const start = t;
    t += s.durationInFrames;
    return { id: s.id, start, end: t };
  });
};
