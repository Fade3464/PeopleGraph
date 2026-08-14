import json
import logging
import os
import re
import uuid
from dataclasses import dataclass
from http.client import HTTPException as HttpClientException
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import urlsplit, urlunsplit
from urllib.request import Request, urlopen

from django.conf import settings
from django.db import transaction
from django.utils import timezone

from .models import (
    BlacklistLookupCache,
    NameAddrLookupCache,
    PhoneLookupCache,
    SecondaryRelayConfiguration,
)


logger = logging.getLogger(__name__)


MAX_TURNSTILE_TOKEN_LENGTH = 2048
MAX_FULL_NAME_LENGTH = 255
MAX_LOCATION_LENGTH = 255
NAME_ALLOWED_PATTERN = re.compile(r"^[A-Za-z][A-Za-z .'\-]*$")
LOCATION_ALLOWED_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9 .,#'\-/]*$")
CONTROL_CHARACTER_PATTERN = re.compile(r'[\x00-\x1f\x7f]')
US_STATE_CODES = {
    'alabama': 'AL', 'alaska': 'AK', 'arizona': 'AZ', 'arkansas': 'AR', 'california': 'CA',
    'colorado': 'CO', 'connecticut': 'CT', 'delaware': 'DE', 'florida': 'FL', 'georgia': 'GA',
    'hawaii': 'HI', 'idaho': 'ID', 'illinois': 'IL', 'indiana': 'IN', 'iowa': 'IA',
    'kansas': 'KS', 'kentucky': 'KY', 'louisiana': 'LA', 'maine': 'ME', 'maryland': 'MD',
    'massachusetts': 'MA', 'michigan': 'MI', 'minnesota': 'MN', 'mississippi': 'MS',
    'missouri': 'MO', 'montana': 'MT', 'nebraska': 'NE', 'nevada': 'NV', 'new hampshire': 'NH',
    'new jersey': 'NJ', 'new mexico': 'NM', 'new york': 'NY', 'north carolina': 'NC',
    'north dakota': 'ND', 'ohio': 'OH', 'oklahoma': 'OK', 'oregon': 'OR',
    'pennsylvania': 'PA', 'rhode island': 'RI', 'south carolina': 'SC', 'south dakota': 'SD',
    'tennessee': 'TN', 'texas': 'TX', 'utah': 'UT', 'vermont': 'VT', 'virginia': 'VA',
    'washington': 'WA', 'west virginia': 'WV', 'wisconsin': 'WI', 'wyoming': 'WY',
    'district of columbia': 'DC',
}
US_STATE_ABBREVIATIONS = set(US_STATE_CODES.values())
US_ZIP_PATTERN = re.compile(r'(?<!\d)\d{5}(?:-\d{4})?(?!\d)')


class LookupError(Exception):
    pass


class UpstreamLookupError(LookupError):
    pass


class InvalidPhoneError(LookupError):
    pass


class InvalidNameAddressError(LookupError):
    pass


class TurnstileValidationError(LookupError):
    pass


@dataclass(frozen=True)
class RelayConfiguration:
    phone_endpoint: str
    name_endpoint: str
    api_token: str
    timeout_seconds: int


