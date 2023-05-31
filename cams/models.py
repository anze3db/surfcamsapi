from django.db import models


# Create your models here.
class Category(models.Model):
    title = models.CharField(max_length=100)
    color = models.CharField(max_length=7)

    def __str__(self):
        return self.title


class Cam(models.Model):
    title = models.CharField(max_length=100)
    subtitle = models.CharField(max_length=100)
    url = models.CharField(max_length=4000)
    title_color = models.CharField(max_length=7)
    subtitle_color = models.CharField(max_length=7)
    background_color = models.CharField(max_length=7)

    category = models.ForeignKey(Category, on_delete=models.CASCADE)

    def __str__(self):
        return self.title + " - " + self.subtitle
