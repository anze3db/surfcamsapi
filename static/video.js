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
        window.addEventListener('resize', (() => { this.setSize() }));
        this.video.addEventListener('play', () => {
            this.setSize();
            this.video.removeAttribute('controls');

        });

        this.video.addEventListener('click', () => {
            if (!his.video.hasAttribute('controls')) {
                window.location = this.backUrl;
            }
        });
    }
    loadSource() {
        if (Hls.isSupported()) {
            var hls = new Hls();
            hls.loadSource(this.url);
            hls.attachMedia(this.video);
            hls.on(Hls.Events.ERROR, (event, data) => {
                console.log("error", event, data);
                if (!this.error.textContent) {
                    this.error.style.display = 'block';
                    this.error.textContent += data.details + " ";
                }
                // this.video.setAttribute('controls', 'controls');
            });
        }
        else if (video.canPlayType('application/vnd.apple.mpegurl')) {
            this.video.src = this.url;
            this.video.addEventListener('error', (event, data) => {
                console.log("error", event, data);
                if (!this.error.textContent) {
                    this.error.style.display = 'block';

                    this.error.textContent += data.details + " ";
                }
                // this.video.setAttribute('controls', 'controls');

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
