from django.db import models


class PhoneLookupCache(models.Model):
    normalized_phone = models.CharField(max_length=16, unique=True, db_index=True)
    display_phone = models.CharField(max_length=20)
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
    first_name_normalized = models.CharField(max_length=80, db_index=True)
    last_name_normalized = models.CharField(max_length=160, db_index=True)
    location_normalized = models.CharField(max_length=255, db_index=True)
    address = models.CharField(max_length=255, blank=True, db_index=True)
    zipcode = models.CharField(max_length=10, blank=True, db_index=True)
    full_name = models.CharField(max_length=255)
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
