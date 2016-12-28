from django.contrib import admin

from tunga_comments.models import Comment


@admin.register(Comment)
class CommentAdmin(admin.ModelAdmin):
    list_display = ('user', 'body', 'created_at')
    list_filter = ('created_at',)
    search_fields = ('body',)