def validate_turnstile_token(token: str, remote_ip: str | None = None) -> dict[str, Any]:
    cleaned_token = (token or '').strip()
    if not cleaned_token:
        raise TurnstileValidationError('Complete the security check before searching.')

    if len(cleaned_token) > MAX_TURNSTILE_TOKEN_LENGTH:
        raise TurnstileValidationError('Security verification failed. Please try again.')

    secret_key = os.environ.get('TURNSTILE_SECRET_KEY')
    if not secret_key:
        raise TurnstileValidationError('Turnstile is not configured on the server.')

    endpoint = os.environ.get(
        'TURNSTILE_SITEVERIFY_URL',
        'https://challenges.cloudflare.com/turnstile/v0/siteverify',
    )
    timeout = float(os.environ.get('TURNSTILE_TIMEOUT_SECONDS', '10'))
    payload_data = {
        'secret': secret_key,
        'response': cleaned_token,
        'idempotency_key': str(uuid.uuid4()),
    }
    if remote_ip:
        payload_data['remoteip'] = remote_ip

    payload = json.dumps(payload_data).encode('utf-8')
    request = Request(
        endpoint,
        data=payload,
        headers={
            'Content-Type': 'application/json',
        },
        method='POST',
    )

    try:
        with urlopen(request, timeout=timeout) as response:
            body = response.read().decode('utf-8')
            verification = json.loads(body)
    except HTTPError as exc:
        exc.read()
        raise TurnstileValidationError('Security verification failed. Please try again.') from exc
    except (URLError, TimeoutError) as exc:
        raise TurnstileValidationError('Security verification is unavailable. Please try again.') from exc
    except json.JSONDecodeError as exc:
        raise TurnstileValidationError('Security verification returned an invalid response.') from exc

    if not verification.get('success'):
        raise TurnstileValidationError('Security verification failed. Please try again.')

    if settings.TURNSTILE_EXPECTED_ACTION and verification.get('action') != settings.TURNSTILE_EXPECTED_ACTION:
        raise TurnstileValidationError('Security verification failed. Please try again.')

    if settings.TURNSTILE_ALLOWED_HOSTNAMES:
        hostname = str(verification.get('hostname') or '').lower()
        allowed_hostnames = {item.lower() for item in settings.TURNSTILE_ALLOWED_HOSTNAMES}
        if hostname not in allowed_hostnames:
            raise TurnstileValidationError('Security verification failed. Please try again.')

    return verification


def normalize_phone(phone_number: str) -> tuple[str, str]:
    digits = re.sub(r'\D+', '', phone_number or '')

    if len(digits) == 11 and digits.startswith('1'):
        digits = digits[1:]

    if len(digits) != 10:
        raise InvalidPhoneError('Enter a valid 10 digit US phone number.')

    normalized = f'+1{digits}'
    display = f'({digits[0:3]}) {digits[3:6]}-{digits[6:10]}'
    return normalized, display


def normalize_name_address(full_name: str, address_or_zip: str) -> dict[str, str]:
    cleaned_name = re.sub(r'\s+', ' ', full_name or '').strip()
    cleaned_location = re.sub(r'\s+', ' ', address_or_zip or '').strip()

    if not cleaned_name:
        raise InvalidNameAddressError('Enter a full name to start a lookup.')

    if len(cleaned_name) > MAX_FULL_NAME_LENGTH:
        raise InvalidNameAddressError('Full name is too long.')

    if CONTROL_CHARACTER_PATTERN.search(cleaned_name):
        raise InvalidNameAddressError('Full name contains invalid characters.')

    if not NAME_ALLOWED_PATTERN.fullmatch(cleaned_name):
        raise InvalidNameAddressError('Full name contains invalid characters.')

    name_parts = cleaned_name.split(' ', 1)
    if len(name_parts) < 2 or not name_parts[1].strip():
        raise InvalidNameAddressError('Enter both first and last name.')

    if not cleaned_location:
        raise InvalidNameAddressError('Enter an address or zip code.')

    if len(cleaned_location) > MAX_LOCATION_LENGTH:
        raise InvalidNameAddressError('Address or zip code is too long.')

    if CONTROL_CHARACTER_PATTERN.search(cleaned_location):
        raise InvalidNameAddressError('Address or zip code contains invalid characters.')

    if not LOCATION_ALLOWED_PATTERN.fullmatch(cleaned_location):
        raise InvalidNameAddressError('Address or zip code contains invalid characters.')

    first_name = name_parts[0].strip()
    last_name = name_parts[1].strip()
    zipcode = cleaned_location if re.fullmatch(r'\d{5}(?:-\d{4})?', cleaned_location) else ''
    address = '' if zipcode else cleaned_location
    first_name_normalized = normalize_text(first_name)
    last_name_normalized = normalize_text(last_name)
    location_normalized = f'zip:{zipcode.lower()}' if zipcode else f'address:{normalize_text(address)}'

    return {
        'first_name': first_name,
        'last_name': last_name,
        'full_name': cleaned_name,
        'address': address,
        'zipcode': zipcode,
        'first_name_normalized': first_name_normalized,
        'last_name_normalized': last_name_normalized,
        'location_normalized': location_normalized,
    }


