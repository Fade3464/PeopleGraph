from rest_framework.response import Response
from rest_framework import status
from rest_framework.views import APIView

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

        return Response(result)
