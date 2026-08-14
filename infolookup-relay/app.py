import asyncio
import hmac
import json
import logging
import os
import re
import subprocess
import tempfile
import time
import uuid
from collections import deque
from pathlib import Path
from typing import Any

from fastapi import Depends, FastAPI, Header, HTTPException, Request, status
from pydantic import BaseModel, ConfigDict, Field, field_validator


logging.basicConfig(
    level=os.environ.get('LOG_LEVEL', 'INFO').upper(),
    format='%(asctime)s %(levelname)s %(name)s %(message)s',
)
logger = logging.getLogger('infolookup-relay')

BASE_URL = os.environ.get('INFOLOOKUP_BASE_URL', 'https://infolookup.site').rstrip('/')
TOKEN_URL = os.environ.get('INFOLOOKUP_TOKEN_URL', f'{BASE_URL}/lookup-token.php')
LOOKUP_URL = os.environ.get('INFOLOOKUP_PHONE_LOOKUP_URL', f'{BASE_URL}/api/lookup')
NAME_LOOKUP_URL = os.environ.get('INFOLOOKUP_NAME_LOOKUP_URL', f'{BASE_URL}/api/name/')
NAME_LOOKUP_REFERER = os.environ.get('INFOLOOKUP_NAME_LOOKUP_REFERER', f'{BASE_URL}/name-search')
RELAY_API_TOKEN = os.environ.get('RELAY_API_TOKEN', '')
DIAGNOSTIC_PHONE_NUMBER = re.sub(r'\D+', '', os.environ.get('DIAGNOSTIC_PHONE_NUMBER', ''))
DIAGNOSTIC_FIRST_NAME = os.environ.get('DIAGNOSTIC_FIRST_NAME', '').strip()
DIAGNOSTIC_LAST_NAME = os.environ.get('DIAGNOSTIC_LAST_NAME', '').strip()
DIAGNOSTIC_STATE = os.environ.get('DIAGNOSTIC_STATE', '').strip().upper()
DIAGNOSTIC_CACHE_SECONDS = max(10, int(os.environ.get('DIAGNOSTIC_CACHE_SECONDS', '60')))
UPSTREAM_TIMEOUT_SECONDS = max(3.0, float(os.environ.get('UPSTREAM_TIMEOUT_SECONDS', '15')))
MAX_CONCURRENT_LOOKUPS = max(1, int(os.environ.get('MAX_CONCURRENT_LOOKUPS', '4')))
RATE_LIMIT_PER_MINUTE = max(1, int(os.environ.get('RATE_LIMIT_PER_MINUTE', '30')))
MAX_UPSTREAM_BYTES = max(1024, int(os.environ.get('MAX_UPSTREAM_BYTES', '2097152')))
NAME_PATTERN = re.compile(r"^[A-Za-z][A-Za-z .'-]*$")
US_STATE_CODES = {
    'AL', 'AK', 'AZ', 'AR', 'CA', 'CO', 'CT', 'DE', 'FL', 'GA', 'HI', 'ID', 'IL', 'IN',
    'IA', 'KS', 'KY', 'LA', 'ME', 'MD', 'MA', 'MI', 'MN', 'MS', 'MO', 'MT', 'NE', 'NV',
    'NH', 'NJ', 'NM', 'NY', 'NC', 'ND', 'OH', 'OK', 'OR', 'PA', 'RI', 'SC', 'SD', 'TN',
    'TX', 'UT', 'VT', 'VA', 'WA', 'WV', 'WI', 'WY', 'DC',
}

if not RELAY_API_TOKEN or RELAY_API_TOKEN.startswith('replace-with-') or len(RELAY_API_TOKEN) < 32:
    raise RuntimeError('RELAY_API_TOKEN must be configured with at least 32 characters.')

lookup_slots = asyncio.Semaphore(MAX_CONCURRENT_LOOKUPS)
rate_limit_lock = asyncio.Lock()
recent_requests: deque[float] = deque()
diagnostic_lock = asyncio.Lock()
diagnostic_cached_at = 0.0
diagnostic_cached_response: dict[str, Any] | None = None

app = FastAPI(
    title='InfoLookup Relay',
    version='1.0.0',
    docs_url=None,
    redoc_url=None,
    openapi_url=None,
)


class PhoneLookupRequest(BaseModel):
    model_config = ConfigDict(extra='forbid', str_strip_whitespace=True)

    phone_number: str = Field(min_length=10, max_length=32)

    @field_validator('phone_number')
    @classmethod
    def validate_phone_number(cls, value: str) -> str:
        digits = re.sub(r'\D+', '', value)
        if len(digits) == 11 and digits.startswith('1'):
            digits = digits[1:]
        if len(digits) != 10:
            raise ValueError('Enter a valid 10 digit US phone number.')
        return digits


