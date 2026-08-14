from rest_framework.throttling import ScopedRateThrottle

from .network import get_client_ip


class PublicIPScopedRateThrottle(ScopedRateThrottle):
    def get_ident(self, request):
        return get_client_ip(request) or super().get_ident(request)
