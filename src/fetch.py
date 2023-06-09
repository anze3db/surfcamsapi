from datetime import datetime

import httpx


def fetch():
    "https://services.surfline.com/kbyg/spots/forecasts/tides?spotId=5842041f4e65fad6a7708bc0&days=17&cacheEnabled=true&units%5BtideHeight%5D=M&accesstoken=63dfa06b0cb1cfbfdd474a99eff35c62c71211c6"
    baseurl = "https://services.surfline.com/kbyg/spots/forecasts/"
    tides = "tides"
    response = httpx.get(
        baseurl + tides,
        timeout=5.0,
        params={
            "spotId": "5842041f4e65fad6a7708bc0",
            "days": 2,
        },
    )
    json = response.json()
    for tide in json["data"]["tides"]:
        if tide["type"] == "NORMAL":
            continue
        print(
            datetime.utcfromtimestamp(tide["timestamp"] + tide["utcOffset"] * 3600),
            tide["type"],
            str(tide["height"]) + json["associated"]["units"]["tideHeight"],
        )
    pass


if __name__ == "__main__":
    fetch()