class CompactPerson(BaseModel):
    id: str
    name: str
    age: int | str | None = None
    zipcode: str = ''
    state: str = ''
    email: str = ''
    is_secondary: bool = True


class NameLookupRequest(BaseModel):
    model_config = ConfigDict(extra='forbid', str_strip_whitespace=True)

    first_name: str = Field(min_length=1, max_length=80)
    last_name: str = Field(min_length=1, max_length=160)
    state: str = Field(min_length=2, max_length=2)

    @field_validator('first_name', 'last_name')
    @classmethod
    def validate_name(cls, value: str) -> str:
        cleaned = re.sub(r'\s+', ' ', value).strip()
        if not NAME_PATTERN.fullmatch(cleaned):
            raise ValueError('Name contains invalid characters.')
        return cleaned

    @field_validator('state')
    @classmethod
    def validate_state(cls, value: str) -> str:
        code = value.upper()
        if code not in US_STATE_CODES:
            raise ValueError('Enter a valid two-letter US state code.')
        return code


class LookupResponse(BaseModel):
    status: str
    message: str
    result_count: int
    persons: list[CompactPerson]


@app.middleware('http')
async def request_guard(request: Request, call_next):
    if request.headers.get('content-length'):
        try:
            if int(request.headers['content-length']) > 4096:
                return json_response(413, 'Request body is too large.')
        except ValueError:
            return json_response(400, 'Invalid Content-Length header.')

    request_id = request.headers.get('cf-ray') or uuid.uuid4().hex[:16]
    started = time.monotonic()
    response = await call_next(request)
    response.headers['X-Request-ID'] = request_id
    response.headers['Cache-Control'] = 'no-store'
    response.headers['X-Content-Type-Options'] = 'nosniff'
    logger.info(
        'request_id=%s method=%s path=%s status=%s duration_ms=%d',
        request_id,
        request.method,
        request.url.path,
        response.status_code,
        int((time.monotonic() - started) * 1000),
    )
    return response


def json_response(status_code: int, message: str):
    from fastapi.responses import JSONResponse

    return JSONResponse(status_code=status_code, content={'status': 'error', 'message': message})


async def authenticate(authorization: str | None = Header(default=None)) -> None:
    scheme, _, supplied_token = (authorization or '').partition(' ')
    if scheme.lower() != 'bearer' or not hmac.compare_digest(supplied_token, RELAY_API_TOKEN):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail='Authentication required.',
            headers={'WWW-Authenticate': 'Bearer'},
        )


async def enforce_rate_limit() -> None:
    now = time.monotonic()
    cutoff = now - 60
    async with rate_limit_lock:
        while recent_requests and recent_requests[0] <= cutoff:
            recent_requests.popleft()
        if len(recent_requests) >= RATE_LIMIT_PER_MINUTE:
            raise HTTPException(status_code=429, detail='Relay rate limit exceeded.')
        recent_requests.append(now)


@app.get('/health')
async def health():
    return {'status': 'ok', 'service': 'infolookup-relay'}


@app.post('/v1/diagnostics/upstream', dependencies=[Depends(authenticate)])
async def upstream_diagnostics():
    global diagnostic_cached_at, diagnostic_cached_response

    async with diagnostic_lock:
        now = time.monotonic()
        if diagnostic_cached_response and now - diagnostic_cached_at < DIAGNOSTIC_CACHE_SECONDS:
            return {**diagnostic_cached_response, 'cached': True}

        checks = {
            'phone': await run_phone_diagnostic(),
            'name': await run_name_diagnostic(),
        }
        statuses = {check['status'] for check in checks.values()}
        overall_status = 'ok' if statuses == {'ok'} else 'degraded'
        diagnostic_cached_response = {
            'status': overall_status,
            'checks': checks,
            'cached': False,
        }
        diagnostic_cached_at = now
        return diagnostic_cached_response


async def run_phone_diagnostic():
    if len(DIAGNOSTIC_PHONE_NUMBER) != 10:
        return {'status': 'not_configured'}
    try:
        payload = await asyncio.to_thread(fetch_infolookup_phone, DIAGNOSTIC_PHONE_NUMBER)
        return {'status': 'ok', 'provider_status': str(payload.get('status') or 'unknown')[:32]}
    except RelayUpstreamError as exc:
        logger.warning('diagnostic_error lookup=phone code=%s', exc.code)
        return {'status': 'error', 'code': exc.code}


