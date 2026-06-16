from django.contrib import admin

from .models import PhoneLookupCache


@admin.register(PhoneLookupCache)
class PhoneLookupCacheAdmin(admin.ModelAdmin):
    list_display = (
        'display_phone',
        'normalized_phone',
        'status',
        'result_count',
        'updated_at',
    )
    search_fields = ('display_phone', 'normalized_phone')
    list_filter = ('status',)
    readonly_fields = ('fetched_at', 'updated_at')
