import { useCallback, useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { Publishers } from "../api.js";
import SecretQrCode, { buildPublishSharePayload } from "../components/SecretQrCode.jsx";

export default function PublishersPage() {
  const [publishers, setPublishers] = useState([]);
  const [username, setUsername] = useState("");
  const [label, setLabel] = useState("");
  const [error, setError] = useState("");
  const [secretReveal, setSecretReveal] = useState(null);
  const [busy, setBusy] = useState(false);

  const refresh = useCallback(async () => {
    const data = await Publishers.list();
    setPublishers(data.publishers || []);
  }, []);

  useEffect(() => {
    refresh().catch((err) => setError(err.message));
    const t = setInterval(() => {
      refresh().catch(() => {});
    }, 5000);
    return () => clearInterval(t);
  }, [refresh]);

  async function createPublisher(e) {
    e.preventDefault();
    setBusy(true);
    setError("");
    try {
      const data = await Publishers.create(username, label);
      setSecretReveal(data.publisher);
      setUsername("");
      setLabel("");
      await refresh();
    } catch (err) {
      setError(err.message);
    } finally {
      setBusy(false);
    }
  }

  async function rotate(id) {
    if (!confirm("Rotate stream secret? The old secret stops working immediately.")) {
      return;
    }
    try {
      const data = await Publishers.rotate(id);
      setSecretReveal(data.publisher);
      await refresh();
    } catch (err) {
      setError(err.message);
    }
  }

  async function toggle(pub) {
    try {
      await Publishers.update(pub.id, { enabled: !pub.enabled });
      await refresh();
    } catch (err) {
      setError(err.message);
    }
  }

  async function remove(id) {
    if (!confirm("Delete this publisher permanently?")) return;
    try {
      await Publishers.remove(id);
      await refresh();
    } catch (err) {
      setError(err.message);
    }
  }

  return (
    <main className="page">
      <section className="panel">
        <h1>Publishers</h1>
        <p className="muted">
          Create credentials for devices that publish live audio. Only admins can
          listen.
        </p>

        <form className="create-form" onSubmit={createPublisher}>
          <input
            placeholder="username"
            value={username}
            onChange={(e) => setUsername(e.target.value)}
            required
          />
          <input
            placeholder="label (optional)"
            value={label}
            onChange={(e) => setLabel(e.target.value)}
          />
          <button type="submit" disabled={busy}>
            Create access
          </button>
        </form>

        {error ? <p className="error">{error}</p> : null}

        {secretReveal?.secret ? (
          <div className="secret-banner">
            <div className="secret-banner-main">
              <strong>Copy now — secret is shown once</strong>
              <p className="muted small">
                Scan the QR with the Android app, or copy the values below.
              </p>
              <p>
                User: <code>{secretReveal.username}</code>
              </p>
              <p>
                Secret: <code>{secretReveal.secret}</code>
              </p>
              <p>
                WHIP: <code>{secretReveal.whipUrl}</code>
              </p>
              <button type="button" className="ghost" onClick={() => setSecretReveal(null)}>
                Dismiss
              </button>
            </div>
            <div className="secret-banner-qr">
              <SecretQrCode value={buildPublishSharePayload(secretReveal)} />
              <p className="muted small">Scan to share</p>
            </div>
          </div>
        ) : null}

        <div className="table">
          {publishers.length === 0 ? (
            <p className="muted">No publishers yet.</p>
          ) : (
            publishers.map((pub) => (
              <article key={pub.id} className="row">
                <div className="row-main">
                  <div className="row-title">
                    <span
                      className={`dot ${pub.online ? "on" : "off"}`}
                      title={pub.online ? "Live" : "Offline"}
                    />
                    <strong>{pub.username}</strong>
                    {pub.label ? <span className="tag">{pub.label}</span> : null}
                    {!pub.enabled ? <span className="tag warn">disabled</span> : null}
                  </div>
                  <p className="mono muted small">{pub.streamPath}</p>
                </div>
                <div className="row-actions">
                  <Link className="btn-link" to={`/listen/${pub.id}`}>
                    Listen
                  </Link>
                  <button type="button" className="ghost" onClick={() => toggle(pub)}>
                    {pub.enabled ? "Disable" : "Enable"}
                  </button>
                  <button type="button" className="ghost" onClick={() => rotate(pub.id)}>
                    Rotate
                  </button>
                  <button type="button" className="danger" onClick={() => remove(pub.id)}>
                    Delete
                  </button>
                </div>
              </article>
            ))
          )}
        </div>
      </section>
    </main>
  );
}
