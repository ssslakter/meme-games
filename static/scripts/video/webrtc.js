const configuration = {
  iceServers: [{ urls: "stun:stun.l.google.com:19302" }],
};

// Map to hold peer connections with peerId as key
const peerConnections = new Map();
const localSenders = new Map();

const videoEl = htmx.find("#video");
let isNegotiatingMap = new Map();

function createPeerConnection(peerId) {
  const peerConnection = new RTCPeerConnection(configuration);

  peerConnection.addEventListener("icecandidate", (event) => {
    if (!event.candidate) return;
    ws.send(
      JSON.stringify({
        type: "new-ice-candidate",
        candidate: event.candidate,
        peerId,
      }),
    );
  });

  peerConnection.addEventListener("track", (event) => {
    console.log(`Track received from remote peer ${peerId}:`, event.track);
    // Here you can handle remote tracks if you want to show remote streams
    // For broadcaster only, we might not handle this
  });

  peerConnection.onnegotiationneeded = async () => {
    if (
      isNegotiatingMap.get(peerId) ||
      peerConnection.signalingState !== "stable"
    ) {
      console.log(
        `Skipping negotiation for peer ${peerId}, already in progress or unstable state.`,
      );
      return;
    }
    try {
      isNegotiatingMap.set(peerId, true);
      const offer = await peerConnection.createOffer();
      console.log(
        `Negotiation needed for peer ${peerId}, creating offer...`,
        offer,
      );
      await peerConnection.setLocalDescription(offer);
      ws.send(JSON.stringify({ ...offer, peerId }));
    } catch (e) {
      console.error(`Error during negotiation with peer ${peerId}:`, e);
    } finally {
      isNegotiatingMap.set(peerId, false);
    }
  };

  return peerConnection;
}

async function handleMessage(event) {
  const message = event.detail ? event.detail.message : event.data;
  if (!isJson(message)) return;

  const data = JSON.parse(message);
  const peerId = data.peerId;
  if (!peerId) {
    console.warn("Received signaling message without peerId, ignoring.");
    return;
  }

  let peerConnection = peerConnections.get(peerId);

  switch (data.type) {
    case "offer":
      if (!peerConnection) {
        peerConnection = createPeerConnection(peerId);
        peerConnections.set(peerId, peerConnection);
      }
      console.log(`Offer received from peer ${peerId}`);
      await peerConnection.setRemoteDescription(
        new RTCSessionDescription(data),
      );
      const answer = await peerConnection.createAnswer();
      await peerConnection.setLocalDescription(answer);
      ws.send(JSON.stringify({ ...answer, peerId }));
      break;

    case "answer":
      if (peerConnection) {
        await peerConnection.setRemoteDescription(
          new RTCSessionDescription(data),
        );
        console.log(`Answer received for peer ${peerId}`);
      } else {
        console.warn(`No peer connection found for peerId ${peerId} on answer`);
      }
      break;

    case "new-ice-candidate":
      if (peerConnection) {
        try {
          await peerConnection.addIceCandidate(
            new RTCIceCandidate(data.candidate),
          );
          console.log(`Added ICE candidate from peer ${peerId}`);
        } catch (e) {
          console.error(`Error adding ICE candidate for peer ${peerId}`, e);
        }
      } else {
        console.warn(
          `No peer connection found for peerId ${peerId} on ICE candidate`,
        );
      }
      break;

    case "hangup":
      if (peerConnection) {
        console.log(`Hangup received for peer ${peerId}`);
        closePeerConnection(peerId);
      }
      break;

    default:
      console.warn(`Unknown signaling message type: ${data.type}`);
  }
}

function closePeerConnection(peerId) {
  const peerConnection = peerConnections.get(peerId);
  if (!peerConnection) return;

  peerConnection.close();
  peerConnections.delete(peerId);
  isNegotiatingMap.delete(peerId);

  localSenders.forEach(({ sender }) => {
    if (peerConnection.getSenders().includes(sender)) {
      peerConnection.removeTrack(sender);
    }
  });

  if (peerConnections.size === 0) {
    // No more peers, clean up video element if desired
    videoEl.srcObject = null;
  }

  console.log(`Peer connection with ${peerId} closed and cleaned up.`);
}

function stopAllStreams() {
  // Stop all local tracks and close all peer connections
  localSenders.forEach(({ track }) => {
    track.stop();
  });
  localSenders.clear();

  for (const peerId of peerConnections.keys()) {
    closePeerConnection(peerId);
  }
}

// ------------------------
// ---- Media Controls ----
// ------------------------

const toggleCamera = () => toggleTrack("camera", { video: true });
const toggleMicrophone = () => toggleTrack("mic", { audio: true });
const toggleScreenShare = () => toggleTrack("screen", { video: true });

function toggleControl(key) {
  console.log("toggling", key);
  const elt = htmx.find("#" + key);
  const [onBtn, offBtn] = htmx.findAll(elt, "button");
  htmx.toggleClass(onBtn, "hidden");
  htmx.toggleClass(offBtn, "hidden");
}

async function toggleTrack(key, mediaConstraints) {
  if (localSenders.has(key)) {
    console.log(`Stopping track: ${key}`);
    const { sender, track } = localSenders.get(key);

    localSenders.delete(key);
    track.stop();

    // Remove track from all peer connections
    peerConnections.forEach((peerConnection) => {
      if (peerConnection.getSenders().includes(sender)) {
        peerConnection.removeTrack(sender);
      }
    });

    toggleControl(key);
    if (key === "mic") return;
    videoEl.srcObject = null;
  } else {
    const videoKeyToStop = key === "camera" ? "screen" : "camera";
    if (key !== "mic" && localSenders.has(videoKeyToStop)) {
      await toggleTrack(videoKeyToStop);
    }

    console.log(`Starting track: ${key}`);
    try {
      const stream =
        key === "screen"
          ? await navigator.mediaDevices.getDisplayMedia(mediaConstraints)
          : await navigator.mediaDevices.getUserMedia(mediaConstraints);
      toggleControl(key);

      const track = stream.getTracks()[0];

      // Add track to all peer connections
      peerConnections.forEach((peerConnection) => {
        const sender = peerConnection.addTrack(track, stream);
        localSenders.set(key, { sender, track });
        track.onended = () => {
          toggleControl(key);
          peerConnection.removeTrack(sender);
          localSenders.delete(key);
          videoEl.srcObject = null;
        };
      });

      if (key !== "mic") {
        videoEl.srcObject = stream;
      }
    } catch (error) {
      console.error(`Error starting track ${key}:`, error);
    }
  }
}

// Export functions for usage if needed
window.handleMessage = handleMessage;
window.toggleCamera = toggleCamera;
window.toggleMicrophone = toggleMicrophone;
window.toggleScreenShare = toggleScreenShare;
window.stopAllStreams = stopAllStreams;
