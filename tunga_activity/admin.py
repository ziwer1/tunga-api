from django.contrib import admin

from tunga_activity.models import ActivityReadLog
from tunga_utils.admin import ReadOnlyModelAdmin


@admin.register(ActivityReadLog)
class ActivityReadLogAdmin(ReadOnlyModelAdmin):
    list_display = ('__str__', 'user', 'created_at', 'last_read', 'last_email_at')
    list_filter = ('last_email_at',)
