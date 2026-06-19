from django.conf import settings
from rest_framework.response import Response
from rest_framework import status
from rest_framework.views import APIView

from .models import PhoneLookupAudit
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
        public_ip = get_public_ip(request)

        try:
            validate_turnstile_token(turnstile_token, public_ip)
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
        public_ip = get_public_ip(request)

        try:
            validate_turnstile_token(turnstile_token, public_ip)
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

        return Response(result)


def get_public_ip(request):
    if settings.TRUST_X_FORWARDED_FOR:
        forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR', '')
        if forwarded_for:
            return forwarded_for.split(',')[0].strip() or None

    real_ip = request.META.get('HTTP_X_REAL_IP')
    if settings.TRUST_X_FORWARDED_FOR and real_ip:
        return real_ip.strip()

    return request.META.get('REMOTE_ADDR')


def safe_public_error(exc):
    if settings.DEBUG:
        return str(exc)

    return 'Lookup service is temporarily unavailable. Please try again.'