def normalize_text(value: str) -> str:
    return re.sub(r'\s+', ' ', value or '').strip().lower()


def lookup_phone(phone_number: str) -> dict[str, Any]:
    normalized_phone, display_phone = normalize_phone(phone_number)
    phone_digits = normalized_phone[-10:]
    cached = PhoneLookupCache.objects.filter(normalized_phone=normalized_phone).first()

    if cached and (cached.result_count > 0 or cached.secondary_attempted):
        response = build_lookup_response(cached, source='cache')
        response['blacklist'] = lookup_blacklist(phone_digits, normalized_phone, display_phone)
        return response

    if cached:
        try:
            secondary_response = fetch_secondary_phone_lookup(phone_digits)
            if response_has_persons(secondary_response):
                cached = persist_phone_lookup(
                    normalized_phone,
                    display_phone,
                    secondary_response,
                    provider=PhoneLookupCache.PROVIDER_SECONDARY,
                    secondary_attempted=True,
                )
                response = build_lookup_response(cached, source='upstream')
                response['blacklist'] = lookup_blacklist(phone_digits, normalized_phone, display_phone)
                return response
            cached = persist_phone_lookup(
                normalized_phone,
                display_phone,
                cached.raw_response,
                provider=PhoneLookupCache.PROVIDER_PRIMARY,
                secondary_attempted=True,
            )
        except UpstreamLookupError as exc:
            logger.warning('Secondary phone lookup unavailable: %s', exc)

        response = build_lookup_response(cached, source='cache')
        response['blacklist'] = lookup_blacklist(phone_digits, normalized_phone, display_phone)
        return response

    upstream_response = fetch_phone_lookup(phone_digits)
    provider = PhoneLookupCache.PROVIDER_PRIMARY
    secondary_attempted = False
    if not response_has_persons(upstream_response):
        try:
            secondary_response = fetch_secondary_phone_lookup(phone_digits)
            secondary_attempted = True
            if response_has_persons(secondary_response):
                upstream_response = secondary_response
                provider = PhoneLookupCache.PROVIDER_SECONDARY
        except UpstreamLookupError as exc:
            logger.warning('Secondary phone lookup unavailable: %s', exc)

    cache = persist_phone_lookup(
        normalized_phone,
        display_phone,
        upstream_response,
        provider=provider,
        secondary_attempted=secondary_attempted,
    )
    response = build_lookup_response(cache, source='upstream')
    response['blacklist'] = lookup_blacklist(phone_digits, normalized_phone, display_phone)
    return response


