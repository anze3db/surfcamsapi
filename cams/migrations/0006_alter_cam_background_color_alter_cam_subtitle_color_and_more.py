# Generated by Django 5.1.3 on 2024-11-09 00:49

from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("cams", "0005_alter_cam_slug"),
    ]

    operations = [
        migrations.AlterField(
            model_name="cam",
            name="background_color",
            field=models.CharField(default="#000000", max_length=7),
        ),
        migrations.AlterField(
            model_name="cam",
            name="subtitle_color",
            field=models.CharField(default="#ffffff", max_length=7),
        ),
        migrations.AlterField(
            model_name="cam",
            name="title_color",
            field=models.CharField(default="#ffffff", max_length=7),
        ),
    ]