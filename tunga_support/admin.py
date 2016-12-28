from django import forms
from django.contrib import admin
from django.db import models

from tunga_support.models import SupportPage, SupportSection
from tunga_utils.admin import AdminAutoCreatedBy


@admin.register(SupportSection)
class SupportSectionAdmin(AdminAutoCreatedBy):
    list_display = ('title', 'slug', 'order', 'visibility', 'created_by', 'created_at')
    list_filter = ('created_at',)
    search_fields = ('title',)


@admin.register(SupportPage)
class SupportPageAdmin(AdminAutoCreatedBy):
    list_display = ('title', 'section', 'slug', 'order', 'visibility', 'created_by', 'created_at')
    list_filter = ('section', 'created_at')
    search_fields = ('title',)
    formfield_overrides = {models.TextField: {'widget': forms.Textarea(attrs={'class': 'ckeditor'})}}

    class Media:
        css = {
            'all': ('tunga/css/admin.css',)
        }
        js = ('https://cdnjs.cloudflare.com/ajax/libs/ckeditor/4.5.10/ckeditor.js',)