def lookup_name_address(full_name: str, address_or_zip: str) -> dict[str, Any]:
    normalized = normalize_name_address(full_name, address_or_zip)
    cached = NameAddrLookupCache.objects.filter(
        first_name_normalized=normalized['first_name_normalized'],
        last_name_normalized=normalized['last_name_normalized'],
        location_normalized=normalized['location_normalized'],
    ).first()

    state = ''
    if not normalized['zipcode'] and not contains_us_zip(normalized['address']):
        state = extract_us_state(normalized['address'])
    if cached and (cached.result_count > 0 or not state or cached.secondary_attempted):
        return build_name_address_response(cached, source='cache')

    if cached:
        try:
            secondary_response = fetch_secondary_name_lookup(
                normalized['first_name'],
                normalized['last_name'],
                state,
            )
            if response_has_persons(secondary_response):
                cached = persist_name_address_lookup(
                    normalized,
                    secondary_response,
                    provider=NameAddrLookupCache.PROVIDER_SECONDARY,
                    secondary_attempted=True,
                )
                return build_name_address_response(cached, source='upstream')
            cached = persist_name_address_lookup(
                normalized,
                cached.raw_response,
                provider=NameAddrLookupCache.PROVIDER_PRIMARY,
                secondary_attempted=True,
            )
        except UpstreamLookupError as exc:
            logger.warning('Secondary name lookup unavailable: %s', exc)
        return build_name_address_response(cached, source='cache')

    upstream_response = fetch_name_address_lookup(
        normalized['first_name'],
        normalized['last_name'],
        normalized['address'],
        normalized['zipcode'],
    )
    provider = NameAddrLookupCache.PROVIDER_PRIMARY
    secondary_attempted = False
    if not response_has_persons(upstream_response) and state:
        try:
            secondary_response = fetch_secondary_name_lookup(
                normalized['first_name'],
                normalized['last_name'],
                state,
            )
            secondary_attempted = True
            if response_has_persons(secondary_response):
                upstream_response = secondary_response
                provider = NameAddrLookupCache.PROVIDER_SECONDARY
        except UpstreamLookupError as exc:
            logger.warning('Secondary name lookup unavailable: %s', exc)

    cache = persist_name_address_lookup(
        normalized,
        upstream_response,
        provider=provider,
        secondary_attempted=secondary_attempted,
    )
    return build_name_address_response(cache, source='upstream')


def response_has_persons(response: dict[str, Any]) -> bool:
    return bool(response.get('data', {}).get('persons', []))


def extract_us_state(location: str) -> str:
    cleaned = normalize_text(location)
    for state_name in sorted(US_STATE_CODES, key=len, reverse=True):
        if re.search(rf'(?<![a-z]){re.escape(state_name)}(?![a-z])', cleaned):
            return US_STATE_CODES[state_name]

    state_match = re.search(r'(?<![A-Za-z])([A-Za-z]{2})(?:\s+\d{5}(?:-\d{4})?)?\s*$', location or '')
    if state_match:
        code = state_match.group(1).upper()
        if code in US_STATE_ABBREVIATIONS:
            return code
    return ''


def contains_us_zip(location: str) -> bool:
    return bool(US_ZIP_PATTERN.search(location or ''))


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
        exc.read()
        raise UpstreamLookupError(f'Lookup provider returned {exc.code}.') from exc
    except (URLError, TimeoutError) as exc:
        raise UpstreamLookupError('Lookup provider is unavailable. Please try again.') from exc
    except json.JSONDecodeError as exc:
        raise UpstreamLookupError('Lookup provider returned an invalid response.') from exc


def fetch_name_address_lookup(first_name: str, last_name: str, address: str, zipcode: str) -> dict[str, Any]:
    api_key = os.environ.get('CALLLOOM_API_KEY')
    if not api_key:
        raise UpstreamLookupError('CALLLOOM_API_KEY is not configured.')

    endpoint = os.environ.get(
        'CALLLOOM_NAME_ADDR_LOOKUP_URL',
        os.environ.get(
            'CALLLOOM_PHONE_LOOKUP_URL',
            'https://api.callloom.com/api/people-lookup/get-phone-lookup/',
        ),
    )
    timeout = float(os.environ.get('CALLLOOM_TIMEOUT_SECONDS', '20'))
    payload_data = {
        'first_name': first_name,
        'last_name': last_name,
    }
    if zipcode:
        payload_data['zip_code'] = zipcode
    else:
        payload_data['address'] = address

    payload = json.dumps(payload_data).encode('utf-8')
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
        exc.read()
        raise UpstreamLookupError(f'Lookup provider returned {exc.code}.') from exc
    except (URLError, TimeoutError) as exc:
        raise UpstreamLookupError('Lookup provider is unavailable. Please try again.') from exc
    except json.JSONDecodeError as exc:
        raise UpstreamLookupError('Lookup provider returned an invalid response.') from exc


