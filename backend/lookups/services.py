import json
import os
import re
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from django.db import transaction
from django.utils import timezone

from .models import PhoneLookupCache


class LookupError(Exception):
    pass


class UpstreamLookupError(LookupError):
    pass


class InvalidPhoneError(LookupError):
    pass


def normalize_phone(phone_number: str) -> tuple[str, str]:
    digits = re.sub(r'\D+', '', phone_number or '')

    if len(digits) == 11 and digits.startswith('1'):
        digits = digits[1:]

    if len(digits) != 10:
        raise InvalidPhoneError('Enter a valid 10 digit US phone number.')

    normalized = f'+1{digits}'
    display = f'({digits[0:3]}) {digits[3:6]}-{digits[6:10]}'
    return normalized, display


def lookup_phone(phone_number: str) -> dict[str, Any]:
    normalized_phone, display_phone = normalize_phone(phone_number)
    cached = PhoneLookupCache.objects.filter(normalized_phone=normalized_phone).first()

    if cached:
        return build_lookup_response(cached, source='cache')

    upstream_response = fetch_phone_lookup(normalized_phone[-10:])
    cache = persist_phone_lookup(normalized_phone, display_phone, upstream_response)
    return build_lookup_response(cache, source='upstream')


def fetch_phone_lookup(phone_digits: str) -> dict[str, Any]:
    api_key = os.environ.get('CALLLOOM_API_KEY')
    if not api_key:
        raise UpstreamLookupError('CALLLOOM_API_KEY is not configured.')

    endpoint = os.environ.get(
        'CALLLOOM_PHONE_LOOKUP_URL',
        'https://api.callloom.com/api/people-lookup/get-phone-lookup/',
    )
    timeout = float(os.environ.get('CALLLOOM_TIMEOUT_SECONDS', '20'))
    payload = json.dumps({'phone_number': phone_digits}).encode('utf-8')
    request = Request(
        endpoint,
        data=payload,
        headers={
            'Content-Type': 'application/json',
            'X-API-Key': api_key,
        },
        method='POST',
    )

    try:
        with urlopen(request, timeout=timeout) as response:
            body = response.read().decode('utf-8')
            return json.loads(body)
    except HTTPError as exc:
        body = exc.read().decode('utf-8', errors='replace')
        raise UpstreamLookupError(f'Lookup provider returned {exc.code}: {body[:240]}') from exc
    except (URLError, TimeoutError) as exc:
        raise UpstreamLookupError('Lookup provider is unavailable. Please try again.') from exc
    except json.JSONDecodeError as exc:
        raise UpstreamLookupError('Lookup provider returned an invalid response.') from exc


@transaction.atomic
def persist_phone_lookup(
    normalized_phone: str,
    display_phone: str,
    response: dict[str, Any],
) -> PhoneLookupCache:
    persons = response.get('data', {}).get('persons', [])
    cache, _ = PhoneLookupCache.objects.update_or_create(
        normalized_phone=normalized_phone,
        defaults={
            'display_phone': display_phone,
            'status': str(response.get('status', 'unknown')),
            'message': str(response.get('message', '')),
            'result_count': len(persons),
            'raw_response': response,
            'updated_at': timezone.now(),
        },
    )
    return cache


def build_lookup_response(cache: PhoneLookupCache, source: str) -> dict[str, Any]:
    raw_response = cache.raw_response or {}
    persons = raw_response.get('data', {}).get('persons', [])
    pagination = raw_response.get('data', {}).get('pagination', {})

    return {
        'status': cache.status,
        'message': cache.message,
        'source': source,
        'query': {
            'phone_number': cache.display_phone,
            'normalized_phone': cache.normalized_phone,
        },
        'data': {
            'persons': [serialize_person(person) for person in persons],
            'pagination': pagination,
            'result_count': cache.result_count,
        },
    }


def serialize_person(person: dict[str, Any]) -> dict[str, Any]:
    addresses = person.get('addresses') or []
    phones = person.get('phones') or []
    relatives = person.get('relatives') or []
    aliases = person.get('merged_names_json') or person.get('akas_json') or []
    primary_phone = phones[0] if phones else {}
    primary_address = addresses[0] if addresses else {}
    full_name = ' '.join(
        part
        for part in [
            person.get('first_name'),
            person.get('middle_name'),
            person.get('last_name'),
        ]
        if part
    ).strip() or 'Unknown person'

    return {
        'id': str(person.get('id') or full_name),
        'name': full_name,
        'age': person.get('age'),
        'confidence': estimate_confidence(person),
        'phone': primary_phone.get('phone_number') or 'Not available',
        'phone_type': primary_phone.get('phone_type') or 'Unknown',
        'address': primary_address.get('full_address') or format_address(primary_address),
        'stats': {
            'phones': len(phones),
            'addresses': len(addresses),
            'relatives': len(relatives),
        },
        'aliases': [format_alias(alias) for alias in aliases[:8] if format_alias(alias)],
        'updated': primary_phone.get('last_reported_date')
        or primary_address.get('last_reported_date')
        or 'Recently fetched',
        'raw': {
            'phones': phones,
            'addresses': addresses,
            'emails': person.get('emails') or [],
            'relatives': relatives,
            'associates': person.get('associates') or [],
        },
    }


def estimate_confidence(person: dict[str, Any]) -> str:
    score = 72
    if person.get('phones'):
        score += 10
    if person.get('addresses'):
        score += 8
    if person.get('age'):
        score += 4
    if person.get('relatives'):
        score += 3
    return f'{min(score, 98)}%'


def format_address(address: dict[str, Any]) -> str:
    parts = [
        address.get('street'),
        address.get('city'),
        address.get('state'),
        address.get('zip_code'),
    ]
    return ', '.join(str(part) for part in parts if part) or 'Not available'


def format_alias(alias: dict[str, Any]) -> str:
    return ' '.join(
        part
        for part in [
            alias.get('firstName'),
            alias.get('middleName'),
            alias.get('lastName'),
        ]
        if part
    ).strip()
