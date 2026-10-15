from datetime import UTC, datetime, timedelta
from unittest import mock

import httpx
from django.test import TestCase, TransactionTestCase, override_settings
from model_bakery import baker
from potatoq import current_app
from potatoq.testing import drain, due

from cams.tasks import check_cams
from cams.models import Cam

OFFLINE_SINCE = datetime(2026, 1, 1, tzinfo=UTC)


# TransactionTestCase: tasks are enqueued on commit, which TestCase never does.
@override_settings(P_REFERER="https://referer.example")
class TestCheckCams(TransactionTestCase):
    def setUp(self):
        self.online = baker.make(Cam, url="https://cams.example/online.m3u8")
        self.back_online = baker.make(
            Cam, url="https://cams.example/back.m3u8", offline_since=OFFLINE_SINCE
        )
        self.down = baker.make(Cam, url="https://cams.example/down.m3u8")
        self.still_down = baker.make(
            Cam, url="https://cams.example/down-2.m3u8", offline_since=OFFLINE_SINCE
        )
        self.proxied = baker.make(
            Cam, url="https://cams.example/proxied.m3u8", proxy=True
        )
        self.requests = []

    def run_check(self, error=None):
        async def fake_get(client, url, headers, timeout):
            self.requests.append((url, headers))
            request = httpx.Request("GET", url)
            if error is not None:
                raise error
            return httpx.Response(404 if "down" in url else 200, request=request)

        check_cams.delay()
        with mock.patch.object(httpx.AsyncClient, "get", fake_get):
            [task] = drain(current_app())
        self.assertEqual((task.name, task.state), ("cams.tasks.check_cams", "SUCCESS"))

    def assertOffline(self, cam, since=None):
        cam.refresh_from_db()
        self.assertIsNotNone(cam.offline_since)
        if since is not None:
            self.assertEqual(cam.offline_since, since)

    def assertOnline(self, cam):
        cam.refresh_from_db()
        self.assertIsNone(cam.offline_since)

    def test_check_cams(self):
        self.run_check()

        self.assertOnline(self.online)
        self.assertOnline(self.back_online)
        self.assertOnline(self.proxied)
        self.assertOffline(self.down)
        self.assertOffline(self.still_down, since=OFFLINE_SINCE)
        self.assertIn((self.online.url, {}), self.requests)
        self.assertIn(
            (self.proxied.url, {"Referer": "https://referer.example"}), self.requests
        )

    def test_check_cams_unreachable(self):
        self.run_check(error=httpx.ConnectError("unreachable"))

        self.assertOffline(self.online)
        self.assertOffline(self.back_online, since=OFFLINE_SINCE)


class TestSchedule(TestCase):
    def test_check_cams_every_two_hours(self):
        app = current_app()
        self.assertIn(check_cams.name, app.tasks)
        start = datetime(2026, 10, 9, 11, 0, tzinfo=UTC)
        self.assertEqual(
            due(app, start, start + timedelta(hours=5)),
            [
                ("check-cams", datetime(2026, 10, 9, 12, 0, tzinfo=UTC)),
                ("check-cams", datetime(2026, 10, 9, 14, 0, tzinfo=UTC)),
                ("check-cams", datetime(2026, 10, 9, 16, 0, tzinfo=UTC)),
            ],
        )