def fetch_secondary_phone_lookup(phone_digits: str) -> dict[str, Any]:
    configuration = get_secondary_relay_configuration()
    return request_secondary_relay(
        configuration.phone_endpoint,
        {'phone_number': phone_digits},
        configuration,
        'phone',
    )


def fetch_secondary_name_lookup(first_name: str, last_name: str, state: str) -> dict[str, Any]:
    if state not in US_STATE_ABBREVIATIONS:
        raise UpstreamLookupError('Secondary name lookup requires a valid US state.')
    configuration = get_secondary_relay_configuration()
    return request_secondary_relay(
        configuration.name_endpoint,
        {'first_name': first_name, 'last_name': last_name, 'state': state},
        configuration,
        'name',
    )


def get_secondary_relay_configuration() -> RelayConfiguration:
    record = SecondaryRelayConfiguration.objects.filter(enabled=True).values(
        'phone_endpoint',
        'name_endpoint',
        'api_token',
        'timeout_seconds',
    ).first()
    if not record:
        raise UpstreamLookupError('Secondary lookup relay is not configured.')

    return RelayConfiguration(
        phone_endpoint=record['phone_endpoint'],
        name_endpoint=record['name_endpoint'],
        api_token=record['api_token'],
        timeout_seconds=record['timeout_seconds'],
    )


def probe_secondary_relay() -> dict[str, Any]:
    try:
        configuration = get_secondary_relay_configuration()
    except UpstreamLookupError:
        return {
            'status': 'not_configured',
            'relay': 'not_configured',
            'phone_api': 'unknown',
            'name_api': 'unknown',
        }

    parsed = urlsplit(configuration.phone_endpoint)
    health_endpoint = urlunsplit((parsed.scheme, parsed.netloc, '/health', '', ''))
    hostname = parsed.hostname or ''
    try:
        health_payload = request_relay_status_endpoint(
            health_endpoint,
            configuration.timeout_seconds,
        )
        relay_ok = health_payload.get('status') == 'ok'
    except UpstreamLookupError:
        return {
            'status': 'offline',
            'relay': 'offline',
            'phone_api': 'unknown',
            'name_api': 'unknown',
            'hostname': hostname,
        }

    try:
        diagnostics = request_relay_status_endpoint(
            urlunsplit((parsed.scheme, parsed.netloc, '/v1/diagnostics/upstream', '', '')),
            configuration.timeout_seconds,
            token=configuration.api_token,
            method='POST',
        )
    except UpstreamLookupError:
        diagnostics = {'status': 'error', 'checks': {}}

    checks = diagnostics.get('checks') if isinstance(diagnostics.get('checks'), dict) else {}
    phone_status = relay_probe_status(checks.get('phone'))
    name_status = relay_probe_status(checks.get('name'))
    overall = 'ok' if relay_ok and phone_status == 'ok' and name_status == 'ok' else 'degraded'
    return {
        'status': overall,
        'relay': 'online' if relay_ok else 'offline',
        'phone_api': phone_status,
        'name_api': name_status,
        'hostname': hostname,
        'diagnostics_cached': bool(diagnostics.get('cached')),
    }


def request_relay_status_endpoint(endpoint, timeout_seconds, token=None, method='GET'):
    headers = {'Accept': 'application/json', 'User-Agent': 'PeopleGraph-Relay-Monitor/1.0'}
    if token:
        headers['Authorization'] = f'Bearer {token}'
    request = Request(
        endpoint,
        data=b'' if method == 'POST' else None,
        headers=headers,
        method=method,
    )
    try:
        with urlopen(request, timeout=min(timeout_seconds, 20)) as response:
            body = response.read(65537)
    except HTTPError as exc:
        exc.read(65536)
        raise UpstreamLookupError('Relay status endpoint rejected the request.') from exc
    except (URLError, OSError, HttpClientException) as exc:
        raise UpstreamLookupError('Relay status endpoint is unavailable.') from exc
    if len(body) > 65536:
        raise UpstreamLookupError('Relay status endpoint returned too much data.')
    try:
        payload = json.loads(body.decode('utf-8'))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise UpstreamLookupError('Relay status endpoint returned invalid data.') from exc
    if not isinstance(payload, dict):
        raise UpstreamLookupError('Relay status endpoint returned invalid data.')
    return payload


