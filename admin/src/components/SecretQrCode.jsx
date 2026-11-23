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
      if (!cancelled) setError(err.message || "QR failed");
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
      setError("Could not copy — select and copy manually");
    }
  }

  if (error) {
    return <p className="error small">Could not render QR: {error}</p>;
  }

  return (
    <div className="secret-qr-wrap">
      <canvas
        ref={canvasRef}
        className="secret-qr"
        width={size}
        height={size}
        aria-label="Scan with Android app to import publish credentials"
      />
      <button type="button" className="ghost" onClick={copyPayload}>
        {copied ? "Copied" : "Copy share link"}
      </button>
    </div>
  );
}
