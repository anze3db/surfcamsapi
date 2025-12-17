from adminsortable2.admin import (
    SortableAdminBase,
    SortableAdminMixin,
    SortableInlineAdminMixin,
)
from django.contrib import admin

from cams.models import Cam, Category


class CamInline(SortableInlineAdminMixin, admin.TabularInline):
    # We don't use the Button model but rather the juction model specified on Panel.
    model = Category.cam_set.through


# Register your models here.
@admin.register(Category)
class CategoryAdmin(SortableAdminMixin, admin.ModelAdmin):
    list_display = ("title", "color", "order")
    inlines = (CamInline,)


@admin.register(Cam)
class CamAdmin(SortableAdminBase, admin.ModelAdmin):
    list_display = ("title", "subtitle", "url")
