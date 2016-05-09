from django.contrib import admin

from tunga_messages.models import Message, Reply, Reception


class RecipientInline(admin.TabularInline):
    model = Reception
    exclude = ('read_at',)
    extra = 1


@admin.register(Message)
class MessageAdmin(admin.ModelAdmin):
    list_display = ('user', 'subject', 'is_broadcast', 'created_at')
    inlines = (RecipientInline,)


@admin.register(Reply)
class ReplyAdmin(admin.ModelAdmin):
    list_display = ('user', 'body', 'is_broadcast', 'created_at')

