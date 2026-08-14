import time

from django.conf import settings
from rest_framework.response import Response
from rest_framework import status
from rest_framework.views import APIView

from .access import RegionRestrictedError, RegionVerificationError, enforce_lookup_region
from .models import NameLookupAudit, PhoneLookupAudit
from .network import get_client_ip
from .services import (
    InvalidNameAddressError,
    InvalidPhoneError,
    TurnstileValidationError,
    UpstreamLookupError,
    lookup_name_address,
    lookup_phone,
    validate_turnstile_token,
)


class HealthCheckView(APIView):
    authentication_classes = []
    permission_classes = []

    def get(self, request):
        return Response(
            {
                'status': 'ok',
                'service': 'PeopleGraph API',
            }
        )


class PhoneLookupView(APIView):
    authentication_classes = []
    permission_classes = []
    throttle_scope = 'lookup'

    def post(self, request):
        phone_number = request.data.get('phone_number', '')
        turnstile_token = request.data.get('turnstile_token', '')
        public_ip = get_client_ip(request)

        origin_error = validate_lookup_request_origin(request)
        if origin_error:
            return origin_error

        region_error = validate_lookup_region(public_ip)
        if region_error:
            return region_error

        try:
            validate_turnstile_token(turnstile_token, public_ip)
            lookup_started = time.monotonic()
            result = lookup_phone(phone_number)
        except TurnstileValidationError as exc:
            return Response(
                {'status': 'error', 'message': str(exc), 'data': {'persons': []}},
                status=status.HTTP_403_FORBIDDEN,
            )
        except InvalidPhoneError as exc:
            return Response(
                {'status': 'error', 'message': str(exc), 'data': {'persons': []}},
                status=status.HTTP_400_BAD_REQUEST,
            )
        except UpstreamLookupError as exc:
            return Response(
                {'status': 'error', 'message': safe_public_error(exc), 'data': {'persons': []}},
                status=status.HTTP_502_BAD_GATEWAY,
            )

        PhoneLookupAudit.objects.create(
            phone_number=result.get('query', {}).get('phone_number', phone_number),
            normalized_phone=result.get('query', {}).get('normalized_phone', ''),
            fetched_from_dbcache=result.get('source') == 'cache',
            fetched_from_bla_cache=result.get('blacklist', {}).get('source') == 'cache',
            source=result.get('provider', 'primary'),
            response_time_ms=max(0, round((time.monotonic() - lookup_started) * 1000)),
            successful_result=lookup_result_has_people(result),
            public_ip=public_ip,
        )

        return Response(result)


class NameAddressLookupView(APIView):
    authentication_classes = []
    permission_classes = []
    throttle_scope = 'lookup'

    def post(self, request):
        full_name = request.data.get('full_name', '')
        address_or_zip = request.data.get('address_or_zip', '')
        turnstile_token = request.data.get('turnstile_token', '')
        public_ip = get_client_ip(request)

        origin_error = validate_lookup_request_origin(request)
        if origin_error:
            return origin_error

        region_error = validate_lookup_region(public_ip)
        if region_error:
            return region_error

        try:
            validate_turnstile_token(turnstile_token, public_ip)
            lookup_started = time.monotonic()
            result = lookup_name_address(full_name, address_or_zip)
        except TurnstileValidationError as exc:
            return Response(
                {'status': 'error', 'message': str(exc), 'data': {'persons': []}},
                status=status.HTTP_403_FORBIDDEN,
            )
        except InvalidNameAddressError as exc:
            return Response(
                {'status': 'error', 'message': str(exc), 'data': {'persons': []}},
                status=status.HTTP_400_BAD_REQUEST,
            )
        except UpstreamLookupError as exc:
            return Response(
                {'status': 'error', 'message': safe_public_error(exc), 'data': {'persons': []}},
                status=status.HTTP_502_BAD_GATEWAY,
            )

        query = result.get('query', {})
        NameLookupAudit.objects.create(
            full_name=query.get('full_name', full_name),
            location=query.get('zipcode') or query.get('address') or address_or_zip,
            fetched_from_dbcache=result.get('source') == 'cache',
            source=result.get('provider', 'primary'),
            response_time_ms=max(0, round((time.monotonic() - lookup_started) * 1000)),
            successful_result=lookup_result_has_people(result),
            public_ip=public_ip,
        )

        return Response(result)


def validate_lookup_request_origin(request):
    if not settings.LOOKUP_REQUIRE_TRUSTED_ORIGIN:
        return None

    origin = request.headers.get('Origin', '').rstrip('/')
    fetch_site = request.headers.get('Sec-Fetch-Site', '').lower()
    if not origin or origin not in settings.LOOKUP_ALLOWED_ORIGINS:
        return Response(
            {'status': 'error', 'code': 'origin_not_allowed', 'message': 'Request origin is not allowed.'},
            status=status.HTTP_403_FORBIDDEN,
        )
    if fetch_site and fetch_site not in {'same-origin', 'same-site'}:
        return Response(
            {'status': 'error', 'code': 'origin_not_allowed', 'message': 'Request origin is not allowed.'},
            status=status.HTTP_403_FORBIDDEN,
        )
    return None


def lookup_result_has_people(result):
    data = result.get('data') if isinstance(result, dict) else None
    persons = data.get('persons') if isinstance(data, dict) else None
    return isinstance(persons, list) and len(persons) > 0


def validate_lookup_region(public_ip):
    try:
        enforce_lookup_region(public_ip)
    except RegionRestrictedError as exc:
        return Response(
            {'status': 'error', 'code': 'region_restricted', 'message': str(exc), 'data': {'persons': []}},
            status=status.HTTP_451_UNAVAILABLE_FOR_LEGAL_REASONS,
        )
    except RegionVerificationError:
        return Response(
            {
                'status': 'error',
                'code': 'region_verification_unavailable',
                'message': 'We could not verify your region. Please try again shortly.',
                'data': {'persons': []},
            },
            status=status.HTTP_503_SERVICE_UNAVAILABLE,
        )
    return None


def safe_public_error(exc):
    if settings.DEBUG:
        return str(exc)

    return 'Lookup service is temporarily unavailable. Please try again.'
