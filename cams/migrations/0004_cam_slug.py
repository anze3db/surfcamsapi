# Generated by Django 5.1.2 on 2024-11-02 11:26
from django.db import migrations, models
from django.utils.text import slugify


def set_slug_field(apps, schema_editor):
    Cam = apps.get_model("cams", "Cam")
    cams_to_update = []
    slugs = set()
    for cam in Cam.objects.all():
        cam.slug = slugify(cam.title)
        if cam.slug in slugs:
            cam.slug = f"{cam.slug}-2"
        cams_to_update.append(cam)
        slugs.add(cam.slug)
    Cam.objects.bulk_update(cams_to_update, ["slug"], batch_size=100)


class Migration(migrations.Migration):
    dependencies = [
        ("cams", "0003_cam_spot_id"),
    ]

    operations = [
        migrations.AddField(
            model_name="cam",
            name="slug",
            field=models.SlugField(default=None, max_length=100, null=True),
        ),
        migrations.RunPython(set_slug_field, reverse_code=migrations.RunPython.noop),
    ]
