import { useEffect, useRef, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { Publishers } from "../api.js";
import { startWhep } from "../whep.js";
import AudioVisualizer from "../components/AudioVisualizer.jsx";

const STATUS_LABELS = {
  idle: "آماده",
  connecting: "در حال اتصال",
  connected: "متصل",
  failed: "ناموفق",
  disconnected: "قطع‌شده",
};

export default function ListenPage() {
  const { id } = useParams();
  const [publisher, setPublisher] = useState(null);
  const [stream, setStream] = useState(null);
  const [status, setStatus] = useState("idle");
  const [error, setError] = useState("");
  const sessionRef = useRef(null);
  const audioElRef = useRef(null);

  useEffect(() => {
    Publishers.list()
      .then((data) => {
        const found = (data.publishers || []).find((p) => p.id === id);
        setPublisher(found || null);
        if (!found) setError("ناشر پیدا نشد");
      })
      .catch((err) => setError(err.message));
  }, [id]);

  useEffect(() => {
    return () => {
      sessionRef.current?.stop();
      sessionRef.current = null;
    };
  }, []);

  async function connect() {
    setError("");
    setStatus("connecting");
    try {
      await sessionRef.current?.stop();
      sessionRef.current = null;
      setStream(null);

      const tokenData = await Publishers.listenToken(id);
      const session = await startWhep({
        whepUrl: tokenData.whepUrl,
        authorization: tokenData.authorization,
        onTrack: (mediaStream) => {
          setStream(mediaStream);
          if (audioElRef.current) {
            audioElRef.current.srcObject = mediaStream;
            audioElRef.current.play().catch(() => {});
          }
        },
        onConnectionState: (state) => {
          setStatus(state);
          if (state === "failed" || state === "disconnected") {
            setError("اتصال قطع شد");
          }
        },
      });
      sessionRef.current = session;
      setStatus("connected");
    } catch (err) {
      setStatus("idle");
      setError(err.message || "اتصال برقرار نشد");
    }
  }

  async function disconnect() {
    await sessionRef.current?.stop();
    sessionRef.current = null;
    setStream(null);
    setStatus("idle");
    if (audioElRef.current) {
      audioElRef.current.srcObject = null;
    }
  }

  const live = status === "connected" || status === "connecting";

  return (
    <main className="page listen-page">
      <p className="muted small">
        <Link to="/publishers">ناشران ←</Link>
      </p>

      <div className="listen-hero">
        <div className="live-meta">
          <span className={`live-pill ${live ? "hot" : ""}`}>
            {live ? "زنده" : "آماده"}
          </span>
          <h1>{publisher?.label || publisher?.username || "استریم"}</h1>
          <p className="mono muted">{publisher?.streamPath || "…"}</p>
        </div>

        <AudioVisualizer stream={stream} active={Boolean(stream)} />

        <audio ref={audioElRef} autoPlay playsInline />

        <div className="listen-controls">
          {status === "idle" || status === "failed" || status === "disconnected" ? (
            <button type="button" onClick={connect} disabled={!publisher}>
              شروع گوش دادن
            </button>
          ) : (
            <button type="button" className="danger" onClick={disconnect}>
              توقف
            </button>
          )}
          <span className="muted small">
            وضعیت: {STATUS_LABELS[status] || status}
          </span>
        </div>

        {error ? <p className="error">{error}</p> : null}
      </div>
    </main>
  );
}
