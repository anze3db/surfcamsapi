# Generated by Django 5.1.2 on 2024-11-02 17:25

from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("cams", "0004_cam_slug"),
    ]

    operations = [
        migrations.AlterField(
            model_name="cam",
            name="slug",
            field=models.SlugField(max_length=100, unique=True),
        ),
    ]
