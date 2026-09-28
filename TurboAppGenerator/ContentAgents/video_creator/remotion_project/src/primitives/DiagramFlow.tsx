import React, { Fragment } from "react";
import { Img, interpolate, staticFile, useCurrentFrame } from "remotion";
import { useSpringAt } from "../motion/useEnter";
import { typeScale } from "../motion/tokens";
import { useTheme } from "../motion/theme";
import { ICON_NAMES } from "./IconMotion";
import {
  Settings, Cog, Wrench, RefreshCw,
  Car, Truck, Bus, Bike,
  Rocket, Lightbulb,
  Globe, TrendingUp, Target, ShieldCheck, Cloud, Smartphone, Laptop, Database, Zap,
  Store, Factory, Handshake, Warehouse, Users,
} from "lucide-react";

export { ICON_NAMES };

const ICON_COMPONENTS: Record<string, React.ComponentType<{ size?: number; color?: string; strokeWidth?: number }>> = {
  Settings, Cog, Wrench, RefreshCw,
  Car, Truck, Bus, Bike,
  Rocket, Lightbulb,
  Globe, TrendingUp, Target, ShieldCheck, Cloud, Smartphone, Laptop, Database, Zap,
  Store, Factory, Handshake, Warehouse, Users,
};

// "icon" is either a plain name from ICON_NAMES, or "<provider>:<service>"
// (e.g. "aws:ec2") for a real cloud-provider glyph -- same
// "<provider>:<service>" convention as ppt_creator's icon catalog field.
export type DiagramNode = { label: string; icon: string; caption?: string };

export type DiagramFlowProps = {
  nodes: DiagramNode[]; // 2-5 nodes
  heading?: string;
  delay?: number;
};

// Frames between each node's own entrance -- staggered so the chain reads
// left-to-right as a sequence of events, not everything popping at once.
const NODE_STAGGER = 30;
// How long a connector takes to draw itself in, once triggered.
const CONNECTOR_FRAMES = 16;

const DiagramNodeChip: React.FC<{ node: DiagramNode; delay: number; ink: string; accent: string }> = ({
  node, delay, ink, accent,
}) => {
  const frame = useCurrentFrame();
  const springAt = useSpringAt();
  const popIn = springAt(delay, "snappy");
  const textOpacity = interpolate(frame, [delay + 6, delay + 20], [0, 1], {
    extrapolateLeft: "clamp", extrapolateRight: "clamp",
  });
  const isBrandIcon = node.icon.includes(":");
  const Icon = isBrandIcon ? null : ICON_COMPONENTS[node.icon] ?? Settings;

  return (
    <div style={{ display: "flex", flexDirection: "column", alignItems: "center", gap: 12, flexShrink: 0, width: 190 }}>
      {/* The tint layer is a separate absolutely-positioned sibling behind the
          icon, not a shared-opacity parent -- CSS opacity on a div also fades
          its children, which would dim the icon along with the chip tint.
          Skipped entirely for a brand icon -- a real logo shouldn't be
          tinted/boxed like a generic line icon. */}
      <div style={{ position: "relative", width: 86, height: 86, transform: `scale(${popIn})` }}>
        {!isBrandIcon && <div style={{ position: "absolute", inset: 0, borderRadius: 22, background: accent, opacity: 0.16 }} />}
        <div style={{ position: "relative", width: "100%", height: "100%", display: "flex", alignItems: "center", justifyContent: "center" }}>
          {isBrandIcon ? (
            <Img src={staticFile(`icons/${node.icon.replace(":", "/")}.svg`)} style={{ width: 56, height: 56 }} />
          ) : (
            Icon && <Icon size={40} color={accent} strokeWidth={1.75} />
          )}
        </div>
      </div>
      <div style={{ fontSize: 21, fontWeight: 700, textAlign: "center", opacity: textOpacity, lineHeight: 1.25, color: ink }}>
        {node.label}
      </div>
      {node.caption && (
        <div style={{ fontSize: 14, textAlign: "center", opacity: textOpacity * 0.75, color: ink }}>{node.caption}</div>
      )}
    </div>
  );
};

const DiagramConnector: React.FC<{ delay: number; color: string }> = ({ delay, color }) => {
  const frame = useCurrentFrame();
  const lineWidth = interpolate(frame, [delay, delay + CONNECTOR_FRAMES], [0, 46], {
    extrapolateLeft: "clamp", extrapolateRight: "clamp",
  });
  const arrowOpacity = interpolate(
    frame, [delay + CONNECTOR_FRAMES - 4, delay + CONNECTOR_FRAMES + 2], [0, 1],
    { extrapolateLeft: "clamp", extrapolateRight: "clamp" },
  );
  return (
    // Sits at chip-icon-center height (half of the chip's 86px icon box), not
    // the chip+label's full height, so it lines up with the icons.
    <div style={{ display: "flex", alignItems: "center", flexShrink: 0, height: 86, marginTop: -34 }}>
      <div style={{ width: lineWidth, height: 3, background: color, opacity: 0.7 }} />
      <div
        style={{
          width: 0, height: 0, opacity: arrowOpacity, marginLeft: -1,
          borderTop: "5px solid transparent", borderBottom: "5px solid transparent", borderLeft: `7px solid ${color}`,
        }}
      />
    </div>
  );
};

/**
 * A left-to-right chain of icon+label nodes connected by drawn-in arrows --
 * for a process, sequence of steps, pipeline, or the players in a flow.
 */
export const DiagramFlow: React.FC<DiagramFlowProps> = ({ nodes, heading, delay = 0 }) => {
  const frame = useCurrentFrame();
  const theme = useTheme();
  const items = nodes.slice(0, 5);
  const headingOpacity = interpolate(frame, [delay, delay + 12], [0, 1], { extrapolateLeft: "clamp", extrapolateRight: "clamp" });

  return (
    <div style={{ display: "flex", flexDirection: "column", alignItems: "center", fontFamily: theme.fontBody }}>
      {heading && (
        <div style={{ fontSize: typeScale.heading, fontWeight: 700, opacity: headingOpacity, marginBottom: 44, textAlign: "center", color: theme.ink }}>
          {heading}
        </div>
      )}
      <div style={{ display: "flex", alignItems: "flex-start", justifyContent: "center" }}>
        {items.map((node, i) => (
          <Fragment key={i}>
            <DiagramNodeChip node={node} delay={delay + i * NODE_STAGGER} ink={theme.ink} accent={theme.accent} />
            {i < items.length - 1 && <DiagramConnector delay={delay + i * NODE_STAGGER + 22} color={theme.accent} />}
          </Fragment>
        ))}
      </div>
    </div>
  );
};
