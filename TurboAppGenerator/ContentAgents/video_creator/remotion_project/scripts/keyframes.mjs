#!/usr/bin/env node
/**
 * Critique loop helper. Renders stills at key moments of every scene so a
 * vision model can review layout before the (slow) full render.
 *
 *   node scripts/keyframes.mjs storyboards/my-video.json          -> renders PNGs to out/keyframes/
 *   node scripts/keyframes.mjs storyboards/my-video.json --dry    -> just prints the frames
 *
 * Per scene it picks: just after entrances settle (~40%), and the hold before the exit (~90%).
 *
 * Bundles ONCE and reuses one browser instance across every still, via
 * @remotion/bundler + @remotion/renderer's own APIs, instead of shelling out
 * to a separate `remotion still` CLI process per shot -- each CLI invocation
 * pays its own full webpack-bundle + Chromium-launch cost from cold, which
 * dominated this script's real wall-clock time (a real 8-scene video's 16
 * stills took the bulk of a 20+ minute end-to-end run before this fix).
 */
import { readFileSync, mkdirSync } from "node:fs";
import { fileURLToPath } from "node:url";
import path from "node:path";
import { bundle } from "@remotion/bundler";
import { openBrowser, renderStill, selectComposition } from "@remotion/renderer";

const [file, flag] = process.argv.slice(2);
if (!file) {
  console.error("usage: node scripts/keyframes.mjs <storyboard.json> [--dry]");
  process.exit(1);
}
const sb = JSON.parse(readFileSync(file, "utf8"));

let t = 0;
const shots = [];
sb.scenes.forEach((s, i) => {
  const tf = i === 0 || !s.transitionIn || s.transitionIn.type === "none" ? 0 : s.transitionIn.durationInFrames ?? 18;
  t -= tf;
  const start = t;
  t += s.durationInFrames;

  // Sample against the scene's OWN clean window, not its raw
  // durationInFrames -- the tail end overlaps with the NEXT scene's
  // incoming transition (same overlap math as `tf` above, one scene
  // ahead), so a naive 90% "hold" sample can land inside that crossfade
  // and show both scenes blended together, confusing the critique step.
  const next = sb.scenes[i + 1];
  const nextTf = next && next.transitionIn && next.transitionIn.type !== "none"
    ? next.transitionIn.durationInFrames ?? 18 : 0;
  const cleanDuration = Math.max(1, s.durationInFrames - nextTf);
  for (const [tag, pct] of [["settled", 0.4], ["hold", 0.9]]) {
    shots.push({ scene: s.id, tag, frame: Math.round(start + cleanDuration * pct) });
  }
});

console.log(JSON.stringify({ totalFrames: t, shots }, null, 2));
if (flag === "--dry") process.exit(0);

mkdirSync("out/keyframes", { recursive: true });

const scriptDir = path.dirname(fileURLToPath(import.meta.url));
const entryPoint = path.resolve(scriptDir, "..", "src", "index.ts");

const serveUrl = await bundle({ entryPoint, onProgress: () => {} });
const browser = await openBrowser("chrome");
try {
  const composition = await selectComposition({
    serveUrl, id: "Storyboard", inputProps: sb, puppeteerInstance: browser,
  });
  for (const s of shots) {
    await renderStill({
      composition, serveUrl, puppeteerInstance: browser, inputProps: sb,
      output: `out/keyframes/${s.scene}-${s.tag}-f${s.frame}.png`,
      frame: s.frame, scale: 0.5,
    });
    console.log(`rendered ${s.scene}-${s.tag}-f${s.frame}`);
  }
} finally {
  await browser.close({ silent: true });
}
