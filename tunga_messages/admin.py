from django.contrib import admin

from tunga_messages.models import Message, Channel, ChannelUser


class ChannelUserInline(admin.TabularInline):
    model = ChannelUser
    exclude = ('last_read', 'read_at')
    extra = 1


@admin.register(Channel)
class ChannelAdmin(admin.ModelAdmin):
    inlines = (ChannelUserInline,)


@admin.register(Message)
class MessageAdmin(admin.ModelAdmin):
    list_display = ('user', 'body', 'created_at')


