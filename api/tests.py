from django.test import TestCase, override_settings

from cams.models import Category


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
