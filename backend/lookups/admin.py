from django import forms
from django.contrib import admin
from django.core.exceptions import ValidationError

from .models import (
    BlacklistLookupCache,
    NameAddrLookupCache,
    PhoneLookupAudit,
    PhoneLookupCache,
    SecondaryRelayConfiguration,
)


@admin.register(PhoneLookupCache)
class PhoneLookupCacheAdmin(admin.ModelAdmin):
    list_display = (
        'display_phone',
        'normalized_phone',
        'provider',
        'secondary_attempted',
        'status',
        'result_count',
        'updated_at',
    )
    search_fields = ('display_phone', 'normalized_phone')
    list_filter = ('provider', 'secondary_attempted', 'status')
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


@admin.register(NameAddrLookupCache)
class NameAddrLookupCacheAdmin(admin.ModelAdmin):
    list_display = (
        'full_name',
        'address',
        'zipcode',
        'provider',
        'secondary_attempted',
        'status',
        'result_count',
        'updated_at',
    )
    search_fields = (
        'full_name',
        'address',
        'zipcode',
        'first_name_normalized',
        'last_name_normalized',
    )
    list_filter = ('provider', 'secondary_attempted', 'status')
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


class SecondaryRelayConfigurationForm(forms.ModelForm):
    api_token = forms.CharField(
        required=False,
        min_length=32,
        max_length=255,
        widget=forms.PasswordInput(render_value=False),
        help_text='Enter a new relay bearer token. Leave blank when editing to keep the current token.',
    )

    class Meta:
        model = SecondaryRelayConfiguration
        fields = '__all__'

    def clean_api_token(self):
        token = (self.cleaned_data.get('api_token') or '').strip()
        if token:
            return token
        if self.instance.pk and self.instance.api_token:
            return self.instance.api_token
        raise ValidationError('Enter the relay bearer token.')


@admin.register(SecondaryRelayConfiguration)
class SecondaryRelayConfigurationAdmin(admin.ModelAdmin):
    form = SecondaryRelayConfigurationForm
    list_display = ('enabled', 'phone_endpoint', 'name_endpoint', 'timeout_seconds', 'updated_at')
    readonly_fields = ('created_at', 'updated_at')

    def has_add_permission(self, request):
        return super().has_add_permission(request) and not SecondaryRelayConfiguration.objects.exists()
