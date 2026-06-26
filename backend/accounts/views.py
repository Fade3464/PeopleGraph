import json
from collections import OrderedDict
from datetime import datetime, timedelta, timezone as datetime_timezone
from zoneinfo import ZoneInfo

from django.contrib.auth import authenticate, login, logout
from django.db.models import Count
from django.http import JsonResponse
from django.middleware.csrf import get_token
from django.utils import timezone
from django.views.decorators.cache import never_cache
from django.views.decorators.csrf import csrf_protect, ensure_csrf_cookie
from django.views.decorators.http import require_GET, require_POST

from lookups.models import PhoneLookupAudit


NEW_YORK_TIMEZONE = ZoneInfo('America/New_York')
MAX_DASHBOARD_RANGE_DAYS = 31


@require_GET
@ensure_csrf_cookie
@never_cache
def csrf_token(request):
    return JsonResponse({'status': 'ok', 'csrfToken': get_token(request)})


@require_GET
@never_cache
def me_view(request):
    user = request.user
    if not user.is_authenticated:
        return JsonResponse({'authenticated': False})

    return JsonResponse(
        {
            'authenticated': True,
            'user': {
                'id': user.id,
                'username': user.get_username(),
                'email': user.email,
                'is_staff': user.is_staff,
                'is_superuser': user.is_superuser,
            },
        }
    )


@require_POST
@csrf_protect
@never_cache
def login_view(request):
    try:
        payload = json.loads(request.body.decode('utf-8') or '{}')
    except json.JSONDecodeError:
        return JsonResponse({'status': 'error', 'message': 'Invalid login payload.'}, status=400)

    username = str(payload.get('username', '')).strip()
    password = str(payload.get('password', ''))

    if not username or not password:
        return JsonResponse({'status': 'error', 'message': 'Enter username and password.'}, status=400)

    user = authenticate(request, username=username, password=password)
    if user is None:
        return JsonResponse({'status': 'error', 'message': 'Invalid username or password.'}, status=401)

    if not user.is_active:
        return JsonResponse({'status': 'error', 'message': 'This account is inactive.'}, status=403)

    if not user.is_staff:
        return JsonResponse({'status': 'error', 'message': 'This account cannot access administration.'}, status=403)

    login(request, user)
    return JsonResponse(
        {
            'status': 'success',
            'message': 'Signed in.',
            'user': {
                'id': user.id,
                'username': user.get_username(),
                'email': user.email,
                'is_staff': user.is_staff,
                'is_superuser': user.is_superuser,
            },
        }
    )


@require_POST
@csrf_protect
@never_cache
def logout_view(request):
    logout(request)
    return JsonResponse({'status': 'success', 'message': 'Signed out.'})


@require_GET
@never_cache
def phone_lookup_dashboard(request):
    if not request.user.is_authenticated or not request.user.is_staff:
        return JsonResponse({'status': 'error', 'message': 'Administration access required.'}, status=403)

    now_ny = timezone.now().astimezone(NEW_YORK_TIMEZONE)
    default_to = now_ny.replace(second=0, microsecond=0)
    default_from = default_to - timedelta(hours=24)

    try:
        from_dt = parse_new_york_datetime(request.GET.get('from'), default_from)
        to_dt = parse_new_york_datetime(request.GET.get('to'), default_to)
    except ValueError as exc:
        return JsonResponse({'status': 'error', 'message': str(exc)}, status=400)

    if from_dt >= to_dt:
        return JsonResponse({'status': 'error', 'message': 'From must be earlier than To.'}, status=400)

    if to_dt - from_dt > timedelta(days=MAX_DASHBOARD_RANGE_DAYS):
        return JsonResponse(
            {'status': 'error', 'message': f'Date range cannot exceed {MAX_DASHBOARD_RANGE_DAYS} days.'},
            status=400,
        )

    from_utc = from_dt.astimezone(datetime_timezone.utc)
    to_utc = to_dt.astimezone(datetime_timezone.utc)
    audits = PhoneLookupAudit.objects.filter(timestamp__gte=from_utc, timestamp__lte=to_utc)

    bucket_minutes = choose_bucket_minutes(from_dt, to_dt)
    buckets = build_lookup_buckets(audits, from_dt, to_dt, bucket_minutes)

    public_ip_counts = list(
        audits.values('public_ip')
        .annotate(total_lookups=Count('id'), unique_phone_numbers=Count('normalized_phone', distinct=True))
        .order_by('-total_lookups', 'public_ip')[:20]
    )

    return JsonResponse(
        {
            'status': 'success',
            'timezone': 'America/New_York',
            'range': {
                'from': from_dt.isoformat(),
                'to': to_dt.isoformat(),
                'bucket_minutes': bucket_minutes,
            },
            'summary': {
                'total_lookups': audits.count(),
                'unique_phone_numbers': audits.values('normalized_phone').distinct().count(),
                'unique_public_ips': audits.exclude(public_ip__isnull=True).values('public_ip').distinct().count(),
            },
            'lookup_counts': buckets,
            'public_ip_counts': [
                {
                    'public_ip': row['public_ip'] or 'Unknown',
                    'total_lookups': row['total_lookups'],
                    'unique_phone_numbers': row['unique_phone_numbers'],
                }
                for row in public_ip_counts
            ],
        }
    )


def parse_new_york_datetime(value, fallback):
    if not value:
        return fallback

    normalized = value.strip()
    if normalized.endswith('Z'):
        normalized = normalized[:-1] + '+00:00'

    try:
        parsed = datetime.fromisoformat(normalized)
    except ValueError as exc:
        raise ValueError('Use a valid date and time.') from exc

    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=NEW_YORK_TIMEZONE)

    return parsed.astimezone(NEW_YORK_TIMEZONE)


def choose_bucket_minutes(from_dt, to_dt):
    total_seconds = (to_dt - from_dt).total_seconds()
    if total_seconds <= 6 * 60 * 60:
        return 30
    if total_seconds <= 48 * 60 * 60:
        return 60
    return 24 * 60


def floor_to_bucket(dt, bucket_minutes):
    if bucket_minutes >= 24 * 60:
        return dt.replace(hour=0, minute=0, second=0, microsecond=0)

    minute = (dt.minute // bucket_minutes) * bucket_minutes
    return dt.replace(minute=minute, second=0, microsecond=0)


def build_lookup_buckets(audits, from_dt, to_dt, bucket_minutes):
    start = floor_to_bucket(from_dt, bucket_minutes)
    buckets = OrderedDict()
    current = start
    step = timedelta(minutes=bucket_minutes)

    while current <= to_dt:
        label = f'{current:%b} {current.day}' if bucket_minutes >= 24 * 60 else current.strftime('%I:%M %p').lstrip('0')
        buckets[current.isoformat()] = {
            'timestamp': current.isoformat(),
            'label': label,
            'count': 0,
        }
        current += step

    for audit in audits.only('timestamp').iterator():
        local_time = audit.timestamp.astimezone(NEW_YORK_TIMEZONE)
        bucket = floor_to_bucket(local_time, bucket_minutes).isoformat()
        if bucket in buckets:
            buckets[bucket]['count'] += 1

    return list(buckets.values())
