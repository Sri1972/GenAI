import React from "react";
import { AbsoluteFill, staticFile } from "remotion";
import { Audio } from "@remotion/media";
import { TransitionSeries, springTiming, type TransitionPresentation } from "@remotion/transitions";
import { fade } from "@remotion/transitions/fade";
import { slide } from "@remotion/transitions/slide";
import { wipe } from "@remotion/transitions/wipe";
import { flip } from "@remotion/transitions/flip";
import { CameraMotionBlur } from "@remotion/motion-blur";
import { loadFont } from "@remotion/google-fonts/Sora";
import { ThemeProvider } from "../motion/theme";
import { springs } from "../motion/tokens";
import { Backdrop } from "../primitives/Backdrop";
import { Grain } from "../primitives/Grain";
import { CameraPush } from "../primitives/CameraPush";
import { KineticTitle } from "../primitives/KineticTitle";
import { StaggerList } from "../primitives/StaggerList";
import { CountUp } from "../primitives/CountUp";
import { ChartBuild } from "../primitives/ChartBuild";
import { DrawPath } from "../primitives/DrawPath";
import { GsapTextBurst } from "../primitives/GsapTextBurst";
import { PeopleCrowd } from "../primitives/PeopleCrowd";
import { IconMotion } from "../primitives/IconMotion";
import { DiagramFlow } from "../primitives/DiagramFlow";
import { BrandIcon } from "../primitives/BrandIcon";
import { AnimatedGif } from "../primitives/AnimatedGif";
import { storyboardSchema, transitionFrames, type Element, type Scene, type Storyboard } from "./schema";

// Must match video_creator/run.py's NARRATION_DIR_NAME.
const NARRATION_DIR = "narration";

loadFont("normal", { weights: ["400", "500", "600", "700", "800"], subsets: ["latin"] });

const renderElement = (el: Element, key: number) => {
  switch (el.type) {
    case "kineticTitle": {
      const { type, ...p } = el;
      return <KineticTitle key={key} {...p} />;
    }
    case "staggerList": {
      const { type, ...p } = el;
      return <StaggerList key={key} {...p} />;
    }
    case "countUp": {
      const { type, ...p } = el;
      return <CountUp key={key} {...p} />;
    }
    case "chartBuild": {
      const { type, ...p } = el;
      return <ChartBuild key={key} {...p} />;
    }
    case "drawPath": {
      const { type, ...p } = el;
      return <DrawPath key={key} {...p} />;
    }
    case "gsapTextBurst": {
      const { type, ...p } = el;
      return <GsapTextBurst key={key} {...p} />;
    }
    case "peopleCrowd": {
      const { type, ...p } = el;
      return <PeopleCrowd key={key} {...p} />;
    }
    case "iconMotion": {
      const { type, ...p } = el;
      return <IconMotion key={key} {...p} />;
    }
    case "diagramFlow": {
      const { type, ...p } = el;
      return <DiagramFlow key={key} {...p} />;
    }
    case "brandIcon": {
      const { type, ...p } = el;
      return <BrandIcon key={key} {...p} />;
    }
    case "animatedGif": {
      const { type, ...p } = el;
      return <AnimatedGif key={key} {...p} />;
    }
  }
};

const layoutStyle: Record<Scene["layout"], React.CSSProperties> = {
  center: { flexDirection: "column", alignItems: "center", justifyContent: "center", gap: 56, textAlign: "center" },
  stack: { flexDirection: "column", alignItems: "flex-start", justifyContent: "center", gap: 48, padding: "0 180px" },
  row: { flexDirection: "row", alignItems: "center", justifyContent: "space-evenly", padding: "0 120px" },
  split: { display: "grid", gridTemplateColumns: "1.15fr 1fr", alignItems: "center", gap: 90, padding: "0 140px" },
};

const SceneView: React.FC<{ scene: Scene }> = ({ scene }) => {
  const content = (
    <AbsoluteFill style={{ display: "flex", ...layoutStyle[scene.layout] }}>
      {scene.layout === "split" ? (
        <>
          <div style={{ minWidth: 0 }}>{renderElement(scene.elements[0], 0)}</div>
          <div style={{ display: "flex", flexDirection: "column", gap: 48, minWidth: 0 }}>
            {scene.elements.slice(1).map((el, i) => renderElement(el, i + 1))}
          </div>
        </>
      ) : (
        scene.elements.map(renderElement)
      )}
    </AbsoluteFill>
  );
  const withCamera =
    scene.camera === false ? content : (
      <CameraPush durationInFrames={scene.durationInFrames} {...(scene.camera ?? {})}>
        {content}
      </CameraPush>
    );
  return (
    <AbsoluteFill>
      <Backdrop seed={scene.id} />
      {scene.motionBlur ? (
        <CameraMotionBlur shutterAngle={180} samples={8}>
          {withCamera}
        </CameraMotionBlur>
      ) : (
        withCamera
      )}
      {scene.narrationFile && <Audio src={staticFile(`${NARRATION_DIR}/${scene.narrationFile}`)} />}
    </AbsoluteFill>
  );
};

// eslint-disable-next-line @typescript-eslint/no-explicit-any
const presentationFor = (t: NonNullable<Scene["transitionIn"]>): TransitionPresentation<any> => {
  const direction = t.direction ?? "from-right";
  switch (t.type) {
    case "slide":
      return slide({ direction }) as TransitionPresentation<any>;
    case "wipe":
      return wipe({ direction }) as TransitionPresentation<any>;
    case "flip":
      return flip({ direction }) as TransitionPresentation<any>;
    default:
      return fade() as TransitionPresentation<any>;
  }
};

export const StoryboardVideo: React.FC<Storyboard> = (props) => {
  const sb = storyboardSchema.parse(props);
  return (
    <ThemeProvider theme={sb.theme}>
      <AbsoluteFill>
        <TransitionSeries>
          {sb.scenes.map((scene, i) => {
            const tf = transitionFrames(scene, i);
            return (
              <React.Fragment key={scene.id}>
                {tf > 0 && scene.transitionIn && (
                  <TransitionSeries.Transition
                    presentation={presentationFor(scene.transitionIn)}
                    timing={springTiming({ config: springs.gentle, durationInFrames: tf, durationRestThreshold: 0.001 })}
                  />
                )}
                <TransitionSeries.Sequence durationInFrames={scene.durationInFrames}>
                  <SceneView scene={scene} />
                </TransitionSeries.Sequence>
              </React.Fragment>
            );
          })}
        </TransitionSeries>
        {sb.grain && <Grain />}
      </AbsoluteFill>
    </ThemeProvider>
  );
};
