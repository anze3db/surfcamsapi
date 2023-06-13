class Video {
    constructor(url, backUrl) {
        this.url = url;
        this.backUrl = backUrl;
        this.video = document.getElementById('video');
    }
    setSize() {
        if (this.video.videoHeight > window.innerHeight) {
            this.video.setAttribute('height', window.innerHeight);
        }
        else {
            this.video.setAttribute('width', document.body.clientWidth);
        }
    }
    addListeners() {
        window.addEventListener('resize', this.setSize);
        this.video.addEventListener('play', () => {
            this.setSize();

        });
        this.video.addEventListener('click', () => {
            window.location = this.backUrl;
        })
    }
    loadSource() {
        if (Hls.isSupported()) {
            var hls = new Hls();
            hls.loadSource(this.url);
            hls.attachMedia(this.video);
            hls.on(Hls.Events.ERROR, function (event, data) {
                console.log("error", event, data)
            });
        }
        else if (video.canPlayType('application/vnd.apple.mpegurl')) {
            this.video.src = this.url;
            this.video.addEventListener('error', function (event, data) {
                console.log("error", event, data)
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
