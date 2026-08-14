import ipaddress
import json
from datetime import timedelta
from urllib.error import HTTPError, URLError
from urllib.parse import quote
from urllib.request import Request, urlopen

from django.conf import settings
from django.utils import timezone

from .models import LookupIPAccessDecision


class RegionAccessError(Exception):
    pass


class RegionRestrictedError(RegionAccessError):
    pass


class RegionVerificationError(RegionAccessError):
    pass


def enforce_lookup_region(ip_address):
    if not settings.LOOKUP_REGION_ENFORCEMENT_ENABLED:
        return None

    try:
        canonical_ip = str(ipaddress.ip_address(ip_address or ''))
    except ValueError as exc:
        raise RegionVerificationError('Unable to verify your region.') from exc

    parsed_ip = ipaddress.ip_address(canonical_ip)
    if not parsed_ip.is_global:
        if settings.DEBUG and settings.LOOKUP_ALLOW_PRIVATE_IPS_IN_DEBUG:
            return None
        raise RegionVerificationError('Unable to verify your region.')

    now = timezone.now()
    cached = LookupIPAccessDecision.objects.filter(
        ip_address=canonical_ip,
        expires_at__gt=now,
    ).first()
    if cached:
        if cached.allowed:
            return cached
        raise RegionRestrictedError(settings.LOOKUP_REGION_RESTRICTED_MESSAGE)

    payload = fetch_ipinfo_lite(canonical_ip)
    country_code = str(payload.get('country_code') or '').strip().upper()[:2]
    country = str(payload.get('country') or '').strip()[:100]
    if len(country_code) != 2:
        raise RegionVerificationError('Unable to verify your region.')

    allowed = country_code == settings.LOOKUP_ALLOWED_COUNTRY_CODE
    lifetime = (
        timedelta(days=settings.IPINFO_ALLOWED_CACHE_DAYS)
        if allowed
        else timedelta(hours=settings.IPINFO_DENIED_CACHE_HOURS)
    )
    decision, _ = LookupIPAccessDecision.objects.update_or_create(
        ip_address=canonical_ip,
        defaults={
            'country_code': country_code,
            'country': country,
            'allowed': allowed,
            'provider': 'ipinfo-lite',
            'expires_at': now + lifetime,
        },
    )
    if not allowed:
        raise RegionRestrictedError(settings.LOOKUP_REGION_RESTRICTED_MESSAGE)
    return decision


def fetch_ipinfo_lite(ip_address):
    token = settings.IPINFO_API_TOKEN
    if not token:
        raise RegionVerificationError('Regional verification is not configured.')

    endpoint = f'{settings.IPINFO_LITE_URL.rstrip("/")}/{quote(ip_address, safe=":")}'
    request = Request(
        endpoint,
        headers={
            'Accept': 'application/json',
            'Authorization': f'Bearer {token}',
            'User-Agent': 'PeopleGraph-Region-Check/1.0',
        },
        method='GET',
    )
    try:
        with urlopen(request, timeout=settings.IPINFO_TIMEOUT_SECONDS) as response:
            body = response.read(16385)
    except HTTPError as exc:
        exc.read(16384)
        raise RegionVerificationError('Regional verification is temporarily unavailable.') from exc
    except (URLError, OSError) as exc:
        raise RegionVerificationError('Regional verification is temporarily unavailable.') from exc

    if len(body) > 16384:
        raise RegionVerificationError('Regional verification returned too much data.')
    try:
        payload = json.loads(body.decode('utf-8'))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise RegionVerificationError('Regional verification returned invalid data.') from exc
    if not isinstance(payload, dict) or payload.get('bogon') is True:
        raise RegionVerificationError('Unable to verify your region.')
    return payload
