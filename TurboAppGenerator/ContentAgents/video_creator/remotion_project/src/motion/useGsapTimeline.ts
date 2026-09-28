import { useLayoutEffect, useRef } from "react";
import { useCurrentFrame, useVideoConfig } from "remotion";
import gsap from "gsap";

/**
 * Bridge GSAP into Remotion. GSAP builds a paused timeline; Remotion owns time
 * and seeks it to the current frame, so renders stay deterministic.
 * Selectors inside `build` are scoped to the returned ref's element.
 *
 *   const scope = useGsapTimeline((tl) => {
 *     tl.from(".char", { y: 80, opacity: 0, stagger: 0.03, ease: "back.out(2)" });
 *   });
 *   return <div ref={scope}>...</div>;
 */
export const useGsapTimeline = (build: (tl: gsap.core.Timeline) => void, delayFrames = 0) => {
  const scope = useRef<HTMLDivElement>(null);
  const tl = useRef<gsap.core.Timeline | null>(null);
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();

  useLayoutEffect(() => {
    const ctx = gsap.context(() => {
      const timeline = gsap.timeline({ paused: true });
      build(timeline);
      tl.current = timeline;
    }, scope.current ?? undefined);
    return () => ctx.revert();
    // Build once: the timeline is a pure function of time.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  useLayoutEffect(() => {
    tl.current?.seek(Math.max(0, (frame - delayFrames) / fps), false);
  }, [frame, fps, delayFrames]);

  return scope;
};
