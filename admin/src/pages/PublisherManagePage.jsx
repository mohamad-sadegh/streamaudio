import { useCallback, useEffect, useMemo, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { Publishers } from "../api.js";
import NetworkPlot from "../components/NetworkPlot.jsx";
import SlotListenPanel from "../components/SlotListenPanel.jsx";

const MODE_LABELS = {
  idle: "آماده",
  streaming: "استریم",
  recording: "ضبط",
};

function modeLabel(mode) {
  return MODE_LABELS[mode] || mode || "آماده";
}

export default function PublisherManagePage() {
  const { id } = useParams();
  const [publisher, setPublisher] = useState(null);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const [slotBusy, setSlotBusy] = useState(null);
  const [draftDeviceIds, setDraftDeviceIds] = useState([]);

  const refresh = useCallback(async () => {
    const data = await Publishers.get(id);
    setPublisher(data.publisher);
  }, [id]);

  useEffect(() => {
    refresh().catch((err) => setError(err.message));
    const t = setInterval(() => {
      refresh().catch(() => {});
    }, 1000);
    return () => clearInterval(t);
  }, [refresh]);

  useEffect(() => {
    if (!publisher) return;
    setDraftDeviceIds((publisher.selectedInputs || []).map((s) => s.deviceId));
    // Only reseat draft when publisher identity changes (not every poll).
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [publisher?.id]);

  const available = publisher?.availableInputs || [];
  const selected = publisher?.selectedInputs || [];
  const actualBySlot = useMemo(() => {
    const map = new Map();
    for (const item of publisher?.actualInputs || []) {
      map.set(item.slot, item);
    }
    return map;
  }, [publisher?.actualInputs]);

  const maxInputs = publisher?.maxInputs || 8;

  async function saveInputs(nextIds) {
    setBusy(true);
    setError("");
    try {
      const prevByDevice = new Map(
        (publisher?.selectedInputs || []).map((s) => [s.deviceId, s]),
      );
      const inputs = nextIds.slice(0, maxInputs).map((deviceId, index) => {
        const device = available.find((d) => d.id === deviceId);
        const prev = prevByDevice.get(deviceId);
        return {
          deviceId,
          slot: prev?.slot ?? index,
          label: device?.label || prev?.label || `ورودی ${deviceId}`,
          desiredMode: prev?.desiredMode || "idle",
        };
      });
      // Reassign contiguous slots 0..n-1 for stability
      inputs.forEach((item, index) => {
        item.slot = index;
      });
      const data = await Publishers.setInputs(id, inputs);
      setPublisher(data.publisher);
      setDraftDeviceIds(inputs.map((i) => i.deviceId));
    } catch (err) {
      setError(err.message);
    } finally {
      setBusy(false);
    }
  }

  function toggleDevice(deviceId) {
    setDraftDeviceIds((prev) => {
      if (prev.includes(deviceId)) {
        return prev.filter((x) => x !== deviceId);
      }
      if (prev.length >= maxInputs) {
        setError(`حداکثر ${maxInputs} ورودی`);
        return prev;
      }
      setError("");
      return [...prev, deviceId];
    });
  }

  async function applyDraft() {
    await saveInputs(draftDeviceIds);
  }

  async function setSlotMode(slot, mode) {
    setSlotBusy(`${slot}:${mode}`);
    setError("");
    try {
      const data = await Publishers.setInputDesiredMode(id, slot, mode);
      setPublisher(data.publisher);
    } catch (err) {
      setError(err.message);
    } finally {
      setSlotBusy(null);
    }
  }

  if (!publisher && !error) {
    return (
      <main className="page">
        <p className="muted">در حال بارگذاری…</p>
      </main>
    );
  }

  if (!publisher) {
    return (
      <main className="page">
        <p className="error">{error || "ناشر پیدا نشد"}</p>
        <Link to="/publishers">بازگشت</Link>
      </main>
    );
  }

  const draftDirty =
    JSON.stringify([...draftDeviceIds].sort()) !==
    JSON.stringify((selected || []).map((s) => s.deviceId).sort());

  return (
    <main className="page manage-page">
      <p className="muted small">
        <Link to="/publishers">ناشران ←</Link>
      </p>

      <section className="panel">
        <div className="manage-header">
          <div>
            <h1>{publisher.label || publisher.username}</h1>
            <p className="mono muted small">{publisher.streamPath}</p>
          </div>
          <div className="manage-tags">
            <span className={`dot ${publisher.online ? "on" : "off"}`} />
            <span className={`tag ${publisher.deviceConnected ? "ok" : ""}`}>
              {publisher.deviceConnected ? "دستگاه وصل" : "دستگاه قطع"}
            </span>
            <span className="tag">مطلوب: {modeLabel(publisher.desiredMode)}</span>
            <span className="tag">واقعی: {modeLabel(publisher.actualMode)}</span>
            {!publisher.enabled ? <span className="tag warn">غیرفعال</span> : null}
          </div>
        </div>

        {publisher.deviceLastError ? (
          <p className="error small">{publisher.deviceLastError}</p>
        ) : null}
        {error ? <p className="error">{error}</p> : null}

        <div className="manage-section">
          <h2>وضعیت شبکه</h2>
          <p className="muted small">نرخ ارسال زنده از گوشی (به‌ازای هر اسلات استریم)</p>
          <NetworkPlot telemetry={publisher.telemetry || []} />
        </div>

        <div className="manage-section">
          <div className="manage-section-head">
            <div>
              <h2>ورودی‌های گوشی</h2>
              <p className="muted small">
                تا {maxInputs} ورودی انتخاب کنید — هم‌زمان با گوشی همگام می‌شود
              </p>
            </div>
            <button
              type="button"
              disabled={busy || !draftDirty}
              onClick={applyDraft}
            >
              ذخیره انتخاب
            </button>
          </div>

          {!publisher.deviceConnected ? (
            <p className="muted">برای دیدن ورودی‌ها، گوشی باید به کنترل وصل باشد.</p>
          ) : available.length === 0 ? (
            <p className="muted">هنوز لیست ورودی از گوشی نرسیده است…</p>
          ) : (
            <div className="input-grid">
              {available.map((device) => {
                const checked = draftDeviceIds.includes(device.id);
                return (
                  <label
                    key={device.id}
                    className={`input-chip ${checked ? "on" : ""}`}
                  >
                    <input
                      type="checkbox"
                      checked={checked}
                      disabled={busy || (!checked && draftDeviceIds.length >= maxInputs)}
                      onChange={() => toggleDevice(device.id)}
                    />
                    <span>{device.label || `دستگاه ${device.id}`}</span>
                  </label>
                );
              })}
            </div>
          )}

          {selected
            .filter((s) => !available.some((d) => d.id === s.deviceId))
            .map((s) => (
              <p key={`missing-${s.slot}`} className="warn-text small">
                اسلات {s.slot}: «{s.label || s.deviceId}» روی گوشی در دسترس نیست
              </p>
            ))}
        </div>

        <div className="manage-section">
          <h2>کنترل اسلات‌ها</h2>
          <p className="muted small">
            هر ورودی می‌تواند جداگانه استریم، ضبط محلی، یا متوقف باشد. چند استریم را هم‌زمان
            بشنوید.
          </p>

          {selected.length === 0 ? (
            <p className="muted">ابتدا ورودی‌ها را انتخاب و ذخیره کنید.</p>
          ) : (
            <div className="slot-grid">
              {selected.map((item) => {
                const actual = actualBySlot.get(item.slot);
                const actualMode = actual?.mode || "idle";
                const controlBusy = slotBusy?.startsWith(`${item.slot}:`);
                const canStart = publisher.enabled && !controlBusy;
                return (
                  <article key={item.slot} className="slot-card">
                    <div className="slot-card-head">
                      <strong>
                        اسلات {item.slot} · {item.label || item.deviceId}
                      </strong>
                      <span className="tag">مطلوب: {modeLabel(item.desiredMode)}</span>
                      <span className="tag">واقعی: {modeLabel(actualMode)}</span>
                    </div>
                    {actual?.error ? (
                      <p className="error small">{actual.error}</p>
                    ) : null}
                    <div className="row-actions">
                      <button
                        type="button"
                        className="ghost"
                        disabled={!canStart || item.desiredMode === "streaming"}
                        onClick={() => setSlotMode(item.slot, "streaming")}
                      >
                        استریم
                      </button>
                      <button
                        type="button"
                        className="ghost"
                        disabled={!canStart || item.desiredMode === "recording"}
                        onClick={() => setSlotMode(item.slot, "recording")}
                      >
                        ضبط محلی
                      </button>
                      <button
                        type="button"
                        className="ghost"
                        disabled={controlBusy || item.desiredMode === "idle"}
                        onClick={() => setSlotMode(item.slot, "idle")}
                      >
                        توقف
                      </button>
                    </div>
                    <SlotListenPanel
                      publisherId={publisher.id}
                      slot={item.slot}
                      label={item.label}
                      active={actualMode === "streaming" || item.desiredMode === "streaming"}
                    />
                  </article>
                );
              })}
            </div>
          )}
        </div>
      </section>
    </main>
  );
}
