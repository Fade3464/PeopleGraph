import os
from urllib.parse import urlsplit, urlunsplit

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from lookups.models import SecondaryRelayConfiguration


def env_bool(name: str, default: bool) -> bool:
    value = os.environ.get(name)
    if value is None:
        return default
    normalized = value.strip().lower()
    if normalized in {'1', 'true', 'yes', 'on'}:
        return True
    if normalized in {'0', 'false', 'no', 'off'}:
        return False
    raise CommandError(f'{name} must be true or false.')


class Command(BaseCommand):
    help = 'Create or update the singleton secondary relay configuration from environment variables.'

    def handle(self, *args, **options):
        base_url = os.environ.get('SECONDARY_RELAY_BASE_URL', '').strip().rstrip('/')
        token = os.environ.get('SECONDARY_RELAY_API_TOKEN', '').strip()

        if not base_url or not token:
            raise CommandError(
                'SECONDARY_RELAY_BASE_URL and SECONDARY_RELAY_API_TOKEN are required '
                'when relay bootstrap is enabled.'
            )

        parsed = urlsplit(base_url)
        if (
            parsed.scheme != 'https'
            or not parsed.hostname
            or parsed.username
            or parsed.password
            or parsed.query
            or parsed.fragment
            or parsed.path not in {'', '/'}
        ):
            raise CommandError('SECONDARY_RELAY_BASE_URL must be an HTTPS origin with no path, query, or fragment.')

        try:
            timeout_seconds = int(os.environ.get('SECONDARY_RELAY_TIMEOUT_SECONDS', '20'))
        except ValueError as exc:
            raise CommandError('SECONDARY_RELAY_TIMEOUT_SECONDS must be an integer.') from exc
        if not 3 <= timeout_seconds <= 60:
            raise CommandError('SECONDARY_RELAY_TIMEOUT_SECONDS must be between 3 and 60.')

        enabled = env_bool('SECONDARY_RELAY_ENABLED', True)
        origin = urlunsplit((parsed.scheme, parsed.netloc, '', '', '')).rstrip('/')
        values = {
            'enabled': enabled,
            'phone_endpoint': f'{origin}/v1/lookups/phone',
            'name_endpoint': f'{origin}/v1/lookups/name',
            'api_token': token,
            'timeout_seconds': timeout_seconds,
        }

        with transaction.atomic():
            configuration = SecondaryRelayConfiguration.objects.select_for_update().filter(singleton_key=1).first()
            created = configuration is None
            if created:
                configuration = SecondaryRelayConfiguration(singleton_key=1, **values)
            else:
                for field, value in values.items():
                    setattr(configuration, field, value)
            configuration.save()

        action = 'Created' if created else 'Updated'
        self.stdout.write(
            self.style.SUCCESS(
                f'{action} secondary relay configuration for {parsed.hostname} '
                f'({"enabled" if enabled else "disabled"}).'
            )
        )
