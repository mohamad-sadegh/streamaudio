/**
 * Minimal WHEP client for MediaMTX (audio-only listen).
 */
export async function startWhep({
  whepUrl,
  authorization,
  onTrack,
  onConnectionState,
}) {
  const pc = new RTCPeerConnection({
    iceServers: [{ urls: "stun:stun.l.google.com:19302" }],
  });

  pc.addTransceiver("audio", { direction: "recvonly" });

  pc.ontrack = (ev) => {
    if (onTrack) onTrack(ev.streams[0] || new MediaStream([ev.track]));
  };

  pc.onconnectionstatechange = () => {
    if (onConnectionState) onConnectionState(pc.connectionState);
  };

  const offer = await pc.createOffer();
  await pc.setLocalDescription(offer);

  await waitForIceGathering(pc);

  const res = await fetch(whepUrl, {
    method: "POST",
    headers: {
      "Content-Type": "application/sdp",
      Authorization: authorization,
    },
    body: pc.localDescription.sdp,
  });

  if (!res.ok) {
    pc.close();
    const text = await res.text();
    throw new Error(`WHEP failed (${res.status}): ${text || res.statusText}`);
  }

  const answer = await res.text();
  const location = res.headers.get("Location");
  await pc.setRemoteDescription({ type: "answer", sdp: answer });

  return {
    pc,
    resourceUrl: location
      ? new URL(location, whepUrl).toString()
      : null,
    async stop() {
      if (location) {
        try {
          await fetch(new URL(location, whepUrl).toString(), {
            method: "DELETE",
            headers: { Authorization: authorization },
          });
        } catch {
          /* ignore */
        }
      }
      pc.close();
    },
  };
}

function waitForIceGathering(pc) {
  if (pc.iceGatheringState === "complete") return Promise.resolve();
  return new Promise((resolve) => {
    const check = () => {
      if (pc.iceGatheringState === "complete") {
        pc.removeEventListener("icegatheringstatechange", check);
        resolve();
      }
    };
    pc.addEventListener("icegatheringstatechange", check);
    setTimeout(() => {
      pc.removeEventListener("icegatheringstatechange", check);
      resolve();
    }, 2000);
  });
}
