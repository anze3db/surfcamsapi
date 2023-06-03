import json

from django.core.management.base import BaseCommand, CommandError

from cams.models import Cam, Category


class Command(BaseCommand):
    help = "Imports cams and categories from JSON file"

    def add_arguments(self, parser):
        parser.add_argument("json_file", type=str)

    def handle(self, *args, json_file: str | None = None, **options):
        if not json_file:
            raise CommandError("Please provide a JSON file")

        with open(json_file) as f:
            cams_json = json.load(f)

        Cam.objects.all().delete()
        Category.objects.all().delete()

        cams = set()
        for category in cams_json["categories"]:
            category_model = Category(title=category["title"], color=category["color"])
            category_model.save()
            for cam in category["cams"]:
                lookup = cam["url"]
                if lookup in cams:
                    Cam.objects.filter(url=cam["url"]).get().categories.add(
                        category_model
                    )
                    continue
                cams.add(lookup)

                cam_model = Cam(
                    title=cam["title"],
                    subtitle=cam["subTitle"],
                    url=cam["url"],
                    title_color=cam["titleColor"],
                    subtitle_color=cam["subTitleColor"],
                    background_color=cam["backgroundColor"],
                )
                cam_model.save()
                cam_model.categories.add(category_model)
        self.stdout.write(self.style.SUCCESS("Done!"))
