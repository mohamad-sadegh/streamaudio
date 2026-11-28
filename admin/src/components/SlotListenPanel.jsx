import { useEffect, useRef, useState } from "react";
import { Publishers } from "../api.js";
import { startWhep } from "../whep.js";
import AudioVisualizer from "./AudioVisualizer.jsx";

export default function SlotListenPanel({ publisherId, slot, label, active }) {
  const [stream, setStream] = useState(null);
  const [status, setStatus] = useState("idle");
  const [error, setError] = useState("");
  const sessionRef = useRef(null);
  const audioElRef = useRef(null);

  useEffect(() => {
    return () => {
      sessionRef.current?.stop();
      sessionRef.current = null;
    };
  }, []);

  useEffect(() => {
    if (!active && sessionRef.current) {
      sessionRef.current.stop();
      sessionRef.current = null;
      setStream(null);
      setStatus("idle");
    }
  }, [active]);

  async function connect() {
    setError("");
    setStatus("connecting");
    try {
      await sessionRef.current?.stop();
      sessionRef.current = null;
      setStream(null);

      const tokenData = await Publishers.listenToken(publisherId, slot);
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
    <div className={`slot-listen ${live ? "hot" : ""}`}>
      <div className="slot-listen-head">
        <strong>
          گوش دادن · اسلات {slot}
          {label ? ` · ${label}` : ""}
        </strong>
        <span className={`live-pill ${live ? "hot" : ""}`}>
          {live ? "زنده" : "آماده"}
        </span>
      </div>
      <AudioVisualizer stream={stream} active={Boolean(stream)} compact />
      <audio ref={audioElRef} autoPlay playsInline />
      <div className="slot-listen-actions">
        {status === "idle" || status === "failed" || status === "disconnected" ? (
          <button type="button" className="ghost" onClick={connect} disabled={!active}>
            شروع گوش دادن
          </button>
        ) : (
          <button type="button" className="danger" onClick={disconnect}>
            توقف گوش دادن
          </button>
        )}
      </div>
      {error ? <p className="error small">{error}</p> : null}
    </div>
  );
}
