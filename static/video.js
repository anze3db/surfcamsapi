function debounce(cb, delay = 250) {
    let timeout
    return (...args) => {
        clearTimeout(timeout)
        timeout = setTimeout(() => {
            cb(...args)
        }, delay)
    }
}

class Video {
    constructor(url, backUrl) {
        this.url = url;
        this.backUrl = backUrl;
        this.video = document.getElementById('video');
        this.error = document.getElementById('error');
    }
    setSize() {
        if (!this.video.videoHeight || !this.video.videoWidth) {
            return;
        }
        const ratio = this.video.videoWidth / this.video.videoHeight;
        let width = window.innerWidth;
        let height = width / ratio;
        if (height > window.innerHeight) {
            height = window.innerHeight;
        }
        this.video.setAttribute('height', height);
    }
    addListeners() {
        window.addEventListener('resize', (debounce((ev) => {
            this.setSize();
        }, 20)));
        this.video.addEventListener('play', () => {
            this.setSize();

        });

        this.video.addEventListener('click', () => {
            window.location = this.backUrl;
        });
    }
    loadSource() {
        // Where hls.js would fall back to ManagedMediaSource (iOS/iPadOS), the
        // system pauses buffering at will and live streams stall, so let
        // Apple's native player handle HLS instead.
        const preferNative = window.ManagedMediaSource && this.video.canPlayType('application/vnd.apple.mpegurl');
        if (!preferNative && Hls.isSupported()) {
            var hls = new Hls();
            hls.loadSource(this.url);
            hls.attachMedia(this.video);
            hls.on(Hls.Events.ERROR, (event, data) => {
                console.log("error", event, data);
                if (!this.error.textContent) {
                    this.error.style.display = 'block';
                    this.error.textContent += data.details + " ";
                }
            });
        }
        else if (this.video.canPlayType('application/vnd.apple.mpegurl')) {
            this.video.src = this.url;
            this.video.addEventListener('error', (event) => {
                console.log("error", event, this.video.error);
                if (!this.error.textContent) {
                    this.error.style.display = 'block';
                    this.error.textContent += (this.video.error?.message || "Playback error") + " ";
                }
            });
        }
        else {
            console.warn('Your browser does not support MSE');
        }
    }
    play() {
        this.setSize();
        this.addListeners();
        this.loadSource();
    }
}
