from django.contrib import admin


class AdminAutoCreatedBy(admin.ModelAdmin):
    exclude = ('created_by',)

    def save_model(self, request, obj, form, change):
        obj.created_by = request.user
        obj.save()
