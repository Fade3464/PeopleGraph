from unittest.mock import patch

from rest_framework.test import APITestCase

from .models import BlacklistLookupCache, PhoneLookupAudit, PhoneLookupCache


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

SAMPLE_BLACKLIST_RESPONSE = {
    'status': 'ok',
    'lookup': {
        'phone': '8134044790',
        'code': 'florida-dnc,federal-dnc',
        'status': 'success',
        'message': 'FederalDNC',
        'tcpa_litigator': {
            'summary_status': 'State DNC | Federal DNC',
            'risk_category': 'state_dnc',
            'results': {
                'status_array': ['state_dnc', 'federal_dnc'],
                'is_bad_number': True,
                'status': 'State DNC | Federal DNC',
            },
        },
    },
    'scrub': {
        'summary_status': 'State DNC | Federal DNC',
        'risk_category': 'state_dnc',
        'results': {
            'status_array': ['state_dnc', 'federal_dnc'],
            'is_bad_number': True,
            'status': 'State DNC | Federal DNC',
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
        with (
            patch('lookups.services.fetch_phone_lookup', return_value=SAMPLE_RESPONSE) as fetch,
            patch('lookups.services.fetch_blacklist_lookup', return_value=SAMPLE_BLACKLIST_RESPONSE) as blacklist_fetch,
        ):
            response = self.client.post(
                '/api/v1/lookups/phone/',
                {'phone_number': '(617) 541-2753'},
                format='json',
                HTTP_HOST='localhost',
                HTTP_X_FORWARDED_FOR='203.0.113.10, 10.0.0.1',
            )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data['source'], 'upstream')
        self.assertEqual(response.data['data']['result_count'], 1)
        self.assertEqual(response.data['data']['persons'][0]['name'], 'Evencio Pena')
        self.assertEqual(response.data['blacklist']['source'], 'upstream')
        self.assertEqual(response.data['blacklist']['summary_status'], 'State DNC | Federal DNC')
        self.assertEqual(response.data['blacklist']['bla_code'], 'florida-dnc,federal-dnc')
        self.assertEqual(response.data['blacklist']['tcpa_status'], 'State DNC | Federal DNC')
        self.assertEqual(PhoneLookupCache.objects.count(), 1)
        self.assertEqual(BlacklistLookupCache.objects.count(), 1)
        self.assertEqual(PhoneLookupAudit.objects.count(), 1)
        audit = PhoneLookupAudit.objects.first()
        self.assertEqual(audit.normalized_phone, '+16175412753')
        self.assertFalse(audit.fetched_from_dbcache)
        self.assertFalse(audit.fetched_from_bla_cache)
        self.assertEqual(audit.public_ip, '203.0.113.10')
        fetch.assert_called_once_with('6175412753')
        blacklist_fetch.assert_called_once_with('6175412753')

    def test_phone_lookup_uses_cache_when_available(self):
        PhoneLookupCache.objects.create(
            normalized_phone='+16175412753',
            display_phone='(617) 541-2753',
            status='success',
            message='Found 1 result(s)',
            result_count=1,
            raw_response=SAMPLE_RESPONSE,
        )
        BlacklistLookupCache.objects.create(
            normalized_phone='+16175412753',
            phone_digits='6175412753',
            display_phone='(617) 541-2753',
            bla_code='florida-dnc,federal-dnc',
            tcpa_status='State DNC | Federal DNC',
            summary_status='State DNC | Federal DNC',
            risk_category='state_dnc',
            status_array=['state_dnc', 'federal_dnc'],
            is_bad_number=True,
            raw_response=SAMPLE_BLACKLIST_RESPONSE,
        )

        with (
            patch('lookups.services.fetch_phone_lookup') as fetch,
            patch('lookups.services.fetch_blacklist_lookup') as blacklist_fetch,
        ):
            response = self.client.post(
                '/api/v1/lookups/phone/',
                {'phone_number': '6175412753'},
                format='json',
                HTTP_HOST='localhost',
                REMOTE_ADDR='198.51.100.24',
            )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data['source'], 'cache')
        self.assertEqual(response.data['blacklist']['source'], 'cache')
        self.assertEqual(response.data['query']['normalized_phone'], '+16175412753')
        audit = PhoneLookupAudit.objects.first()
        self.assertTrue(audit.fetched_from_dbcache)
        self.assertTrue(audit.fetched_from_bla_cache)
        self.assertEqual(audit.public_ip, '198.51.100.24')
        fetch.assert_not_called()
        blacklist_fetch.assert_not_called()

    def test_phone_lookup_rejects_invalid_phone(self):
        response = self.client.post(
            '/api/v1/lookups/phone/',
            {'phone_number': '123'},
            format='json',
            HTTP_HOST='localhost',
        )

        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.data['status'], 'error')