def relay_probe_status(check):
    if not isinstance(check, dict):
        return 'unknown'
    status_value = check.get('status')
    return status_value if status_value in {'ok', 'error', 'not_configured'} else 'unknown'


def request_secondary_relay(
    endpoint: str,
    request_payload: dict[str, str],
    configuration: RelayConfiguration,
    lookup_type: str,
) -> dict[str, Any]:
    request = Request(
        endpoint,
        data=json.dumps(request_payload, separators=(',', ':')).encode('utf-8'),
        headers={
            'Accept': 'application/json',
            'Authorization': f'Bearer {configuration.api_token}',
            'Content-Type': 'application/json',
            'User-Agent': 'PeopleGraph-Secondary-Relay/1.0',
        },
        method='POST',
    )
    try:
        with urlopen(request, timeout=configuration.timeout_seconds) as response:
            body = response.read(settings.SECONDARY_RELAY_MAX_RESPONSE_BYTES + 1)
    except HTTPError as exc:
        exc.read(settings.SECONDARY_RELAY_MAX_RESPONSE_BYTES)
        logger.warning('Secondary relay rejected lookup_type=%s status=%s', lookup_type, exc.code)
        raise UpstreamLookupError(f'Secondary relay returned {exc.code}.') from exc
    except (URLError, OSError, HttpClientException) as exc:
        raise UpstreamLookupError('Secondary lookup relay is unavailable.') from exc

    if len(body) > settings.SECONDARY_RELAY_MAX_RESPONSE_BYTES:
        raise UpstreamLookupError('Secondary lookup relay returned too much data.')

    try:
        payload = json.loads(body.decode('utf-8'))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise UpstreamLookupError('Secondary lookup relay returned invalid JSON.') from exc
    return normalize_relay_response(payload, lookup_type)


def normalize_relay_response(payload: Any, lookup_type: str) -> dict[str, Any]:
    if not isinstance(payload, dict):
        raise UpstreamLookupError('Secondary lookup relay returned invalid data.')
    relay_status = payload.get('status')
    records = payload.get('persons')
    if relay_status not in {'success', 'not_found'} or not isinstance(records, list):
        raise UpstreamLookupError('Secondary lookup relay returned invalid data.')

    persons = []
    for index, record in enumerate(records[:100]):
        if not isinstance(record, dict):
            continue
        name = relay_text(record.get('name'), 255) or 'Unknown person'
        zipcode = relay_text(record.get('zipcode'), 10)
        raw_age = record.get('age')
        if isinstance(raw_age, int) and not isinstance(raw_age, bool):
            age = raw_age
        elif isinstance(raw_age, str):
            age = raw_age.strip()[:16]
        else:
            age = None
        persons.append(
            {
                'id': relay_text(record.get('id'), 255)
                or f'secondary-{lookup_type}-{index}-{normalize_text(name)}-{zipcode}',
                'name': name,
                'age': age,
                'zipcode': zipcode,
                'state': relay_text(record.get('state'), 2).upper(),
                'email': relay_text(record.get('email'), 320),
                'is_secondary': True,
            }
        )

    count = len(persons)
    return {
        'status': 'success' if count else 'not_found',
        'message': f'Found {count} result(s)' if count else 'No records found.',
        'data': {
            'persons': persons,
            'pagination': {
                'currentPageNumber': 1,
                'resultsPerPage': count,
                'totalPages': 1 if count else 0,
                'totalResults': count,
            },
        },
    }


