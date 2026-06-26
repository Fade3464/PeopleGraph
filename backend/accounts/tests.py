import json
from datetime import timedelta
from zoneinfo import ZoneInfo

from django.contrib.auth import get_user_model
from django.test import Client, TestCase
from django.utils import timezone

from .models import Feedback
from lookups.models import PhoneLookupAudit, PhoneLookupCache


class FeedbackTests(TestCase):
    def test_public_feedback_submission_creates_unread_feedback(self):
        response = self.client.post(
            '/api/v1/auth/feedback/',
            data=json.dumps(
                {
                    'name': 'Test User',
                    'email': 'tester@example.com',
                    'experience': 'Good',
                    'areas': ['Results layout', 'Speed'],
                    'feature': 'Phone search results',
                    'device': 'Desktop',
                    'details': 'The results were useful but the spacing could be improved.',
                    'suggestion': 'Make the important fields easier to scan.',
                    'page_url': 'https://peoplegraph.co/feedback',
                }
            ),
            content_type='application/json',
            REMOTE_ADDR='198.51.100.40',
        )

        self.assertEqual(response.status_code, 201)
        self.assertEqual(Feedback.objects.count(), 1)
        feedback = Feedback.objects.first()
        self.assertFalse(feedback.is_read)
        self.assertEqual(feedback.email, 'tester@example.com')
        self.assertEqual(feedback.public_ip, '198.51.100.40')

    def test_feedback_submission_rejects_missing_details(self):
        response = self.client.post(
            '/api/v1/auth/feedback/',
            data=json.dumps({'experience': 'Good', 'areas': ['Speed'], 'details': ''}),
            content_type='application/json',
        )

        self.assertEqual(response.status_code, 400)
        self.assertEqual(Feedback.objects.count(), 0)

    def test_staff_can_list_and_mark_feedback_as_read(self):
        User = get_user_model()
        user = User.objects.create_user(
            username='admin@example.com',
            email='admin@example.com',
            password='password',
            is_staff=True,
        )
        feedback = Feedback.objects.create(
            experience='Average',
            areas=['Visual design'],
            details='The interface needs a clearer empty state.',
            device='Mobile',
        )
        client = Client()
        client.force_login(user)

        list_response = client.get('/api/v1/auth/feedbacks/')
        self.assertEqual(list_response.status_code, 200)
        self.assertEqual(list_response.json()['unread_count'], 1)

        read_response = client.post(f'/api/v1/auth/feedbacks/{feedback.id}/read/')
        self.assertEqual(read_response.status_code, 200)
        self.assertEqual(read_response.json()['unread_count'], 0)
        feedback.refresh_from_db()
        self.assertTrue(feedback.is_read)
        self.assertIsNotNone(feedback.read_at)

    def test_non_staff_cannot_list_feedback(self):
        User = get_user_model()
        user = User.objects.create_user(username='user@example.com', password='password')
        client = Client()
        client.force_login(user)

        response = client.get('/api/v1/auth/feedbacks/')

        self.assertEqual(response.status_code, 403)


class ExportLookupResultsTests(TestCase):
    def test_staff_can_export_cached_lookup_results_from_audit_range(self):
        User = get_user_model()
        user = User.objects.create_user(
            username='admin@example.com',
            email='admin@example.com',
            password='password',
            is_staff=True,
        )
        PhoneLookupCache.objects.create(
            normalized_phone='+17814013217',
            display_phone='(781) 401-3217',
            status='success',
            message='Found 2 result(s)',
            result_count=2,
            raw_response={
                'data': {
                    'persons': [
                        {
                            'first_name': 'Frances',
                            'middle_name': 'J',
                            'last_name': 'Block',
                            'age': 88,
                            'phones': [{'phone_number': '(781) 401-3217'}],
                        },
                        {
                            'first_name': 'Jamie',
                            'middle_name': 'F',
                            'last_name': 'Cook',
                            'age': 35,
                            'phones': [{'phone_number': '(781) 294-4711'}],
                        },
                    ]
                },
            },
        )
        PhoneLookupAudit.objects.create(
            phone_number='(781) 401-3217',
            normalized_phone='+17814013217',
            public_ip='198.51.100.40',
        )
        client = Client()
        client.force_login(user)
        now_ny = timezone.now().astimezone(ZoneInfo('America/New_York'))
        from_string = (now_ny - timedelta(hours=1)).strftime('%Y-%m-%dT%H:%M')
        to_string = (now_ny + timedelta(hours=1)).strftime('%Y-%m-%dT%H:%M')

        response = client.get(
            '/api/v1/auth/exports/lookup-results/',
            {'from': from_string, 'to': to_string},
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response['Content-Type'], 'text/csv')
        body = response.content.decode('utf-8')
        self.assertIn('Frances J Block', body)
        self.assertIn('88', body)
        self.assertIn('(781) 401-3217', body)
        self.assertIn('Jamie F Cook', body)
        self.assertIn('35', body)
        self.assertIn('(781) 294-4711', body)

    def test_non_staff_cannot_export_lookup_results(self):
        User = get_user_model()
        user = User.objects.create_user(username='user@example.com', password='password')
        client = Client()
        client.force_login(user)

        response = client.get('/api/v1/auth/exports/lookup-results/')

        self.assertEqual(response.status_code, 403)
