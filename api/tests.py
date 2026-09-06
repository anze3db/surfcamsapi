from datetime import UTC, datetime
from unittest import mock

from django.test import TestCase, override_settings

from cams.models import Cam, Category
from surfline.urls import SurflineFetcher


class TestHealthApi(TestCase):
    def test_health(self):
        categories = [Category(title=f"Cat {i}") for i in range(3)]
        Category.objects.bulk_create(categories)
        response = self.client.get("/api/health")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {"message": "ok"})

    def test_health_no_categories(self):
        response = self.client.get("/api/health")
        self.assertEqual(response.status_code, 503)
        self.assertEqual(response.json(), {"message": "Please retry later"})

    @override_settings(DEBUG=True)
    def test_health_no_categories_debug_mode(self):
        response = self.client.get("/api/health")
        self.assertEqual(response.status_code, 503)
        self.assertEqual(response.json(), {"message": "Not enough categories"})


# detail.html renders {% static %} links, which the manifest storage can only
# resolve after collectstatic has run.
@override_settings(
    STORAGES={
        "default": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
        "staticfiles": {
            "BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage"
        },
    }
)
class TestCamsDetail(TestCase):
    def setUp(self):
        self.cam = Cam.objects.create(
            slug="pipeline",
            title="Pipeline",
            subtitle="Surfline",
            url="https://example.com/stream.m3u8",
            spot_id="spot-1",
        )

    def patched_fetch_all(self, result):
        async def fetch_all(_self):
            return result

        return mock.patch.object(SurflineFetcher, "fetch_all", fetch_all)

    def test_detail_renders_the_forecast(self):
        wind = [{"date": datetime(2026, 9, 5, 6, tzinfo=UTC), "direction": 90}]
        with self.patched_fetch_all((None, None, wind, [])):
            response = self.client.get(f"/api/cams/{self.cam.id}")

        self.assertContains(response, "Pipeline")
        self.assertEqual(len(response.context["forecast_days"]), 1)

    def test_detail_renders_without_a_forecast(self):
        with self.patched_fetch_all((None, None, [], [])):
            response = self.client.get(f"/api/cams/{self.cam.id}")

        self.assertContains(response, "Pipeline")
        # The chart script still needs valid JSON to parse.
        self.assertContains(response, "const chartDays = [];")

    def test_detail_unknown_cam(self):
        response = self.client.get(f"/api/cams/{self.cam.id + 1}")
        self.assertEqual(response.status_code, 404)
        self.assertEqual(response.json(), {"message": "Cam not found"})
