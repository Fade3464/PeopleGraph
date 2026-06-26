import os

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand, CommandError


class Command(BaseCommand):
    help = 'Create or update the configured Django admin superuser.'

    def handle(self, *args, **options):
        email = os.environ.get('DJANGO_ADMIN_EMAIL', '').strip().lower()
        password = os.environ.get('DJANGO_ADMIN_PASSWORD', '')

        if not email and not password:
            self.stdout.write('DJANGO_ADMIN_EMAIL and DJANGO_ADMIN_PASSWORD are not set; skipping admin bootstrap.')
            return

        if not email or not password:
            raise CommandError('Both DJANGO_ADMIN_EMAIL and DJANGO_ADMIN_PASSWORD are required for admin bootstrap.')

        User = get_user_model()
        user, created = User.objects.get_or_create(
            username=email,
            defaults={
                'email': email,
                'is_staff': True,
                'is_superuser': True,
                'is_active': True,
            },
        )

        changed_fields = []
        if user.email != email:
            user.email = email
            changed_fields.append('email')
        if not user.is_staff:
            user.is_staff = True
            changed_fields.append('is_staff')
        if not user.is_superuser:
            user.is_superuser = True
            changed_fields.append('is_superuser')
        if not user.is_active:
            user.is_active = True
            changed_fields.append('is_active')

        user.set_password(password)
        changed_fields.append('password')
        user.save(update_fields=changed_fields if not created else None)

        action = 'Created' if created else 'Updated'
        self.stdout.write(self.style.SUCCESS(f'{action} Django admin user: {email}'))
