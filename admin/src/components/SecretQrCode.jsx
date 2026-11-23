import { useEffect, useRef, useState } from "react";
import QRCode from "qrcode";

/**
 * Compact share URI for phone cameras (shorter / easier than JSON).
 * Android accepts this and legacy JSON.
 */
export function buildPublishSharePayload(publisher) {
  const params = new URLSearchParams({
    u: publisher.username,
    s: publisher.secret,
    w: publisher.whipUrl,
  });
  return `streamaudio://publish?${params.toString()}`;
}

export default function SecretQrCode({ value, size = 300 }) {
  const canvasRef = useRef(null);
  const [error, setError] = useState("");
  const [copied, setCopied] = useState(false);

  useEffect(() => {
    let cancelled = false;
    setError("");
    const canvas = canvasRef.current;
    if (!canvas || !value) return;

    QRCode.toCanvas(canvas, value, {
      width: size,
      margin: 4,
      errorCorrectionLevel: "M",
      color: {
        dark: "#000000",
        light: "#ffffff",
      },
    }).catch((err) => {
      if (!cancelled) setError(err.message || "ساخت QR ناموفق بود");
    });

    return () => {
      cancelled = true;
    };
  }, [value, size]);

  async function copyPayload() {
    try {
      await navigator.clipboard.writeText(value);
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    } catch {
      setError("کپی ممکن نشد — دستی انتخاب و کپی کنید");
    }
  }

  if (error) {
    return <p className="error small">نمایش QR ممکن نشد: {error}</p>;
  }

  return (
    <div className="secret-qr-wrap">
      <canvas
        ref={canvasRef}
        className="secret-qr"
        width={size}
        height={size}
        aria-label="اسکن با اپ اندروید برای ورود اعتبارنامه انتشار"
      />
      <button type="button" className="ghost" onClick={copyPayload}>
        {copied ? "کپی شد" : "کپی لینک اشتراک"}
      </button>
    </div>
  );
}
