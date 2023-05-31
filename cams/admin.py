from django.contrib import admin

from cams.models import Cam, Category


# Register your models here.
class CategoryAdmin(admin.ModelAdmin):
    list_display = ("title", "color")


class CamAdmin(admin.ModelAdmin):
    list_display = ("title", "subtitle", "url")


admin.site.register(Category, CategoryAdmin)
admin.site.register(Cam, CamAdmin)
