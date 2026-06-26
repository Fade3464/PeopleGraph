import json
import csv
from collections import OrderedDict
from datetime import datetime, timedelta, timezone as datetime_timezone
from urllib.parse import urlparse
from zoneinfo import ZoneInfo

from django.contrib.auth import authenticate, login, logout
from django.conf import settings
from django.core.cache import cache
from django.db.models import Count
from django.core.validators import validate_email
from django.core.exceptions import ValidationError
from django.http import HttpResponse, JsonResponse
from django.middleware.csrf import get_token
from django.utils import timezone
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.cache import never_cache
from django.views.decorators.csrf import csrf_protect, ensure_csrf_cookie
from django.views.decorators.http import require_GET, require_POST

from .models import Feedback
from lookups.models import PhoneLookupAudit, PhoneLookupCache


NEW_YORK_TIMEZONE = ZoneInfo('America/New_York')
MAX_DASHBOARD_RANGE_DAYS = 31
MAX_EXPORT_RANGE_DAYS = 31
MAX_FEEDBACK_DETAILS_LENGTH = 5000
MAX_FEEDBACK_SUGGESTION_LENGTH = 3000
MAX_FEEDBACK_FIELD_LENGTH = 160
ALLOWED_EXPERIENCES = {'Excellent', 'Good', 'Average', 'Difficult'}
ALLOWED_DEVICES = {'Desktop', 'Mobile', 'Tablet'}
FEEDBACK_RATE_LIMIT = 5
FEEDBACK_RATE_LIMIT_SECONDS = 10 * 60


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


@require_GET
@never_cache
def export_lookup_results(request):
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

    if to_dt - from_dt > timedelta(days=MAX_EXPORT_RANGE_DAYS):
        return JsonResponse(
            {'status': 'error', 'message': f'Export range cannot exceed {MAX_EXPORT_RANGE_DAYS} days.'},
            status=400,
        )

    from_utc = from_dt.astimezone(datetime_timezone.utc)
    to_utc = to_dt.astimezone(datetime_timezone.utc)
    audit_rows = (
        PhoneLookupAudit.objects.filter(timestamp__gte=from_utc, timestamp__lte=to_utc)
        .values('normalized_phone', 'phone_number')
        .annotate(lookup_count=Count('id'))
        .order_by('normalized_phone')
    )
    audit_map = {
        row['normalized_phone']: {
            'phone_number': row['phone_number'],
            'lookup_count': row['lookup_count'],
        }
        for row in audit_rows
        if row['normalized_phone']
    }
    caches = PhoneLookupCache.objects.filter(normalized_phone__in=audit_map.keys()).only(
        'normalized_phone',
        'display_phone',
        'raw_response',
    )

    filename = f'peoplegraph-lookup-results-{from_dt:%Y%m%d%H%M}-{to_dt:%Y%m%d%H%M}.csv'
    response = HttpResponse(content_type='text/csv')
    response['Content-Disposition'] = f'attachment; filename="{filename}"'
    response['Cache-Control'] = 'no-store, max-age=0'
    response['Pragma'] = 'no-cache'
    response['X-Content-Type-Options'] = 'nosniff'

    writer = csv.writer(response)
    writer.writerow(
        [
            'searched_phone_number',
            'normalized_phone',
            'matched_name',
            'age',
            'primary_phone_number',
            'lookup_count_in_range',
            'range_from_new_york',
            'range_to_new_york',
        ]
    )

    for cache in caches:
        audit = audit_map.get(cache.normalized_phone, {})
        persons = (cache.raw_response or {}).get('data', {}).get('persons', [])
        if not persons:
            write_csv_row(
                writer,
                [
                    audit.get('phone_number') or cache.display_phone,
                    cache.normalized_phone,
                    '',
                    '',
                    '',
                    audit.get('lookup_count', 0),
                    from_dt.isoformat(),
                    to_dt.isoformat(),
                ]
            )
            continue

        for person in persons:
            primary_phone = get_primary_phone_number(person)
            write_csv_row(
                writer,
                [
                    audit.get('phone_number') or cache.display_phone,
                    cache.normalized_phone,
                    get_person_name(person),
                    person.get('age') or '',
                    primary_phone,
                    audit.get('lookup_count', 0),
                    from_dt.isoformat(),
                    to_dt.isoformat(),
                ]
            )

    return response


def write_csv_row(writer, row):
    writer.writerow([safe_csv_value(value) for value in row])


def safe_csv_value(value):
    if value is None:
        return ''

    text = str(value)
    if text and text[0] in {'=', '+', '-', '@', '\t', '\r', '\n'}:
        return f"'{text}"

    return text


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


def get_person_name(person):
    if person.get('name'):
        return person['name']

    parts = [person.get('first_name'), person.get('middle_name'), person.get('last_name')]
    return ' '.join(str(part).strip() for part in parts if part).strip()


def get_primary_phone_number(person):
    phones = person.get('phones') or []
    if phones and isinstance(phones, list):
        return phones[0].get('phone_number') or ''

    return person.get('phone') or person.get('phone_number') or ''


@require_POST
@csrf_exempt
@never_cache
def submit_feedback(request):
    if not request_origin_is_allowed(request):
        return JsonResponse({'status': 'error', 'message': 'Feedback origin is not allowed.'}, status=403)

    try:
        enforce_feedback_rate_limit(request)
    except ValueError as exc:
        return JsonResponse({'status': 'error', 'message': str(exc)}, status=429)

    try:
        payload = json.loads(request.body.decode('utf-8') or '{}')
    except json.JSONDecodeError:
        return JsonResponse({'status': 'error', 'message': 'Invalid feedback payload.'}, status=400)

    try:
        feedback = create_feedback_from_payload(payload, request)
    except ValueError as exc:
        return JsonResponse({'status': 'error', 'message': str(exc)}, status=400)

    return JsonResponse(
        {
            'status': 'success',
            'message': 'Feedback submitted.',
            'feedback': serialize_feedback(feedback),
        },
        status=201,
    )


