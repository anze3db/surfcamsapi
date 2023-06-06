from django.test import TestCase, override_settings

from cams.models import Cam, Category, CategoryCam


class TestCamsApi(TestCase):
    maxDiff = None

    @classmethod
    def setUpTestData(cls):
        cls.cat1 = cat1 = Category.objects.create(title="Cat 1", color="#000000")
        cls.cat2 = cat2 = Category.objects.create(title="Cat 2", color="#000000")
        cls.cat3 = Category.objects.create(title="Cat 3", color="#000000")

        cls.cam1 = cam1 = Cam.objects.create(title="Cam 1")
        cls.cam2 = cam2 = Cam.objects.create(title="Cam 2")
        cls.cam3 = cam3 = Cam.objects.create(title="Cam 3")
        cam4 = Cam.objects.create(title="Cam 4")

        cam1.categories.add(cat1)
        cam2.categories.add(cat2)
        cam3.categories.add(cat1, cat2)

    def test_get_cams(self):
        with self.assertNumQueries(2):
            response = self.client.get("/api/cams.json")
        self.assertEqual(response.status_code, 200)

        self.assertEqual(
            [
                {
                    "title": cat["title"],
                    "color": cat["color"],
                    "cams": [
                        {"title": cam["title"], "detailUrl": cam["detailUrl"]}
                        for cam in cat["cams"]
                    ],
                }
                for cat in response.json()["categories"]
            ],
            [
                {
                    "title": "Cat 1",
                    "color": "#000000",
                    "cams": [
                        {
                            "title": "Cam 1",
                            "detailUrl": f"http://localhost:8000/api/cams/{self.cam1.id}",
                        },
                        {
                            "title": "Cam 3",
                            "detailUrl": f"http://localhost:8000/api/cams/{self.cam3.id}",
                        },
                    ],
                },
                {
                    "title": "Cat 2",
                    "color": "#000000",
                    "cams": [
                        {
                            "title": "Cam 2",
                            "detailUrl": f"http://localhost:8000/api/cams/{self.cam2.id}",
                        },
                        {
                            "title": "Cam 3",
                            "detailUrl": f"http://localhost:8000/api/cams/{self.cam3.id}",
                        },
                    ],
                },
                {"title": "Cat 3", "color": "#000000", "cams": []},
            ],
        )

    def test_get_cams_w_category_order(self):
        self.cat1.order = 2
        self.cat3.order = 1
        self.cat2.order = 3
        Category.objects.bulk_update([self.cat1, self.cat2, self.cat3], ["order"])

        with self.assertNumQueries(2):
            response = self.client.get("/api/cams.json")
        self.assertEqual(response.status_code, 200)

        self.assertEqual(
            [
                {
                    "title": cat["title"],
                    "color": cat["color"],
                    "cams": [{"title": cam["title"]} for cam in cat["cams"]],
                }
                for cat in response.json()["categories"]
            ],
            [
                {"title": "Cat 3", "color": "#000000", "cams": []},
                {
                    "title": "Cat 1",
                    "color": "#000000",
                    "cams": [{"title": "Cam 1"}, {"title": "Cam 3"}],
                },
                {
                    "title": "Cat 2",
                    "color": "#000000",
                    "cams": [{"title": "Cam 2"}, {"title": "Cam 3"}],
                },
            ],
        )

    def test_get_cams_w_cam_order(self):
        all_cat1 = list(CategoryCam.objects.filter(category=self.cat1))
        all_cat1[1].order = 1
        all_cat1[0].order = 2
        CategoryCam.objects.bulk_update(all_cat1, ["order"])

        with self.assertNumQueries(2):
            response = self.client.get("/api/cams.json")
        self.assertEqual(response.status_code, 200)

        self.assertEqual(
            [
                {
                    "title": cat["title"],
                    "color": cat["color"],
                    "cams": [{"title": cam["title"]} for cam in cat["cams"]],
                }
                for cat in response.json()["categories"]
            ],
            [
                {
                    "title": "Cat 1",
                    "color": "#000000",
                    "cams": [{"title": "Cam 3"}, {"title": "Cam 1"}],
                },
                {
                    "title": "Cat 2",
                    "color": "#000000",
                    "cams": [{"title": "Cam 2"}, {"title": "Cam 3"}],
                },
                {"title": "Cat 3", "color": "#000000", "cams": []},
            ],
        )


class TestHealth(TestCase):
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
