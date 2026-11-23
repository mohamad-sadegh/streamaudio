import { useEffect, useRef, useState } from "react";
import QRCode from "qrcode";

/** Payload the Android app scans after Create / Rotate. */
export function buildPublishSharePayload(publisher) {
  return JSON.stringify({
    v: 1,
    type: "streamaudio.publish",
    username: publisher.username,
    secret: publisher.secret,
    whipUrl: publisher.whipUrl,
  });
}

export default function SecretQrCode({ value, size = 200 }) {
  const canvasRef = useRef(null);
  const [error, setError] = useState("");

  useEffect(() => {
    let cancelled = false;
    setError("");
    const canvas = canvasRef.current;
    if (!canvas || !value) return;

    QRCode.toCanvas(canvas, value, {
      width: size,
      margin: 2,
      errorCorrectionLevel: "M",
      color: {
        dark: "#07110f",
        light: "#e8f2ee",
      },
    }).catch((err) => {
      if (!cancelled) setError(err.message || "QR failed");
    });

    return () => {
      cancelled = true;
    };
  }, [value, size]);

  if (error) {
    return <p className="error small">Could not render QR: {error}</p>;
  }

  return (
    <canvas
      ref={canvasRef}
      className="secret-qr"
      width={size}
      height={size}
      aria-label="Scan with Android app to import publish credentials"
    />
  );
}
