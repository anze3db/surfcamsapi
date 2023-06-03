from django.contrib import admin

from cams.models import Cam, Category
from adminsortable2.admin import SortableInlineAdminMixin, SortableAdminBase


class CamInline(SortableInlineAdminMixin, admin.TabularInline):
    # We don't use the Button model but rather the juction model specified on Panel.
    model = Category.cam_set.through


# Register your models here.
class CategoryAdmin(SortableAdminBase, admin.ModelAdmin):
    list_display = ("title", "color")
    inlines = (CamInline,)


class CamAdmin(SortableAdminBase, admin.ModelAdmin):
    list_display = ("title", "subtitle", "url")


admin.site.register(Category, CategoryAdmin)
admin.site.register(Cam, CamAdmin)
