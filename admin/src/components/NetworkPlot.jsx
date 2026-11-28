import { useEffect, useMemo, useRef } from "react";

const SLOT_COLORS = [
  "#2ec4a2",
  "#7dffb3",
  "#5b8def",
  "#e6b35a",
  "#ff6b6b",
  "#c084fc",
  "#22d3ee",
  "#f472b6",
];

export default function NetworkPlot({ telemetry = [], height = 180 }) {
  const canvasRef = useRef(null);

  const series = useMemo(() => {
    const bySlot = new Map();
    for (const point of telemetry) {
      const slot = Number(point.slot ?? 0);
      if (!bySlot.has(slot)) bySlot.set(slot, []);
      bySlot.get(slot).push(point);
    }
    return [...bySlot.entries()]
      .sort((a, b) => a[0] - b[0])
      .map(([slot, points]) => ({
        slot,
        points: points.slice(-90),
        color: SLOT_COLORS[slot % SLOT_COLORS.length],
      }));
  }, [telemetry]);

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const ctx = canvas.getContext("2d");
    if (!ctx) return;

    const dpr = window.devicePixelRatio || 1;
    const width = canvas.clientWidth || 640;
    canvas.width = Math.floor(width * dpr);
    canvas.height = Math.floor(height * dpr);
    ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
    ctx.clearRect(0, 0, width, height);

    const styles = getComputedStyle(document.documentElement);
    const muted = styles.getPropertyValue("--muted").trim() || "#8aa399";
    const line = styles.getPropertyValue("--line").trim() || "rgba(126,180,160,0.18)";
    const ink = styles.getPropertyValue("--ink").trim() || "#e8f2ee";

    ctx.fillStyle = "transparent";
    ctx.fillRect(0, 0, width, height);

    // Grid
    ctx.strokeStyle = line;
    ctx.lineWidth = 1;
    for (let i = 1; i <= 3; i += 1) {
      const y = (height / 4) * i;
      ctx.beginPath();
      ctx.moveTo(0, y);
      ctx.lineTo(width, y);
      ctx.stroke();
    }

    const allPoints = series.flatMap((s) => s.points);
    if (allPoints.length < 2) {
      ctx.fillStyle = muted;
      ctx.font = "13px Vazirmatn, Tahoma, sans-serif";
      ctx.textAlign = "center";
      ctx.fillText("در انتظار داده شبکه…", width / 2, height / 2);
      return;
    }

    const maxBitrate = Math.max(
      32,
      ...allPoints.map((p) => Number(p.bitrateKbps) || 0),
    );
    const pad = 8;

    for (const s of series) {
      if (s.points.length < 2) continue;
      ctx.strokeStyle = s.color;
      ctx.lineWidth = 2;
      ctx.beginPath();
      s.points.forEach((p, i) => {
        const x =
          pad + ((width - pad * 2) * i) / Math.max(1, s.points.length - 1);
        const y =
          height -
          pad -
          ((Number(p.bitrateKbps) || 0) / maxBitrate) * (height - pad * 2);
        if (i === 0) ctx.moveTo(x, y);
        else ctx.lineTo(x, y);
      });
      ctx.stroke();
    }

    ctx.fillStyle = muted;
    ctx.font = "11px Vazirmatn, Tahoma, sans-serif";
    ctx.textAlign = "left";
    ctx.fillText(`${Math.round(maxBitrate)} kbps`, 6, 14);

    // Legend
    let lx = width - 8;
    ctx.textAlign = "right";
    for (const s of series) {
      const label = `اسلات ${s.slot}`;
      ctx.fillStyle = s.color;
      ctx.fillText(label, lx, 14);
      lx -= ctx.measureText(label).width + 14;
    }

    // Latest RTT hint
    const last = allPoints[allPoints.length - 1];
    if (last && Number(last.rttMs) > 0) {
      ctx.fillStyle = ink;
      ctx.textAlign = "left";
      ctx.fillText(`RTT ${Math.round(last.rttMs)} ms`, 6, height - 8);
    }
  }, [series, height]);

  return (
    <div className="network-plot">
      <canvas ref={canvasRef} style={{ width: "100%", height }} />
    </div>
  );
}
