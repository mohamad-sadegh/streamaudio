import { useEffect, useRef } from "react";

export default function AudioVisualizer({ stream, active }) {
  const canvasRef = useRef(null);
  const rafRef = useRef(0);
  const audioRef = useRef(null);

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return undefined;

    const ctx = canvas.getContext("2d");
    let analyser = null;
    let source = null;
    let audioCtx = null;
    let data = null;

    const size = () => ({
      width: canvas.clientWidth || 1,
      height: canvas.clientHeight || 1,
    });

    const drawIdle = () => {
      const { width, height } = size();
      ctx.clearRect(0, 0, width, height);
      const bars = 48;
      const gap = 4;
      const barW = (width - gap * (bars - 1)) / bars;
      for (let i = 0; i < bars; i++) {
        const h = 4 + Math.sin(Date.now() / 600 + i * 0.2) * 2;
        const x = i * (barW + gap);
        const y = (height - h) / 2;
        ctx.fillStyle = "rgba(120, 160, 150, 0.25)";
        ctx.fillRect(x, y, barW, h);
      }
      rafRef.current = requestAnimationFrame(drawIdle);
    };

    const drawLive = () => {
      const { width, height } = size();
      analyser.getByteFrequencyData(data);
      ctx.clearRect(0, 0, width, height);

      const bars = 64;
      const step = Math.floor(data.length / bars);
      const gap = 3;
      const barW = (width - gap * (bars - 1)) / bars;

      for (let i = 0; i < bars; i++) {
        const v = data[i * step] / 255;
        const h = Math.max(3, v * height * 0.92);
        const x = i * (barW + gap);
        const y = (height - h) / 2;
        const g = ctx.createLinearGradient(0, y, 0, y + h);
        g.addColorStop(0, "#7dffb3");
        g.addColorStop(0.5, "#2ec4a2");
        g.addColorStop(1, "#1a6b5c");
        ctx.fillStyle = g;
        ctx.fillRect(x, y, barW, h);
      }
      rafRef.current = requestAnimationFrame(drawLive);
    };

    const resize = () => {
      const rect = canvas.parentElement.getBoundingClientRect();
      canvas.width = Math.floor(rect.width * devicePixelRatio);
      canvas.height = Math.floor(rect.height * devicePixelRatio);
      ctx.setTransform(devicePixelRatio, 0, 0, devicePixelRatio, 0, 0);
      canvas.style.width = `${rect.width}px`;
      canvas.style.height = `${rect.height}px`;
    };

    resize();
    window.addEventListener("resize", resize);

    if (active && stream) {
      audioCtx = new AudioContext();
      analyser = audioCtx.createAnalyser();
      analyser.fftSize = 256;
      analyser.smoothingTimeConstant = 0.75;
      source = audioCtx.createMediaStreamSource(stream);
      source.connect(analyser);
      // Keep audible via hidden audio element; analyser taps the same stream
      data = new Uint8Array(analyser.frequencyBinCount);
      drawLive();
    } else {
      drawIdle();
    }

    audioRef.current = { audioCtx, source };

    return () => {
      cancelAnimationFrame(rafRef.current);
      window.removeEventListener("resize", resize);
      try {
        source?.disconnect();
        audioCtx?.close();
      } catch {
        /* ignore */
      }
    };
  }, [stream, active]);

  return (
    <div className="visualizer">
      <canvas ref={canvasRef} />
    </div>
  );
}
