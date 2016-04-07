from django.contrib import admin

from tunga_comments.models import Comment


@admin.register(Comment)
class CommentAdmin(admin.ModelAdmin):
    pass
