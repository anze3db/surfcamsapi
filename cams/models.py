from django.conf import settings
from django.db import models
from django.urls import reverse


# Create your models here.
class Category(models.Model):
    title = models.CharField(max_length=100)
    color = models.CharField(max_length=7)
    order = models.PositiveIntegerField(
        default=0,
        blank=False,
        null=False,
    )

    def __str__(self):
        return self.title

    class Meta:
        verbose_name_plural = "categories"
        ordering = ["order"]


class Cam(models.Model):
    title = models.CharField(max_length=100)
    subtitle = models.CharField(max_length=100)
    url = models.CharField(max_length=4000)
    title_color = models.CharField(max_length=7)
    subtitle_color = models.CharField(max_length=7)
    background_color = models.CharField(max_length=7)

    categories = models.ManyToManyField(Category, through="CategoryCam")

    def __str__(self):
        return self.title + " - " + self.subtitle

    def detail_url(self):
        return f"{settings.HOST}{reverse('api-1.0.0:cam_detail', args=[self.id])}"


class CategoryCam(models.Model):
    category = models.ForeignKey(Category, on_delete=models.CASCADE)
    cam = models.ForeignKey(Cam, on_delete=models.CASCADE)
    order = models.PositiveIntegerField(default=0)

    def __str__(self):
        return str(self.order)

    class Meta:
        ordering = ["order"]
