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
    slug = models.SlugField(max_length=100, unique=True)
    title = models.CharField(max_length=100)
    subtitle = models.CharField(max_length=100)
    url = models.CharField(max_length=4000)
    title_color = models.CharField(max_length=7, default="#ffffff")
    subtitle_color = models.CharField(max_length=7, default="#ffffff")
    background_color = models.CharField(max_length=7, default="#000000")

    categories = models.ManyToManyField(Category, through="CategoryCam")
    spot_id = models.CharField(max_length=100, blank=True, null=True)

    def __str__(self):
        return self.title + " - " + self.subtitle

    def detail_url(self):
        return f"{settings.HOST}{reverse('api-1.0.0:cams_detail', args=[self.id])}"

    def image_name(self):
        match self.subtitle:
            case "Beachcam":
                return "beachcam.jpeg"
            case "Surfline":
                return "surfline.webp"
            case _:
                return "unknown.png"

    def bullet_color(self):
        match self.subtitle:
            case "Beachcam":
                return "yellow"
            case "Surfline":
                return "#15a0eb"
            case _:
                return "gray"

    async def related_cams(self):
        categories = [
            cat
            async for cat in self.categories.all()
            .prefetch_related(
                models.Prefetch(
                    "cam_set", queryset=Cam.objects.order_by("categorycam__order")
                )
            )
            .order_by("order")
        ]
        cams = []
        for cat in list(categories):
            for cam in cat.cam_set.all():
                cams.append(cam)
        return cams


class CategoryCam(models.Model):
    category = models.ForeignKey(Category, on_delete=models.CASCADE)
    cam = models.ForeignKey(Cam, on_delete=models.CASCADE)
    order = models.PositiveIntegerField(default=0)

    def __str__(self):
        return str(self.order)

    class Meta:
        ordering = ["order"]
