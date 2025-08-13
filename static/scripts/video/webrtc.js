const configuration = { 'iceServers': [{ 'urls': 'stun:stun.l.google.com:19302' }] }

let peerConnection = new RTCPeerConnection(configuration);
const localSenders = new Map();
let isNegotiating = false;

const videoEl = htmx.find('#video')

// -------------------------
// ---- Peer connection ----
// -------------------------

peerConnection.addEventListener('icecandidate', event => {
    if (!event.candidate) return;
    ws.send(JSON.stringify({ 'type': 'new-ice-candidate', 'candidate': event.candidate }));
});


peerConnection.addEventListener('track', event => {
    console.log("Track received from remote peer:", event.track);
    if (!videoEl.srcObject) {
        videoEl.srcObject = new MediaStream();
    }
    videoEl.srcObject.addTrack(event.track);
});

peerConnection.onnegotiationneeded = async () => {
    if (isNegotiating || peerConnection.signalingState !== 'stable') {
        console.log("Skipping negotiation, already in progress or not in stable state.");
        return;
    }
    try {
        isNegotiating = true;
        const offer = await peerConnection.createOffer();
        console.log('Negotiation needed, creating offer...', offer);
        await peerConnection.setLocalDescription(offer);
        ws.send(JSON.stringify(offer));
    } catch (e) {
        console.error('Error during negotiation:', e);
    } finally {
        isNegotiating = false;
    }
};

// -------------------------
// ---- Signaling logic ----
// -------------------------

async function makeCall() {
    const offer = await peerConnection.createOffer();
    await peerConnection.setLocalDescription(offer);
    console.log("sending offer", offer)
    ws.send(JSON.stringify(offer));
}

async function handleMessage(event) {
    const message = event.detail ? event.detail.message : event.data;
    if (!isJson(message)) return

    const data = JSON.parse(message);
    switch (data.type) {
        case 'answer':
            // if (peerConnection.signalingState !== 'have-local-offer') return;
            await peerConnection.setRemoteDescription(data);
            break;
        case 'offer':
            console.log("offer", peerConnection.signalingState)
            // if (peerConnection.signalingState !== 'stable') return;
            console.log(data)
            await peerConnection.setRemoteDescription(data);
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
        case 'hangup':
            console.log('Received hangup signal.');
            stopStream();
            break;
    }
}


function stopStream() {
    if (!peerConnection) return;

    if (ws && ws.readyState === WebSocket.OPEN) {
        ws.send(JSON.stringify({ type: 'hangup' }));
    }
    
    isNegotiating = false;

    localSenders.forEach(({ track, sender }) => {
        track.stop();
        if (peerConnection.getSenders().includes(sender)) {
            peerConnection.removeTrack(sender);
        }
    });
    localSenders.clear();

    peerConnection.close();
    videoEl.srcObject = null;

    console.log("Call ended and resources cleaned up.");
}


// ------------------------
// ---- Media Controls ----
// ------------------------

const toggleCamera = () => toggleTrack('camera', { video: true });
const toggleMicrophone = () => toggleTrack('mic', { audio: true });
const toggleScreenShare = () => toggleTrack('screen', { video: true });

function toggleControl(key) {
    console.log('toggling', key)
    const elt = htmx.find('#' + key)
    const [onBtn, offBtn] = htmx.findAll(elt, "button")
    htmx.toggleClass(onBtn, "hidden")
    htmx.toggleClass(offBtn, "hidden")
}

async function toggleTrack(key, mediaConstraints) {

    if (localSenders.has(key)) {
        console.log(`Stopping track: ${key}`);
        const { sender, track } = localSenders.get(key);
        peerConnection.removeTrack(sender);
        track.stop();
        localSenders.delete(key);

        toggleControl(key);
        if (key === 'mic') return;
        videoEl.srcObject = null;
    } else {
        const videoKeyToStop = key === 'camera' ? 'screen' : 'camera';
        if (key !== 'mic' && localSenders.has(videoKeyToStop)) {
            await toggleTrack(videoKeyToStop);
        }

        console.log(`Starting track: ${key}`);
        try {
            const stream = key === 'screen'
                ? await navigator.mediaDevices.getDisplayMedia(mediaConstraints)
                : await navigator.mediaDevices.getUserMedia(mediaConstraints);
            toggleControl(key);

            const track = stream.getTracks()[0];
            const sender = peerConnection.addTrack(track, stream);

            localSenders.set(key, { sender, track });

            if (key !== 'mic') {
                videoEl.srcObject = stream;
            }

            track.onended = () => {
                toggleControl(key);
                peerConnection.removeTrack(sender);
                localSenders.delete(key);
                videoEl.srcObject = null;
            };

        } catch (error) {
            console.error(`Error starting track ${key}:`, error);
        }
    }
}