async def run_name_diagnostic():
    if (
        not DIAGNOSTIC_FIRST_NAME
        or not DIAGNOSTIC_LAST_NAME
        or DIAGNOSTIC_STATE not in US_STATE_CODES
    ):
        return {'status': 'not_configured'}
    try:
        payload = await asyncio.to_thread(
            fetch_infolookup_name,
            DIAGNOSTIC_FIRST_NAME,
            DIAGNOSTIC_LAST_NAME,
            DIAGNOSTIC_STATE,
        )
        return {'status': 'ok', 'provider_status': str(payload.get('status') or 'unknown')[:32]}
    except RelayUpstreamError as exc:
        logger.warning('diagnostic_error lookup=name code=%s', exc.code)
        return {'status': 'error', 'code': exc.code}


@app.post(
    '/v1/lookups/phone',
    response_model=LookupResponse,
    dependencies=[Depends(authenticate), Depends(enforce_rate_limit)],
)
async def phone_lookup(payload: PhoneLookupRequest):
    async with lookup_slots:
        try:
            upstream = await asyncio.to_thread(fetch_infolookup_phone, payload.phone_number)
        except RelayUpstreamError as exc:
            logger.warning('upstream_error code=%s', exc.code)
            raise HTTPException(status_code=502, detail=exc.public_message) from exc

    persons = compact_people(upstream.get('person'))
    if not persons:
        return LookupResponse(
            status='not_found',
            message='No records found.',
            result_count=0,
            persons=[],
        )
    return LookupResponse(
        status='success',
        message=f'Found {len(persons)} result(s)',
        result_count=len(persons),
        persons=persons,
    )


@app.post(
    '/v1/lookups/name',
    response_model=LookupResponse,
    dependencies=[Depends(authenticate), Depends(enforce_rate_limit)],
)
async def name_lookup(payload: NameLookupRequest):
    async with lookup_slots:
        try:
            upstream = await asyncio.to_thread(
                fetch_infolookup_name,
                payload.first_name,
                payload.last_name,
                payload.state,
            )
        except RelayUpstreamError as exc:
            logger.warning('upstream_error lookup=name code=%s', exc.code)
            raise HTTPException(status_code=502, detail=exc.public_message) from exc

    persons = compact_name_people(upstream.get('results'))
    if not persons:
        return LookupResponse(
            status='not_found',
            message='No records found.',
            result_count=0,
            persons=[],
        )
    return LookupResponse(
        status='success',
        message=f'Found {len(persons)} result(s)',
        result_count=len(persons),
        persons=persons,
    )


class RelayUpstreamError(Exception):
    def __init__(self, code: str, public_message: str):
        super().__init__(code)
        self.code = code
        self.public_message = public_message


def fetch_infolookup_phone(phone_digits: str) -> dict[str, Any]:
    with tempfile.TemporaryDirectory(prefix='infolookup-relay-') as temp_dir:
        cookie_jar = str(Path(temp_dir) / 'cookies.txt')
        token_payload = run_curl_json(
            [
                '-c', cookie_jar,
                '-b', cookie_jar,
                '-H', f'Referer: {BASE_URL}/',
                '--', TOKEN_URL,
            ],
            stage='token',
        )
        token = str(token_payload.get('token') or '').strip()
        expires = token_payload.get('expires')
        if token_payload.get('status') != 'ok' or not token:
            raise RelayUpstreamError('token_missing', 'Lookup provider did not issue a token.')
        if expires is not None:
            try:
                if int(expires) <= int(time.time()):
                    raise RelayUpstreamError('token_expired', 'Lookup provider issued an expired token.')
            except (TypeError, ValueError) as exc:
                raise RelayUpstreamError('token_expiry_invalid', 'Lookup provider returned an invalid token.') from exc

        lookup_payload = run_curl_json(
            [
                '-b', cookie_jar,
                '-H', 'Accept: application/json',
                '-H', f'Referer: {BASE_URL}/',
                '-G', LOOKUP_URL,
                '--data-urlencode', f'x={phone_digits}',
                '--data-urlencode', f'_t={token}',
            ],
            stage='lookup',
        )

    if lookup_payload.get('status') == 'ok':
        return lookup_payload
    provider_code = str(lookup_payload.get('code') or 'provider_error')[:64]
    if provider_code == 'need_turnstile':
        raise RelayUpstreamError('need_turnstile', 'Lookup provider requires interactive verification.')
    if lookup_payload.get('isNotFound') is True or lookup_payload.get('count') == 0:
        return {'status': 'ok', 'person': []}
    raise RelayUpstreamError(provider_code, 'Lookup provider rejected the request.')


