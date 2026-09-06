from datetime import UTC, datetime
from unittest import mock

from django.test import TestCase
from django.urls import reverse

from cams.models import Cam
from surfline.urls import SurflineFetcher


def timestamp(hour):
    return int(datetime(2026, 9, 5, hour, tzinfo=UTC).timestamp())


class SurflineFetcherTests(TestCase):
    async def test_fetch_waves_merges_surf_and_swells(self):
        surf = {
            "data": {
                "surf": [
                    {
                        "timestamp": timestamp(6),
                        "utcOffset": 0,
                        "surf": {"min": 0.3, "max": 0.6, "humanRelation": "Knee high"},
                    },
                    # Filtered out: only every third hour from 04:00 is shown.
                    {
                        "timestamp": timestamp(7),
                        "utcOffset": 0,
                        "surf": {"min": 9, "max": 9, "humanRelation": "Nope"},
                    },
                ]
            }
        }
        swells = {
            "data": {
                "swells": [
                    {
                        "timestamp": timestamp(6),
                        "power": 120.5,
                        "swells": [
                            {"height": 0.5, "period": 8, "impact": 0.1, "direction": 10},
                            {"height": 1.5, "period": 13, "impact": 0.9, "direction": 220},
                        ],
                    }
                ]
            }
        }

        async def fetch(endpoint, params=None):
            return {"surf": surf, "swells": swells}[endpoint]

        fetcher = SurflineFetcher("spot-1", client=None)
        with mock.patch.object(fetcher, "fetch", fetch):
            waves = await fetcher.fetch_waves()

        self.assertEqual(
            waves,
            [
                {
                    "date": datetime(2026, 9, 5, 6, tzinfo=UTC),
                    "min": 0.3,
                    "max": 0.6,
                    "human": "Knee high",
                    # The highest-impact swell wins, not the biggest one.
                    "primary_swell_size": 1.5,
                    "primary_swell_period": 13,
                    "primary_swell_direction": 220,
                    "power": 120.5,
                }
            ],
        )

    async def test_fetch_waves_without_matching_swells(self):
        async def fetch(endpoint, params=None):
            if endpoint == "surf":
                return {
                    "data": {
                        "surf": [
                            {
                                "timestamp": timestamp(6),
                                "utcOffset": 0,
                                "surf": {
                                    "min": 0.3,
                                    "max": 0.6,
                                    "humanRelation": "Knee high",
                                },
                            }
                        ]
                    }
                }
            return {"data": {"swells": []}}

        fetcher = SurflineFetcher("spot-1", client=None)
        with mock.patch.object(fetcher, "fetch", fetch):
            waves = await fetcher.fetch_waves()

        self.assertEqual(waves[0]["primary_swell_size"], None)
        self.assertEqual(waves[0]["power"], None)

    async def test_fetch_all_keeps_the_endpoints_that_worked(self):
        fetcher = SurflineFetcher("spot-1", client=None)

        async def boom():
            raise ValueError("Surfline is down")

        async def wind():
            return [{"date": datetime(2026, 9, 5, 6, tzinfo=UTC)}]

        with (
            mock.patch.object(fetcher, "fetch_tides", boom),
            mock.patch.object(fetcher, "fetch_sunlight", boom),
            mock.patch.object(fetcher, "fetch_wind", wind),
            mock.patch.object(fetcher, "fetch_waves", boom),
            self.assertLogs("surfline.urls", "WARNING"),
        ):
            tides, sunlight, wind_data, waves = await fetcher.fetch_all()

        self.assertIsNone(tides)
        self.assertIsNone(sunlight)
        self.assertEqual(len(wind_data), 1)
        self.assertEqual(waves, [])

    async def test_fetch_all_without_a_spot_id(self):
        self.assertEqual(
            await SurflineFetcher("", client=None).fetch_all(), (None, None, [], [])
        )


class SurflineViewTests(TestCase):
    def setUp(self):
        self.cam = Cam.objects.create(
            slug="pipeline",
            title="Pipeline",
            subtitle="Surfline",
            url="https://example.com/stream.m3u8",
            spot_id="spot-1",
        )
        self.url = reverse("surfline_detail", args=[self.cam.id])

    def patched_fetch_all(self, result):
        async def fetch_all(_self):
            return result

        return mock.patch.object(SurflineFetcher, "fetch_all", fetch_all)

    def test_unknown_cam(self):
        response = self.client.get(reverse("surfline_detail", args=[self.cam.id + 1]))
        self.assertContains(response, "Cam not found")

    def test_rows_are_grouped_per_day_and_survive_a_missing_endpoint(self):
        wind = [
            {"date": datetime(2026, 9, 5, 6, tzinfo=UTC), "direction": 90},
            {"date": datetime(2026, 9, 5, 9, tzinfo=UTC), "direction": 90},
            {"date": datetime(2026, 9, 6, 6, tzinfo=UTC), "direction": 90},
        ]
        with self.patched_fetch_all((None, None, wind, [])):
            response = self.client.get(self.url)

        forecast_days = response.context["forecast_days"]
        self.assertEqual([len(day["rows"]) for day in forecast_days], [2, 1])
        self.assertEqual(forecast_days[0]["rows"][0]["wind"], wind[0])
        self.assertIsNone(forecast_days[0]["rows"][0]["wave"])

    def test_rows_stay_aligned_when_wind_is_missing(self):
        waves = [{"date": datetime(2026, 9, 5, 9, tzinfo=UTC), "power": 100}]
        with self.patched_fetch_all((None, None, [], waves)):
            response = self.client.get(self.url)

        row = response.context["forecast_days"][0]["rows"][0]
        self.assertIsNone(row["wind"])
        self.assertEqual(row["wave"], waves[0])

    def test_everything_down_retries_with_exponential_backoff(self):
        with self.patched_fetch_all((None, None, [], [])):
            first = self.client.get(self.url)
            later = self.client.get(self.url, {"attempt": 3})
            capped = self.client.get(self.url, {"attempt": 8})

        self.assertContains(first, "delay:3s")
        self.assertContains(first, f"{self.url}?attempt=1")
        self.assertContains(later, "delay:24s")
        self.assertContains(later, f"{self.url}?attempt=4")
        # Retries stop once MAX_RETRIES is reached.
        self.assertNotContains(capped, "hx-trigger")
        self.assertContains(capped, "Try again")

    def test_retry_delay_is_capped(self):
        with self.patched_fetch_all((None, None, [], [])):
            response = self.client.get(self.url, {"attempt": 4})
        self.assertContains(response, "delay:48s")

    def test_garbage_attempt_starts_over(self):
        with self.patched_fetch_all((None, None, [], [])):
            response = self.client.get(self.url, {"attempt": "🏄"})
        self.assertContains(response, "delay:3s")

    def test_cam_without_a_spot_id_renders_an_empty_forecast(self):
        self.cam.spot_id = ""
        self.cam.save()
        response = self.client.get(self.url)
        self.assertNotContains(response, "wiped out")
        self.assertEqual(response.context["forecast_days"], [])
