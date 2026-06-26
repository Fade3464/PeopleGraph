from django.contrib import admin

from .models import Feedback


@admin.register(Feedback)
class FeedbackAdmin(admin.ModelAdmin):
    list_display = ('id', 'experience', 'display_author', 'feature', 'device', 'is_read', 'created_at')
    list_filter = ('experience', 'device', 'is_read', 'created_at')
    search_fields = ('name', 'email', 'feature', 'details', 'suggestion', 'public_ip')
    readonly_fields = ('created_at', 'updated_at', 'read_at', 'public_ip', 'user_agent')
    ordering = ('-created_at',)

    def display_author(self, obj):
        return obj.email or obj.name or 'Anonymous'

    display_author.short_description = 'Author'