def fetch_infolookup_name(first_name: str, last_name: str, state_code: str) -> dict[str, Any]:
    payload = run_curl_json(
        [
            '-H', 'Accept: application/json',
            '-H', f'Referer: {NAME_LOOKUP_REFERER}',
            '-G', NAME_LOOKUP_URL,
            '--data-urlencode', f'firstName={first_name}',
            '--data-urlencode', f'lastName={last_name}',
            '--data-urlencode', f'state={state_code}',
        ],
        stage='name_lookup',
    )
    if payload.get('status') == 'ok':
        return payload
    provider_code = str(payload.get('code') or 'provider_error')[:64]
    if provider_code == 'need_turnstile':
        raise RelayUpstreamError('need_turnstile', 'Lookup provider requires interactive verification.')
    if payload.get('count') == 0:
        return {'status': 'ok', 'results': []}
    raise RelayUpstreamError(provider_code, 'Lookup provider rejected the request.')


def run_curl_json(arguments: list[str], stage: str) -> dict[str, Any]:
    command = [
        'curl',
        '-sS',
        '--fail-with-body',
        '--proto', '=https',
        '--connect-timeout', str(min(5.0, UPSTREAM_TIMEOUT_SECONDS)),
        '--max-time', str(UPSTREAM_TIMEOUT_SECONDS),
        '--max-filesize', str(MAX_UPSTREAM_BYTES),
        *arguments,
    ]
    try:
        completed = subprocess.run(
            command,
            capture_output=True,
            text=True,
            timeout=UPSTREAM_TIMEOUT_SECONDS + 2,
            check=False,
        )
    except FileNotFoundError as exc:
        raise RelayUpstreamError('curl_missing', 'Lookup client is unavailable.') from exc
    except subprocess.TimeoutExpired as exc:
        raise RelayUpstreamError(f'{stage}_timeout', 'Lookup provider timed out.') from exc

    if completed.returncode != 0:
        logger.warning('curl_failure stage=%s exit_code=%s', stage, completed.returncode)
        raise RelayUpstreamError(f'{stage}_http_failure', 'Lookup provider is unavailable.')
    if len(completed.stdout.encode('utf-8')) > MAX_UPSTREAM_BYTES:
        raise RelayUpstreamError(f'{stage}_response_too_large', 'Lookup provider response was too large.')
    try:
        payload = json.loads(completed.stdout)
    except json.JSONDecodeError as exc:
        raise RelayUpstreamError(f'{stage}_invalid_json', 'Lookup provider returned invalid data.') from exc
    if not isinstance(payload, dict):
        raise RelayUpstreamError(f'{stage}_invalid_shape', 'Lookup provider returned invalid data.')
    return payload


def compact_people(records: Any) -> list[CompactPerson]:
    if not isinstance(records, list):
        return []

    persons: list[CompactPerson] = []
    for index, record in enumerate(records[:100]):
        if not isinstance(record, dict):
            continue
        addresses = record.get('addresses') if isinstance(record.get('addresses'), list) else []
        primary_address = addresses[0] if addresses and isinstance(addresses[0], dict) else {}
        emails = record.get('emails') if isinstance(record.get('emails'), list) else []
        email = next((str(item) for item in emails if isinstance(item, str) and item), '')
        name = str(record.get('name') or 'Unknown person').strip()[:255]
        raw_age = record.get('age')
        age = raw_age if isinstance(raw_age, (int, str)) and not isinstance(raw_age, bool) else None
        persons.append(
            CompactPerson(
                id=f'relay-phone-{index}-{slug(name)}-{str(primary_address.get("zip") or "")[:10]}',
                name=name,
                age=age,
                zipcode=str(primary_address.get('zip') or '')[:10],
                state=str(primary_address.get('state') or '')[:2].upper(),
                email=email[:320],
            )
        )
    return persons


def compact_name_people(records: Any) -> list[CompactPerson]:
    if not isinstance(records, list):
        return []

    persons: list[CompactPerson] = []
    for index, record in enumerate(records[:100]):
        if not isinstance(record, dict):
            continue
        address = record.get('addressParts') if isinstance(record.get('addressParts'), dict) else {}
        email = record.get('email') if isinstance(record.get('email'), str) else ''
        if not email:
            emails = record.get('emails') if isinstance(record.get('emails'), list) else []
            email = next((str(item) for item in emails if isinstance(item, str) and item), '')
        name = str(record.get('name') or 'Unknown person').strip()[:255]
        raw_age = record.get('age')
        age = raw_age if isinstance(raw_age, (int, str)) and not isinstance(raw_age, bool) else None
        zipcode = str(address.get('zip') or '')[:10]
        persons.append(
            CompactPerson(
                id=f'relay-name-{index}-{slug(name)}-{zipcode}',
                name=name,
                age=age,
                zipcode=zipcode,
                state=str(address.get('state') or '')[:2].upper(),
                email=email[:320],
            )
        )
    return persons


def slug(value: str) -> str:
    return re.sub(r'[^a-z0-9]+', '-', value.lower()).strip('-')[:80] or 'unknown'
