class Video {
    constructor(url) {
        this.url = url;
        this.video = document.getElementById('video');
    }
    setSize() {
        video.setAttribute('width', document.body.clientWidth);
    }
    addListeners() {
        window.addEventListener('resize', this.setSize);
        this.video.addEventListener('click', function (event) {
            // Go back
            // window.location = django.indexUrl;
        });
        this.video.addEventListener('play', () => {
            this.setSize()
        });
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
