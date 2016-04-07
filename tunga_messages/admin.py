from django.contrib import admin

from tunga_messages.models import Message, Reply, Recipient


class RecipientInline(admin.TabularInline):
    model = Recipient
    exclude = ('read_at', 'status')
    extra = 1


@admin.register(Message)
class MessageAdmin(admin.ModelAdmin):
    list_display = ('user', 'subject', 'is_broadcast', 'status', 'created_at')
    inlines = (RecipientInline,)


@admin.register(Reply)
class ReplyAdmin(admin.ModelAdmin):
    list_display = ('user', 'body', 'is_broadcast', 'created_at')

