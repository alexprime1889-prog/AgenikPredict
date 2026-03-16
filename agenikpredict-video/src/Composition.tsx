import {
  AbsoluteFill,
  Img,
  OffthreadVideo,
  Sequence,
  interpolate,
  staticFile,
  useCurrentFrame,
} from "remotion";

const FPS = 30;

const FadeInSlide: React.FC<{ src: string }> = ({ src }) => {
  const frame = useCurrentFrame();
  const opacity = interpolate(frame, [0, 8, 82, 90], [0, 1, 1, 0], {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
  });
  const scale = interpolate(frame, [0, 8], [1.05, 1], {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
  });

  return (
    <AbsoluteFill
      style={{
        justifyContent: "center",
        alignItems: "center",
        backgroundColor: "rgba(0,0,0,0.75)",
        opacity,
      }}
    >
      <Img
        src={src}
        style={{
          width: "85%",
          height: "auto",
          transform: `scale(${scale})`,
        }}
      />
    </AbsoluteFill>
  );
};

export const MyComposition = () => {
  return (
    <AbsoluteFill style={{ backgroundColor: "#0C0C0C" }}>
      {/* Base video — plays the entire duration */}
      <OffthreadVideo src={staticFile("hr-video.mp4")} />

      {/* Slide 1: $500K cost — 0:00 to 0:05 (frames 0-150) */}
      <Sequence from={30} durationInFrames={90}>
        <FadeInSlide src={staticFile("hr-slide-1-cost.png")} />
      </Sequence>

      {/* Slide 2: Team simulation — 0:12 to 0:20 (frames 360-600) */}
      <Sequence from={360} durationInFrames={180}>
        <FadeInSlide src={staticFile("hr-slide-2-simulation.png")} />
      </Sequence>

      {/* Slide 3: 73% conflict report — 0:20 to 0:27 (frames 600-810) */}
      <Sequence from={600} durationInFrames={180}>
        <FadeInSlide src={staticFile("hr-slide-3-report.png")} />
      </Sequence>

      {/* Slide 4: $30K vs $5 — 0:27 to 0:32 (frames 810-960) */}
      <Sequence from={810} durationInFrames={150}>
        <FadeInSlide src={staticFile("hr-slide-4-price.png")} />
      </Sequence>
    </AbsoluteFill>
  );
};
