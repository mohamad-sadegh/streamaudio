import { useCallback, useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { Publishers } from "../api.js";
import SecretQrCode, { buildPublishSharePayload } from "../components/SecretQrCode.jsx";

const MODE_LABELS = {
  idle: "آماده",
  streaming: "استریم",
  recording: "ضبط",
};

function modeLabel(mode) {
  return MODE_LABELS[mode] || mode || "آماده";
}

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
    if (!confirm("رمز استریم عوض شود؟ رمز قبلی فوراً از کار می‌افتد.")) {
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
    if (!confirm("این ناشر برای همیشه حذف شود؟")) return;
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
        <h1>ناشران</h1>
        <p className="muted">
          برای دستگاه‌هایی که صدای زنده منتشر می‌کنند، اعتبارنامه بسازید. مدیریت استریم،
          ضبط، ورودی‌ها و شنیدن از صفحهٔ هر گوشی انجام می‌شود.
        </p>

        <form className="create-form" onSubmit={createPublisher}>
          <input
            placeholder="نام کاربری"
            value={username}
            onChange={(e) => setUsername(e.target.value)}
            required
          />
          <input
            placeholder="برچسب (اختیاری)"
            value={label}
            onChange={(e) => setLabel(e.target.value)}
          />
          <button type="submit" disabled={busy}>
            ایجاد دسترسی
          </button>
        </form>

        {error ? <p className="error">{error}</p> : null}

        {secretReveal?.secret ? (
          <div className="secret-banner">
            <div className="secret-banner-main">
              <strong>همین حالا کپی کنید — رمز فقط یک‌بار نمایش داده می‌شود</strong>
              <p className="muted small">
                در اپ اندروید QR را اسکن کنید، یا «کپی لینک اشتراک» را بزنید و در اپ
                بچسبانید.
              </p>
              <p>
                کاربر: <code className="mono">{secretReveal.username}</code>
              </p>
              <p>
                رمز: <code className="mono">{secretReveal.secret}</code>
              </p>
              <p>
                WHIP: <code className="mono">{secretReveal.whipUrl}</code>
              </p>
              <button type="button" className="ghost" onClick={() => setSecretReveal(null)}>
                بستن
              </button>
            </div>
            <div className="secret-banner-qr">
              <SecretQrCode value={buildPublishSharePayload(secretReveal)} />
              <p className="muted small">اسکن برای اشتراک</p>
            </div>
          </div>
        ) : null}

        <div className="table">
          {publishers.length === 0 ? (
            <p className="muted">هنوز ناشری نیست.</p>
          ) : (
            publishers.map((pub) => (
              <article key={pub.id} className="row">
                <div className="row-main">
                  <div className="row-title">
                    <span
                      className={`dot ${pub.online ? "on" : "off"}`}
                      title={pub.online ? "زنده روی مدیا" : "بدون انتشار مدیا"}
                    />
                    <strong>{pub.username}</strong>
                    {pub.label ? <span className="tag">{pub.label}</span> : null}
                    {!pub.enabled ? <span className="tag warn">غیرفعال</span> : null}
                    <span
                      className={`tag ${pub.deviceConnected ? "ok" : ""}`}
                      title="اتصال سرویس کنترل گوشی"
                    >
                      {pub.deviceConnected ? "دستگاه وصل" : "دستگاه قطع"}
                    </span>
                    <span className="tag">مطلوب: {modeLabel(pub.desiredMode)}</span>
                    <span className="tag">واقعی: {modeLabel(pub.actualMode)}</span>
                    {(pub.selectedInputs || []).length > 0 ? (
                      <span className="tag">
                        {(pub.selectedInputs || []).length} ورودی
                      </span>
                    ) : null}
                  </div>
                  <p className="mono muted small">{pub.streamPath}</p>
                  {pub.deviceLastError ? (
                    <p className="error small">{pub.deviceLastError}</p>
                  ) : null}
                </div>
                <div className="row-actions">
                  <Link className="btn-link" to={`/publishers/${pub.id}`}>
                    مدیریت
                  </Link>
                  <button type="button" className="ghost" onClick={() => toggle(pub)}>
                    {pub.enabled ? "غیرفعال کردن" : "فعال کردن"}
                  </button>
                  <button type="button" className="ghost" onClick={() => rotate(pub.id)}>
                    تعویض رمز
                  </button>
                  <button type="button" className="danger" onClick={() => remove(pub.id)}>
                    حذف
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
