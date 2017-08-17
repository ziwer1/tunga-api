from django import forms
from django.contrib import admin
from django.db import models

from tunga_pages.models import SkillPage, SkillPageProfile
from tunga_utils.admin import AdminAutoCreatedBy


class SkillPageProfileInline(admin.StackedInline):
    verbose_name = 'profile info'
    model = SkillPageProfile
    exclude = ('created_by',)
    extra = 1
    raw_id_fields = ('user',)

    def save_model(self, request, obj, form, change):
        obj.created_by = request.user
        obj.save()


@admin.register(SkillPage)
class SkillPageAdmin(AdminAutoCreatedBy):
    list_display = (
        'keyword', 'skill', 'welcome_header', 'welcome_sub_header', 'welcome_cta', 'created_by', 'created_at'
    )
    list_filter = ('created_at', )
    search_fields = ('keyword', 'skill__name')
    inlines = (SkillPageProfileInline,)
    formfield_overrides = {
        models.CharField: {'widget': forms.Textarea(attrs={'rows': 2})},
        models.TextField: {'widget': forms.Textarea(attrs={'class': 'ckeditor'})}
    }

    class Media:
        css = {
            'all': ('tunga/css/admin.css',)
        }
        js = ('https://cdnjs.cloudflare.com/ajax/libs/ckeditor/4.5.10/ckeditor.js',)

    def save_formset(self, request, form, formset, change):
        instances = formset.save(commit=False)
        for instance in instances:
            instance.created_by = request.user
            instance.save()
        formset.save_m2m()
