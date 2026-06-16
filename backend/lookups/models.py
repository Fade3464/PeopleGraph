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