@require_GET
@never_cache
def feedback_list(request):
    if not request.user.is_authenticated or not request.user.is_staff:
        return JsonResponse({'status': 'error', 'message': 'Administration access required.'}, status=403)

    feedbacks = Feedback.objects.all()[:100]
    unread_count = Feedback.objects.filter(is_read=False).count()

    return JsonResponse(
        {
            'status': 'success',
            'unread_count': unread_count,
            'feedbacks': [serialize_feedback(feedback) for feedback in feedbacks],
        }
    )


@require_POST
@csrf_protect
@never_cache
def mark_feedback_read(request, feedback_id):
    if not request.user.is_authenticated or not request.user.is_staff:
        return JsonResponse({'status': 'error', 'message': 'Administration access required.'}, status=403)

    try:
        feedback = Feedback.objects.get(id=feedback_id)
    except Feedback.DoesNotExist:
        return JsonResponse({'status': 'error', 'message': 'Feedback not found.'}, status=404)

    feedback.mark_as_read()

    return JsonResponse(
        {
            'status': 'success',
            'unread_count': Feedback.objects.filter(is_read=False).count(),
            'feedback': serialize_feedback(feedback),
        }
    )


def create_feedback_from_payload(payload, request):
    name = clean_text(payload.get('name'), 120)
    email = clean_text(payload.get('email'), 254)
    experience = clean_text(payload.get('experience'), 24)
    feature = clean_text(payload.get('feature'), MAX_FEEDBACK_FIELD_LENGTH)
    device = clean_text(payload.get('device'), 40)
    details = clean_text(payload.get('details'), MAX_FEEDBACK_DETAILS_LENGTH, preserve_newlines=True)
    suggestion = clean_text(payload.get('suggestion'), MAX_FEEDBACK_SUGGESTION_LENGTH, preserve_newlines=True)
    page_url = clean_text(payload.get('page_url'), 255)
    areas = payload.get('areas', [])

    if email:
        try:
            validate_email(email)
        except ValidationError as exc:
            raise ValueError('Enter a valid email address.') from exc

    if experience not in ALLOWED_EXPERIENCES:
        raise ValueError('Select a valid overall experience.')

    if device and device not in ALLOWED_DEVICES:
        raise ValueError('Select a valid device.')

    if not details:
        raise ValueError('Describe what happened.')

    if not isinstance(areas, list):
        raise ValueError('Select valid feedback areas.')

    cleaned_areas = []
    for area in areas[:8]:
        cleaned_area = clean_text(area, 60)
        if cleaned_area:
            cleaned_areas.append(cleaned_area)

    return Feedback.objects.create(
        name=name,
        email=email,
        experience=experience,
        areas=cleaned_areas,
        feature=feature,
        device=device,
        details=details,
        suggestion=suggestion,
        page_url=page_url,
        public_ip=get_public_ip(request),
        user_agent=clean_text(request.META.get('HTTP_USER_AGENT'), 255),
    )


def serialize_feedback(feedback):
    return {
        'id': feedback.id,
        'name': feedback.name,
        'email': feedback.email,
        'experience': feedback.experience,
        'areas': feedback.areas or [],
        'feature': feedback.feature,
        'device': feedback.device,
        'details': feedback.details,
        'suggestion': feedback.suggestion,
        'page_url': feedback.page_url,
        'public_ip': feedback.public_ip or '',
        'user_agent': feedback.user_agent,
        'is_read': feedback.is_read,
        'read_at': feedback.read_at.isoformat() if feedback.read_at else None,
        'created_at': feedback.created_at.isoformat(),
    }


def clean_text(value, max_length, preserve_newlines=False):
    raw_text = str(value or '').replace('\x00', '').strip()
    text = raw_text if preserve_newlines else ' '.join(raw_text.split())
    if len(text) > max_length:
        raise ValueError('One or more fields are too long.')
    return text


def enforce_feedback_rate_limit(request):
    public_ip = get_public_ip(request) or 'unknown'
    cache_key = f'feedback-rate:{public_ip}'

    if cache.add(cache_key, 1, FEEDBACK_RATE_LIMIT_SECONDS):
        return

    try:
        count = cache.incr(cache_key)
    except ValueError:
        cache.set(cache_key, 1, FEEDBACK_RATE_LIMIT_SECONDS)
        return

    if count > FEEDBACK_RATE_LIMIT:
        raise ValueError('Too many feedback submissions. Please try again later.')


def request_origin_is_allowed(request):
    origin = request.META.get('HTTP_ORIGIN')
    if not origin:
        return True

    allowed_origins = set(settings.CSRF_TRUSTED_ORIGINS) | set(settings.CORS_ALLOWED_ORIGINS)
    if origin in allowed_origins:
        return True

    parsed = urlparse(origin)
    return parsed.hostname in settings.ALLOWED_HOSTS


def get_public_ip(request):
    forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR', '')
    if forwarded_for:
        return forwarded_for.split(',')[0].strip() or None

    real_ip = request.META.get('HTTP_X_REAL_IP', '')
    return real_ip.strip() or request.META.get('REMOTE_ADDR')
