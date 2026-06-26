from django.db import models
from django.utils import timezone


class Feedback(models.Model):
    EXPERIENCE_CHOICES = [
        ('Excellent', 'Excellent'),
        ('Good', 'Good'),
        ('Average', 'Average'),
        ('Difficult', 'Difficult'),
    ]

    name = models.CharField(max_length=120, blank=True)
    email = models.EmailField(blank=True)
    experience = models.CharField(max_length=24, choices=EXPERIENCE_CHOICES)
    areas = models.JSONField(default=list, blank=True)
    feature = models.CharField(max_length=160, blank=True)
    device = models.CharField(max_length=40, blank=True)
    details = models.TextField()
    suggestion = models.TextField(blank=True)
    page_url = models.CharField(max_length=255, blank=True)
    user_agent = models.CharField(max_length=255, blank=True)
    public_ip = models.GenericIPAddressField(null=True, blank=True, db_index=True)
    is_read = models.BooleanField(default=False, db_index=True)
    read_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['is_read', '-created_at']),
            models.Index(fields=['public_ip', '-created_at']),
        ]

    def __str__(self):
        author = self.email or self.name or 'Anonymous'
        return f'{author} - {self.experience}'

    def mark_as_read(self):
        if self.is_read:
            return

        self.is_read = True
        self.read_at = timezone.now()
        self.save(update_fields=['is_read', 'read_at', 'updated_at'])
