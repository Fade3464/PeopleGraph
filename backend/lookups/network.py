import ipaddress

from django.conf import settings


def get_client_ip(request):
    candidates = []
    if settings.TRUST_X_FORWARDED_FOR:
        forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR', '')
        if forwarded_for:
            # Nginx appends the directly connected client at the right. Reading from
            # the right prevents a caller-supplied prefix from spoofing the address.
            candidates.extend(reversed([item.strip() for item in forwarded_for.split(',')]))
        candidates.append(request.META.get('HTTP_X_REAL_IP', '').strip())
    candidates.append(request.META.get('REMOTE_ADDR', '').strip())

    for candidate in candidates:
        if not candidate:
            continue
        try:
            return str(ipaddress.ip_address(candidate))
        except ValueError:
            continue
    return None
