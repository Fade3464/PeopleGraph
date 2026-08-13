from urllib.parse import urlsplit

from django.core.exceptions import ValidationError
from django.core.validators import MaxValueValidator, MinLengthValidator, MinValueValidator
from django.db import models


class PhoneLookupCache(models.Model):
    PROVIDER_PRIMARY = 'primary'
    PROVIDER_SECONDARY = 'secondary'
    PROVIDER_CHOICES = (
        (PROVIDER_PRIMARY, 'Primary'),
        (PROVIDER_SECONDARY, 'Secondary'),
    )

    normalized_phone = models.CharField(max_length=16, unique=True, db_index=True)
    display_phone = models.CharField(max_length=20)
    provider = models.CharField(max_length=16, choices=PROVIDER_CHOICES, default=PROVIDER_PRIMARY, db_index=True)
    secondary_attempted = models.BooleanField(default=False, db_index=True)
    status = models.CharField(max_length=32)
    message = models.CharField(max_length=255, blank=True)
    result_count = models.PositiveIntegerField(default=0, db_index=True)
    raw_response = models.JSONField()
    fetched_at = models.DateTimeField(auto_now_add=True, db_index=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-updated_at']
        indexes = [
            models.Index(fields=['normalized_phone', '-updated_at']),
            models.Index(fields=['result_count', '-updated_at']),
        ]

    def __str__(self):
        return f'{self.display_phone} ({self.result_count} result(s))'


class NameAddrLookupCache(models.Model):
    PROVIDER_PRIMARY = 'primary'
    PROVIDER_SECONDARY = 'secondary'
    PROVIDER_CHOICES = (
        (PROVIDER_PRIMARY, 'Primary'),
        (PROVIDER_SECONDARY, 'Secondary'),
    )

    first_name_normalized = models.CharField(max_length=80, db_index=True)
    last_name_normalized = models.CharField(max_length=160, db_index=True)
    location_normalized = models.CharField(max_length=255, db_index=True)
    address = models.CharField(max_length=255, blank=True, db_index=True)
    zipcode = models.CharField(max_length=10, blank=True, db_index=True)
    full_name = models.CharField(max_length=255)
    provider = models.CharField(max_length=16, choices=PROVIDER_CHOICES, default=PROVIDER_PRIMARY, db_index=True)
    secondary_attempted = models.BooleanField(default=False, db_index=True)
    status = models.CharField(max_length=32)
    message = models.CharField(max_length=255, blank=True)
    result_count = models.PositiveIntegerField(default=0, db_index=True)
    raw_response = models.JSONField()
    fetched_at = models.DateTimeField(auto_now_add=True, db_index=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-updated_at']
        constraints = [
            models.UniqueConstraint(
                fields=['first_name_normalized', 'last_name_normalized', 'location_normalized'],
                name='unique_name_address_lookup_cache_key',
            )
        ]
        indexes = [
            models.Index(
                fields=['first_name_normalized', 'last_name_normalized', 'location_normalized'],
                name='nameaddr_cache_key_idx',
            ),
            models.Index(fields=['zipcode', '-updated_at'], name='nameaddr_zip_updated_idx'),
            models.Index(fields=['result_count', '-updated_at'], name='nameaddr_count_updated_idx'),
        ]

    def __str__(self):
        location = self.zipcode or self.address
        return f'{self.full_name} at {location} ({self.result_count} result(s))'


class BlacklistLookupCache(models.Model):
    normalized_phone = models.CharField(max_length=16, unique=True, db_index=True)
    phone_digits = models.CharField(max_length=10, unique=True, db_index=True)
    display_phone = models.CharField(max_length=20)
    bla_code = models.CharField(max_length=255, blank=True, db_index=True)
    tcpa_status = models.CharField(max_length=255, blank=True, db_index=True)
    summary_status = models.CharField(max_length=255, blank=True, db_index=True)
    risk_category = models.CharField(max_length=64, blank=True, db_index=True)
    status_array = models.JSONField(default=list, blank=True)
    is_bad_number = models.BooleanField(default=False, db_index=True)
    raw_response = models.JSONField()
    fetched_at = models.DateTimeField(auto_now_add=True, db_index=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-updated_at']
        indexes = [
            models.Index(fields=['normalized_phone', '-updated_at']),
            models.Index(fields=['risk_category', '-updated_at']),
            models.Index(fields=['is_bad_number', '-updated_at']),
        ]

    def __str__(self):
        status = self.summary_status or 'Unknown status'
        return f'{self.display_phone} - {status}'


class PhoneLookupAudit(models.Model):
    timestamp = models.DateTimeField(auto_now_add=True, db_index=True)
    phone_number = models.CharField(max_length=20)
    normalized_phone = models.CharField(max_length=16, db_index=True)
    fetched_from_dbcache = models.BooleanField(default=False, db_index=True)
    fetched_from_bla_cache = models.BooleanField(default=False, db_index=True)
    public_ip = models.GenericIPAddressField(null=True, blank=True, db_index=True)

    class Meta:
        ordering = ['-timestamp']
        indexes = [
            models.Index(fields=['normalized_phone', '-timestamp']),
            models.Index(fields=['public_ip', '-timestamp']),
        ]

    def __str__(self):
        return f'{self.phone_number} from {self.public_ip or "unknown IP"} at {self.timestamp}'


class SecondaryRelayConfiguration(models.Model):
    singleton_key = models.PositiveSmallIntegerField(default=1, unique=True, editable=False)
    enabled = models.BooleanField(default=True, db_index=True)
    phone_endpoint = models.URLField(max_length=500)
    name_endpoint = models.URLField(max_length=500)
    api_token = models.CharField(max_length=255, validators=[MinLengthValidator(32)])
    timeout_seconds = models.PositiveSmallIntegerField(
        default=20,
        validators=[MinValueValidator(3), MaxValueValidator(60)],
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'secondary relay configuration'
        verbose_name_plural = 'secondary relay configuration'

    def clean(self):
        super().clean()
        self.phone_endpoint = self._validate_endpoint(
            self.phone_endpoint,
            '/v1/lookups/phone',
            'phone_endpoint',
        )
        self.name_endpoint = self._validate_endpoint(
            self.name_endpoint,
            '/v1/lookups/name',
            'name_endpoint',
        )

    @staticmethod
    def _validate_endpoint(value, expected_path, field_name):
        cleaned = (value or '').strip().rstrip('/')
        parsed = urlsplit(cleaned)
        if parsed.scheme != 'https':
            raise ValidationError({field_name: 'Relay endpoints must use HTTPS.'})
        if not parsed.hostname or parsed.username or parsed.password:
            raise ValidationError({field_name: 'Enter a valid relay endpoint.'})
        if parsed.query or parsed.fragment or parsed.path != expected_path:
            raise ValidationError(
                {field_name: f'Relay endpoint must end exactly with {expected_path}.'}
            )
        return cleaned

    def save(self, *args, **kwargs):
        self.singleton_key = 1
        self.full_clean()
        return super().save(*args, **kwargs)

    def __str__(self):
        status = 'enabled' if self.enabled else 'disabled'
        return f'Secondary lookup relay ({status})'
