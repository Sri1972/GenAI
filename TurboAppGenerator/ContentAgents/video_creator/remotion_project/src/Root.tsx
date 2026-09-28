import React from "react";
import { Composition, type CalculateMetadataFunction } from "remotion";
import { StoryboardVideo } from "./storyboard/StoryboardVideo";
import { storyboardSchema, totalDuration, type Storyboard } from "./storyboard/schema";
import sample from "../storyboards/sample.json";

const calculateMetadata: CalculateMetadataFunction<Storyboard> = ({ props }) => {
  const sb = storyboardSchema.parse(props);
  return { durationInFrames: totalDuration(sb), fps: sb.fps, width: sb.width, height: sb.height };
};

export const RemotionRoot: React.FC = () => (
  <Composition
    id="Storyboard"
    component={StoryboardVideo}
    defaultProps={sample as unknown as Storyboard}
    // Duration/fps/size come from the storyboard itself (video_creator/run.py
    // passes one via --props for every real render), not fixed values here.
    calculateMetadata={calculateMetadata}
    durationInFrames={300}
    fps={30}
    width={1280}
    height={720}
  />
);
