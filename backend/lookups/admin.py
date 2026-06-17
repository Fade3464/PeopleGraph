from django.contrib import admin

from .models import BlacklistLookupCache, PhoneLookupAudit, PhoneLookupCache


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


@admin.register(BlacklistLookupCache)
class BlacklistLookupCacheAdmin(admin.ModelAdmin):
    list_display = (
        'display_phone',
        'bla_code',
        'tcpa_status',
        'summary_status',
        'risk_category',
        'is_bad_number',
        'updated_at',
    )
    search_fields = ('display_phone', 'normalized_phone', 'phone_digits')
    list_filter = ('risk_category', 'is_bad_number', 'bla_code')
    readonly_fields = ('fetched_at', 'updated_at')


@admin.register(PhoneLookupAudit)
class PhoneLookupAuditAdmin(admin.ModelAdmin):
    list_display = (
        'timestamp',
        'phone_number',
        'public_ip',
        'fetched_from_dbcache',
        'fetched_from_bla_cache',
    )
    search_fields = ('phone_number', 'normalized_phone', 'public_ip')
    list_filter = ('fetched_from_dbcache', 'fetched_from_bla_cache')
    readonly_fields = (
        'timestamp',
        'phone_number',
        'normalized_phone',
        'fetched_from_dbcache',
        'fetched_from_bla_cache',
        'public_ip',
    )
