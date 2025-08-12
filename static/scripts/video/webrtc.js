const configuration = { 'iceServers': [{ 'urls': 'stun:stun.l.google.com:19302' }] }

// ---- Peer connection ----
let peerConnection = new RTCPeerConnection(configuration);
peerConnection.addEventListener('icecandidate', event => {
    console.log("ICE Candidate found:", event.candidate);
    if (event.candidate) {
        ws.send(JSON.stringify({ 'type': 'new-ice-candidate', 'candidate': event.candidate }));
    }
});

peerConnection.addEventListener('connectionstatechange', event => {
    console.log('Connection state changed to:', peerConnection.connectionState);
    if (peerConnection.connectionState === 'connected') {
        // Peers connected!
    }
});

peerConnection.addEventListener('track', event => {
    console.log("Track received from remote peer:", event.streams);
    const remoteVideo = document.getElementById('video');
    remoteVideo.srcObject = event.streams[0];
});

// ---- Signaling logic ----

async function makeCall() {
    const offer = await peerConnection.createOffer();
    await peerConnection.setLocalDescription(offer);
    ws.send(JSON.stringify(offer));
}

async function handleMessage(event) {
    const message = event.detail.message;
    if (!isJson(message)) return

    const data = JSON.parse(message);
    switch (data.type) {
        case 'answer':
            await peerConnection.setRemoteDescription(new RTCSessionDescription(data));
            break;
        case 'offer':
            peerConnection.setRemoteDescription(new RTCSessionDescription(data));
            const answer = await peerConnection.createAnswer();
            await peerConnection.setLocalDescription(answer);
            ws.send(JSON.stringify(answer));
            break;
        case 'new-ice-candidate':
            try {
                await peerConnection.addIceCandidate(data.candidate);
            } catch (e) {
                console.error('Error adding received ice candidate', e);
            }
            break;
        default:
            break;
    }
}

async function startStream() {
    await captureMedia();
    await makeCall();
}

async function captureMedia() {
    try {
        var stream = await navigator.mediaDevices.getDisplayMedia({ video: true, audio: true });
        document.body.dispatchEvent(new CustomEvent('start-stream', { detail: stream }))
        stream.getTracks().forEach(track => peerConnection.addTrack(track, stream));

    } catch (error) {
        console.error("Error:", error);
    }
}