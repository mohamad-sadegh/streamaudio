import { useEffect, useRef, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { Auth, Publishers } from "../api.js";
import { startWhep } from "../whep.js";
import AudioVisualizer from "../components/AudioVisualizer.jsx";

export default function ListenPage({ user, onLogout }) {
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
        if (!found) setError("Publisher not found");
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
            setError("Connection lost");
          }
        },
      });
      sessionRef.current = session;
      setStatus("connected");
    } catch (err) {
      setStatus("idle");
      setError(err.message || "Failed to connect");
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

  async function logout() {
    await disconnect();
    await Auth.logout().catch(() => {});
    onLogout();
  }

  const live = status === "connected" || status === "connecting";

  return (
    <div className="app-shell listen-shell">
      <header className="topbar">
        <div>
          <p className="brand">StreamAudio</p>
          <p className="muted small">
            <Link to="/">← Publishers</Link> · {user.username}
          </p>
        </div>
        <button type="button" className="ghost" onClick={logout}>
          Sign out
        </button>
      </header>

      <main className="listen-stage">
        <div className="listen-hero">
          <div className="live-meta">
            <span className={`live-pill ${live ? "hot" : ""}`}>
              {live ? "LIVE" : "STANDBY"}
            </span>
            <h1>{publisher?.label || publisher?.username || "Stream"}</h1>
            <p className="mono muted">{publisher?.streamPath || "…"}</p>
          </div>

          <AudioVisualizer stream={stream} active={Boolean(stream)} />

          <audio ref={audioElRef} autoPlay playsInline />

          <div className="listen-controls">
            {status === "idle" || status === "failed" || status === "disconnected" ? (
              <button type="button" onClick={connect} disabled={!publisher}>
                Start listening
              </button>
            ) : (
              <button type="button" className="danger" onClick={disconnect}>
                Stop
              </button>
            )}
            <span className="muted small">Status: {status}</span>
          </div>

          {error ? <p className="error">{error}</p> : null}
        </div>
      </main>
    </div>
  );
}