def relay_text(value: Any, max_length: int) -> str:
    return value.strip()[:max_length] if isinstance(value, str) else ''


def lookup_blacklist(phone_digits: str, normalized_phone: str, display_phone: str) -> dict[str, Any]:
    cached = BlacklistLookupCache.objects.filter(normalized_phone=normalized_phone).first()

    if cached:
        return build_blacklist_response(cached, source='cache')

    try:
        upstream_response = fetch_blacklist_lookup(phone_digits)
    except UpstreamLookupError as exc:
        return {
            'status': 'error',
            'message': 'TCPA blacklist check is temporarily unavailable.',
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
        exc.read()
        raise UpstreamLookupError(f'TCPA provider returned {exc.code}.') from exc
    except (URLError, TimeoutError) as exc:
        raise UpstreamLookupError('TCPA provider is unavailable. Please try again.') from exc
    except json.JSONDecodeError as exc:
        raise UpstreamLookupError('TCPA provider returned an invalid response.') from exc


@transaction.atomic
def persist_phone_lookup(
    normalized_phone: str,
    display_phone: str,
    response: dict[str, Any],
    provider: str = PhoneLookupCache.PROVIDER_PRIMARY,
    secondary_attempted: bool = False,
) -> PhoneLookupCache:
    persons = response.get('data', {}).get('persons', [])
    cache, _ = PhoneLookupCache.objects.update_or_create(
        normalized_phone=normalized_phone,
        defaults={
            'display_phone': display_phone,
            'provider': provider,
            'secondary_attempted': secondary_attempted,
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


@transaction.atomic
def persist_name_address_lookup(
    normalized: dict[str, str],
    response: dict[str, Any],
    provider: str = NameAddrLookupCache.PROVIDER_PRIMARY,
    secondary_attempted: bool = False,
) -> NameAddrLookupCache:
    persons = response.get('data', {}).get('persons', [])
    cache, _ = NameAddrLookupCache.objects.update_or_create(
        first_name_normalized=normalized['first_name_normalized'],
        last_name_normalized=normalized['last_name_normalized'],
        location_normalized=normalized['location_normalized'],
        defaults={
            'address': normalized['address'],
            'zipcode': normalized['zipcode'],
            'full_name': normalized['full_name'],
            'provider': provider,
            'secondary_attempted': secondary_attempted,
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
        'provider': cache.provider,
        'query': {
            'phone_number': cache.display_phone,
            'normalized_phone': cache.normalized_phone,
        },
        'data': {
            'persons': [serialize_cached_person(person, cache.provider) for person in persons],
            'pagination': pagination,
            'result_count': cache.result_count,
        },
    }


def build_name_address_response(cache: NameAddrLookupCache, source: str) -> dict[str, Any]:
    raw_response = cache.raw_response or {}
    persons = raw_response.get('data', {}).get('persons', [])
    pagination = raw_response.get('data', {}).get('pagination', {})

    return {
        'status': cache.status,
        'message': cache.message,
        'source': source,
        'provider': cache.provider,
        'query': {
            'full_name': cache.full_name,
            'first_name': cache.first_name_normalized,
            'last_name': cache.last_name_normalized,
            'address': cache.address,
            'zipcode': cache.zipcode,
            'location_key': cache.location_normalized,
        },
        'data': {
            'persons': [serialize_cached_person(person, cache.provider) for person in persons],
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


def serialize_cached_person(person: dict[str, Any], provider: str) -> dict[str, Any]:
    if provider == PhoneLookupCache.PROVIDER_SECONDARY:
        return {
            'id': str(person.get('id') or person.get('name') or 'secondary-result'),
            'name': str(person.get('name') or 'Unknown person'),
            'age': person.get('age'),
            'zipcode': str(person.get('zipcode') or ''),
            'state': str(person.get('state') or ''),
            'email': str(person.get('email') or ''),
            'is_secondary': True,
        }
    return serialize_person(person)


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
