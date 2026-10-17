from datetime import UTC, datetime, timedelta
from functools import partial
from unittest import mock

import httpx
from django.contrib.auth.models import User
from django.test import TestCase, TransactionTestCase, override_settings
from model_bakery import baker
from potatoq import current_app
from potatoq.testing import drain, due, reset

from cams.tasks import check_cams
from cams.models import Cam

OFFLINE_SINCE = datetime(2026, 1, 1, tzinfo=UTC)


# TransactionTestCase: tasks are enqueued on commit, which TestCase never does.
@override_settings(P_REFERER="https://referer.example")
class TestCheckCams(TransactionTestCase):
    def setUp(self):
        # The test database is reused (--reuse-db), and so is the broker in it.
        reset(current_app())
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


@override_settings(P_REFERER="https://referer.example")
class TestProxy(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.user = baker.make(User)

    def setUp(self):
        self.async_client.force_login(self.user)
        self.requests = []

    def upstream(self, status, content_type, body):
        def handler(request):
            self.requests.append(request)
            return httpx.Response(
                status, headers={"Content-Type": content_type}, content=body
            )

        client = partial(httpx.AsyncClient, transport=httpx.MockTransport(handler))
        return mock.patch.object(httpx, "AsyncClient", client)

    async def get(self, path):
        response = await self.async_client.get(path)
        body = b"".join([chunk async for chunk in response.streaming_content])
        return response, body

    async def test_proxies_playlist(self):
        with self.upstream(200, "application/vnd.apple.mpegurl", b"#EXTM3U"):
            response, body = await self.get("/p/cams.example/live/playlist.m3u8")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response["Content-Type"], "application/vnd.apple.mpegurl")
        self.assertEqual(body, b"#EXTM3U")
        [request] = self.requests
        self.assertEqual(str(request.url), "https://cams.example/live/playlist.m3u8")
        self.assertEqual(request.headers["Referer"], "https://referer.example")

    async def test_proxies_segment(self):
        with self.upstream(200, "video/mp2t", b"\x47" * 188):
            response, body = await self.get("/p/cams.example/live/media_1.ts")

        self.assertEqual(response["Content-Type"], "video/mp2t")
        self.assertEqual(body, b"\x47" * 188)

    async def test_passes_through_upstream_errors(self):
        with self.upstream(404, "text/html", b"Not Found"):
            response, body = await self.get("/p/cams.example/live/media_0.ts")

        self.assertEqual(response.status_code, 404)
        self.assertEqual(body, b"Not Found")

    async def test_requires_login(self):
        await self.async_client.alogout()
        with self.upstream(200, "video/mp2t", b""):
            response = await self.async_client.get("/p/cams.example/live/media_1.ts")

        self.assertEqual(response.status_code, 302)
        self.assertEqual(self.requests, [])
