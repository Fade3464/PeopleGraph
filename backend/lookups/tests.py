from unittest.mock import patch

from rest_framework.test import APITestCase

from .models import PhoneLookupCache


SAMPLE_RESPONSE = {
    'status': 'success',
    'message': 'Found 1 result(s)',
    'data': {
        'persons': [
            {
                'id': 1746470,
                'first_name': 'Evencio',
                'middle_name': '',
                'last_name': 'Pena',
                'age': 80,
                'addresses': [
                    {
                        'full_address': '35 Brannon Harris Way; Boston, MA 02118-1372',
                        'last_reported_date': '2026-05-01',
                    }
                ],
                'phones': [
                    {
                        'phone_number': '(617) 541-2753',
                        'phone_type': 'LandLine/Services',
                        'last_reported_date': '2026-05-01',
                    }
                ],
                'emails': [],
                'relatives': [{'first_name': 'Dinke', 'last_name': 'Pena'}],
                'associates': [],
                'merged_names_json': [
                    {'firstName': 'Evencio', 'middleName': '', 'lastName': 'Pena'}
                ],
            }
        ],
        'pagination': {
            'currentPageNumber': 1,
            'resultsPerPage': 10,
            'totalPages': 1,
            'totalResults': 1,
        },
    },
}


class HealthCheckTests(APITestCase):
    def test_health_check_returns_ok(self):
        response = self.client.get('/api/health/', HTTP_HOST='localhost')

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data['status'], 'ok')
        self.assertEqual(response.data['service'], 'PeopleGraph API')


class PhoneLookupTests(APITestCase):
    def test_phone_lookup_fetches_and_caches_upstream_response(self):
        with patch('lookups.services.fetch_phone_lookup', return_value=SAMPLE_RESPONSE) as fetch:
            response = self.client.post(
                '/api/v1/lookups/phone/',
                {'phone_number': '(617) 541-2753'},
                format='json',
                HTTP_HOST='localhost',
            )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data['source'], 'upstream')
        self.assertEqual(response.data['data']['result_count'], 1)
        self.assertEqual(response.data['data']['persons'][0]['name'], 'Evencio Pena')
        self.assertEqual(PhoneLookupCache.objects.count(), 1)
        fetch.assert_called_once_with('6175412753')

    def test_phone_lookup_uses_cache_when_available(self):
        PhoneLookupCache.objects.create(
            normalized_phone='+16175412753',
            display_phone='(617) 541-2753',
            status='success',
            message='Found 1 result(s)',
            result_count=1,
            raw_response=SAMPLE_RESPONSE,
        )

        with patch('lookups.services.fetch_phone_lookup') as fetch:
            response = self.client.post(
                '/api/v1/lookups/phone/',
                {'phone_number': '6175412753'},
                format='json',
                HTTP_HOST='localhost',
            )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data['source'], 'cache')
        self.assertEqual(response.data['query']['normalized_phone'], '+16175412753')
        fetch.assert_not_called()

    def test_phone_lookup_rejects_invalid_phone(self):
        response = self.client.post(
            '/api/v1/lookups/phone/',
            {'phone_number': '123'},
            format='json',
            HTTP_HOST='localhost',
        )

        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.data['status'], 'error')
