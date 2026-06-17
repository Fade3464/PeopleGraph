from rest_framework.response import Response
from rest_framework import status
from rest_framework.views import APIView

from .models import PhoneLookupAudit
from .services import InvalidPhoneError, UpstreamLookupError, lookup_phone


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

    def post(self, request):
        phone_number = request.data.get('phone_number', '')

        try:
            result = lookup_phone(phone_number)
        except InvalidPhoneError as exc:
            return Response(
                {'status': 'error', 'message': str(exc), 'data': {'persons': []}},
                status=status.HTTP_400_BAD_REQUEST,
            )
        except UpstreamLookupError as exc:
            return Response(
                {'status': 'error', 'message': str(exc), 'data': {'persons': []}},
                status=status.HTTP_502_BAD_GATEWAY,
            )

        PhoneLookupAudit.objects.create(
            phone_number=result.get('query', {}).get('phone_number', phone_number),
            normalized_phone=result.get('query', {}).get('normalized_phone', ''),
            fetched_from_dbcache=result.get('source') == 'cache',
            fetched_from_bla_cache=result.get('blacklist', {}).get('source') == 'cache',
            public_ip=get_public_ip(request),
        )

        return Response(result)


def get_public_ip(request):
    forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR', '')
    if forwarded_for:
        return forwarded_for.split(',')[0].strip() or None

    real_ip = request.META.get('HTTP_X_REAL_IP')
    if real_ip:
        return real_ip.strip()

    return request.META.get('REMOTE_ADDR')
