function createYTplayer(videoId, playerId) {
    console.log(videoId, playerId)
    console.log("sfsfs")
    let p = new YT.Player(playerId, {
        videoId: 'M7lc1UVf-VE',
        height: '390',
        width: '640',
        events: {
            onReady: e => console.log('Player is ready', e),
            onStateChange: e => console.log('Player is changed', e)
        }
    });
    console.log(p)
    return p
}
// https://stackoverflow.com/questions/61047247/add-video-to-page-using-youtube-player-api
// https://stackoverflow.com/questions/20503462/youtube-embed-iframe-events-not-firing-in-local
function onPlayerReady(event) {
    console.log("INIT")
    event.target.playVideo();
}

function onPlayerStateChange(event) {
    console.log("State changed")
    if (event.data == YT.PlayerState.PLAYING && !done) {
        setTimeout(stopVideo, 6000);
        done = true;
    }
}
function stopVideo() {
    player.stopVideo();
}


function sleep(ms) {
    return new Promise(resolve => setTimeout(resolve, ms));
}

