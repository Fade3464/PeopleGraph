import json
import os
import re
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from django.db import transaction
from django.utils import timezone

from .models import BlacklistLookupCache, PhoneLookupCache


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
    phone_digits = normalized_phone[-10:]
    cached = PhoneLookupCache.objects.filter(normalized_phone=normalized_phone).first()

    if cached:
        response = build_lookup_response(cached, source='cache')
        response['blacklist'] = lookup_blacklist(phone_digits, normalized_phone, display_phone)
        return response

    upstream_response = fetch_phone_lookup(phone_digits)
    cache = persist_phone_lookup(normalized_phone, display_phone, upstream_response)
    response = build_lookup_response(cache, source='upstream')
    response['blacklist'] = lookup_blacklist(phone_digits, normalized_phone, display_phone)
    return response


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


def lookup_blacklist(phone_digits: str, normalized_phone: str, display_phone: str) -> dict[str, Any]:
    cached = BlacklistLookupCache.objects.filter(normalized_phone=normalized_phone).first()

    if cached:
        return build_blacklist_response(cached, source='cache')

    try:
        upstream_response = fetch_blacklist_lookup(phone_digits)
    except UpstreamLookupError as exc:
        return {
            'status': 'error',
            'message': str(exc),
            'source': 'error',
            'phone_number': display_phone,
            'normalized_phone': normalized_phone,
            'summary_status': 'Unavailable',
            'bla_code': '',
            'tcpa_status': 'Unavailable',
            'risk_category': 'unknown',
            'status_array': [],
            'is_bad_number': False,
        }

    cache = persist_blacklist_lookup(normalized_phone, phone_digits, display_phone, upstream_response)
    return build_blacklist_response(cache, source='upstream')


def fetch_blacklist_lookup(phone_digits: str) -> dict[str, Any]:
    api_key = os.environ.get('TCPA_BLACKLIST_API_KEY')
    if not api_key:
        raise UpstreamLookupError('TCPA_BLACKLIST_API_KEY is not configured.')

    endpoint = os.environ.get(
        'TCPA_BLACKLIST_LOOKUP_URL',
        'https://api.tcpablacklist.com/api/phone-lookup/',
    )
    timeout = float(os.environ.get('TCPA_BLACKLIST_TIMEOUT_SECONDS', '20'))
    payload = json.dumps({'phone': phone_digits}).encode('utf-8')
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
        raise UpstreamLookupError(f'TCPA provider returned {exc.code}: {body[:240]}') from exc
    except (URLError, TimeoutError) as exc:
        raise UpstreamLookupError('TCPA provider is unavailable. Please try again.') from exc
    except json.JSONDecodeError as exc:
        raise UpstreamLookupError('TCPA provider returned an invalid response.') from exc


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


@transaction.atomic
def persist_blacklist_lookup(
    normalized_phone: str,
    phone_digits: str,
    display_phone: str,
    response: dict[str, Any],
) -> BlacklistLookupCache:
    extracted = extract_blacklist_fields(response)
    cache, _ = BlacklistLookupCache.objects.update_or_create(
        normalized_phone=normalized_phone,
        defaults={
            'phone_digits': phone_digits,
            'display_phone': display_phone,
            'bla_code': extracted['bla_code'],
            'tcpa_status': extracted['tcpa_status'],
            'summary_status': extracted['summary_status'],
            'risk_category': extracted['risk_category'],
            'status_array': extracted['status_array'],
            'is_bad_number': extracted['is_bad_number'],
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


def build_blacklist_response(cache: BlacklistLookupCache, source: str) -> dict[str, Any]:
    extracted = extract_blacklist_fields(cache.raw_response or {})
    bla_code = cache.bla_code or extracted['bla_code']
    tcpa_status = cache.tcpa_status or extracted['tcpa_status']
    summary_status = cache.summary_status or extracted['summary_status']

    return {
        'status': 'ok',
        'message': tcpa_status or summary_status or 'No TCPA status returned',
        'source': source,
        'phone_number': cache.display_phone,
        'normalized_phone': cache.normalized_phone,
        'bla_code': bla_code,
        'tcpa_status': tcpa_status,
        'summary_status': summary_status,
        'risk_category': cache.risk_category,
        'status_array': cache.status_array,
        'is_bad_number': cache.is_bad_number,
        'raw': cache.raw_response,
    }


def extract_blacklist_fields(response: dict[str, Any]) -> dict[str, Any]:
    scrub = response.get('scrub') or {}
    lookup = response.get('lookup') or {}
    litigator = lookup.get('tcpa_litigator') or {}
    results = scrub.get('results') or litigator.get('results') or {}
    litigator_results = litigator.get('results') or {}

    bla_code = lookup.get('code') or ''
    tcpa_status = results.get('status') or litigator_results.get('status') or ''
    summary_status = (
        scrub.get('summary_status')
        or litigator.get('summary_status')
        or tcpa_status
        or lookup.get('message')
        or ''
    )
    risk_category = scrub.get('risk_category') or litigator.get('risk_category') or ''
    status_array = results.get('status_array') or []
    is_bad_number = bool(results.get('is_bad_number') or status_array)

    return {
        'bla_code': str(bla_code),
        'tcpa_status': str(tcpa_status),
        'summary_status': str(summary_status),
        'risk_category': str(risk_category),
        'status_array': status_array if isinstance(status_array, list) else [],
        'is_bad_number': is_bad_number,
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
