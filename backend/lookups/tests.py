import json
from unittest.mock import MagicMock, patch

from django.core.exceptions import ValidationError
from django.test import override_settings
from rest_framework.test import APITestCase

from .admin import SecondaryRelayConfigurationForm
from .models import (
    BlacklistLookupCache,
    NameAddrLookupCache,
    PhoneLookupAudit,
    PhoneLookupCache,
    SecondaryRelayConfiguration,
)
from .services import UpstreamLookupError, fetch_secondary_name_lookup, fetch_secondary_phone_lookup


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

EMPTY_RESPONSE = {
    'status': 'success',
    'message': 'Found 0 result(s)',
    'data': {'persons': [], 'pagination': {'totalResults': 0}},
}

SECONDARY_RESPONSE = {
    'status': 'success',
    'message': 'Found 1 result(s)',
    'data': {
        'persons': [
            {
                'id': 'secondary-name-0-john doe-11224',
                'name': 'John Doe',
                'age': 53,
                'zipcode': '11224',
                'state': 'NY',
                'email': 'john@example.com',
                'is_secondary': True,
            }
        ],
        'pagination': {'totalResults': 1},
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
    def test_secondary_phone_request_uses_database_relay_configuration(self):
        configuration = SecondaryRelayConfiguration.objects.create(
            phone_endpoint='https://relay-example.trycloudflare.com/v1/lookups/phone',
            name_endpoint='https://relay-example.trycloudflare.com/v1/lookups/name',
            api_token='relay-token-with-at-least-thirty-two-characters',
            timeout_seconds=17,
        )
        relay_response = MagicMock()
        relay_response.read.return_value = json.dumps(
            {'status': 'not_found', 'message': 'No records found.', 'result_count': 0, 'persons': []}
        ).encode()
        relay_response.__enter__.return_value = relay_response

        with patch('lookups.services.urlopen', return_value=relay_response) as relay_request:
            result = fetch_secondary_phone_lookup('5405605817')

        request = relay_request.call_args.args[0]
        self.assertEqual(request.full_url, configuration.phone_endpoint)
        self.assertEqual(request.method, 'POST')
        self.assertEqual(json.loads(request.data), {'phone_number': '5405605817'})
        self.assertEqual(
            request.headers['Authorization'],
            'Bearer relay-token-with-at-least-thirty-two-characters',
        )
        self.assertEqual(relay_request.call_args.kwargs['timeout'], 17)
        self.assertEqual(result['status'], 'not_found')

    def test_phone_lookup_falls_back_after_empty_primary_and_caches_secondary(self):
        with (
            patch('lookups.views.validate_turnstile_token', return_value={'success': True}),
            patch('lookups.services.fetch_phone_lookup', return_value=EMPTY_RESPONSE) as primary_fetch,
            patch('lookups.services.fetch_secondary_phone_lookup', return_value=SECONDARY_RESPONSE) as secondary_fetch,
            patch(
                'lookups.services.fetch_blacklist_lookup',
                return_value=SAMPLE_BLACKLIST_RESPONSE,
            ) as blacklist_fetch,
        ):
            response = self.client.post(
                '/api/v1/lookups/phone/',
                {'phone_number': '6175412753', 'turnstile_token': 'test-token'},
                format='json',
                HTTP_HOST='localhost',
            )
            cached_response = self.client.post(
                '/api/v1/lookups/phone/',
                {'phone_number': '6175412753', 'turnstile_token': 'test-token'},
                format='json',
                HTTP_HOST='localhost',
            )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data['provider'], 'secondary')
        self.assertEqual(response.data['blacklist']['summary_status'], 'State DNC | Federal DNC')
        self.assertEqual(cached_response.data['source'], 'cache')
        self.assertEqual(cached_response.data['blacklist']['source'], 'cache')
        self.assertEqual(response.data['data']['persons'][0]['email'], 'john@example.com')
        self.assertNotIn('raw', response.data['data']['persons'][0])
        self.assertEqual(PhoneLookupCache.objects.get().provider, 'secondary')
        self.assertTrue(PhoneLookupCache.objects.get().secondary_attempted)
        primary_fetch.assert_called_once_with('6175412753')
        secondary_fetch.assert_called_once_with('6175412753')
        blacklist_fetch.assert_called_once_with('6175412753')

    @override_settings(TRUST_X_FORWARDED_FOR=True)
    def test_phone_lookup_fetches_and_caches_upstream_response(self):
        with (
            patch('lookups.views.validate_turnstile_token', return_value={'success': True}) as turnstile,
            patch('lookups.services.fetch_phone_lookup', return_value=SAMPLE_RESPONSE) as fetch,
            patch('lookups.services.fetch_blacklist_lookup', return_value=SAMPLE_BLACKLIST_RESPONSE) as blacklist_fetch,
        ):
            response = self.client.post(
                '/api/v1/lookups/phone/',
                {'phone_number': '(617) 541-2753', 'turnstile_token': 'test-token'},
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
        turnstile.assert_called_once_with('test-token', '203.0.113.10')
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
            patch('lookups.views.validate_turnstile_token', return_value={'success': True}),
            patch('lookups.services.fetch_phone_lookup') as fetch,
            patch('lookups.services.fetch_blacklist_lookup') as blacklist_fetch,
        ):
            response = self.client.post(
                '/api/v1/lookups/phone/',
                {'phone_number': '6175412753', 'turnstile_token': 'test-token'},
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
        with patch('lookups.views.validate_turnstile_token', return_value={'success': True}):
            response = self.client.post(
                '/api/v1/lookups/phone/',
                {'phone_number': '123', 'turnstile_token': 'test-token'},
                format='json',
                HTTP_HOST='localhost',
            )
            cached_response = self.client.post(
                '/api/v1/lookups/name-address/',
                {'full_name': 'John Doe', 'address_or_zip': 'Brooklyn, NY', 'turnstile_token': 'test-token'},
                format='json',
                HTTP_HOST='localhost',
            )

        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.data['status'], 'error')

    def test_phone_lookup_does_not_trust_forwarded_ip_by_default(self):
        with (
            patch('lookups.views.validate_turnstile_token', return_value={'success': True}) as turnstile,
            patch('lookups.services.fetch_phone_lookup', return_value=SAMPLE_RESPONSE),
            patch('lookups.services.fetch_blacklist_lookup', return_value=SAMPLE_BLACKLIST_RESPONSE),
        ):
            response = self.client.post(
                '/api/v1/lookups/phone/',
                {'phone_number': '(617) 541-2753', 'turnstile_token': 'test-token'},
                format='json',
                HTTP_HOST='localhost',
                HTTP_X_FORWARDED_FOR='203.0.113.10',
                REMOTE_ADDR='198.51.100.24',
            )

        self.assertEqual(response.status_code, 200)
        audit = PhoneLookupAudit.objects.first()
        self.assertEqual(audit.public_ip, '198.51.100.24')
        turnstile.assert_called_once_with('test-token', '198.51.100.24')

    def test_phone_lookup_rejects_missing_turnstile_token(self):
        response = self.client.post(
            '/api/v1/lookups/phone/',
            {'phone_number': '6175412753'},
            format='json',
            HTTP_HOST='localhost',
        )

        self.assertEqual(response.status_code, 403)
        self.assertEqual(response.data['status'], 'error')


class NameAddressLookupTests(APITestCase):
    def test_name_lookup_falls_back_with_state_after_empty_primary(self):
        with (
            patch('lookups.views.validate_turnstile_token', return_value={'success': True}),
            patch('lookups.services.fetch_name_address_lookup', return_value=EMPTY_RESPONSE) as primary_fetch,
            patch('lookups.services.fetch_secondary_name_lookup', return_value=SECONDARY_RESPONSE) as secondary_fetch,
        ):
            response = self.client.post(
                '/api/v1/lookups/name-address/',
                {'full_name': 'John Doe', 'address_or_zip': 'Brooklyn, NY', 'turnstile_token': 'test-token'},
                format='json',
                HTTP_HOST='localhost',
            )
            cached_response = self.client.post(
                '/api/v1/lookups/name-address/',
                {'full_name': 'John Doe', 'address_or_zip': 'Brooklyn, NY', 'turnstile_token': 'test-token'},
                format='json',
                HTTP_HOST='localhost',
            )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data['provider'], 'secondary')
        self.assertEqual(cached_response.data['source'], 'cache')
        self.assertEqual(response.data['data']['persons'][0], SECONDARY_RESPONSE['data']['persons'][0])
        self.assertEqual(NameAddrLookupCache.objects.get().provider, 'secondary')
        self.assertTrue(NameAddrLookupCache.objects.get().secondary_attempted)
        primary_fetch.assert_called_once_with('John', 'Doe', 'Brooklyn, NY', '')
        secondary_fetch.assert_called_once_with('John', 'Doe', 'NY')

    def test_name_lookup_does_not_fall_back_for_zip_only_input(self):
        with (
            patch('lookups.views.validate_turnstile_token', return_value={'success': True}),
            patch('lookups.services.fetch_name_address_lookup', return_value=EMPTY_RESPONSE),
            patch('lookups.services.fetch_secondary_name_lookup') as secondary_fetch,
        ):
            response = self.client.post(
                '/api/v1/lookups/name-address/',
                {'full_name': 'John Doe', 'address_or_zip': '10001', 'turnstile_token': 'test-token'},
                format='json',
                HTTP_HOST='localhost',
            )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data['provider'], 'primary')
        self.assertEqual(response.data['data']['result_count'], 0)
        secondary_fetch.assert_not_called()

    def test_name_lookup_does_not_fall_back_when_address_contains_zip(self):
        with (
            patch('lookups.views.validate_turnstile_token', return_value={'success': True}),
            patch('lookups.services.fetch_name_address_lookup', return_value=EMPTY_RESPONSE),
            patch('lookups.services.fetch_secondary_name_lookup') as secondary_fetch,
        ):
            response = self.client.post(
                '/api/v1/lookups/name-address/',
                {
                    'full_name': 'John Doe',
                    'address_or_zip': 'Brooklyn, NY 10001',
                    'turnstile_token': 'test-token',
                },
                format='json',
                HTTP_HOST='localhost',
            )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data['provider'], 'primary')
        secondary_fetch.assert_not_called()

    def test_name_address_lookup_fetches_and_caches_upstream_response(self):
        with (
            patch('lookups.views.validate_turnstile_token', return_value={'success': True}) as turnstile,
            patch('lookups.services.fetch_name_address_lookup', return_value=SAMPLE_RESPONSE) as fetch,
        ):
            response = self.client.post(
                '/api/v1/lookups/name-address/',
                {'full_name': 'Evencio Pena', 'address_or_zip': '02118', 'turnstile_token': 'name-token'},
                format='json',
                HTTP_HOST='localhost',
                REMOTE_ADDR='198.51.100.15',
            )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data['source'], 'upstream')
        self.assertEqual(response.data['data']['result_count'], 1)
        self.assertEqual(response.data['data']['persons'][0]['name'], 'Evencio Pena')
        self.assertNotIn('blacklist', response.data)
        self.assertEqual(NameAddrLookupCache.objects.count(), 1)
        cache = NameAddrLookupCache.objects.first()
        self.assertEqual(cache.first_name_normalized, 'evencio')
        self.assertEqual(cache.last_name_normalized, 'pena')
        self.assertEqual(cache.location_normalized, 'zip:02118')
        turnstile.assert_called_once_with('name-token', '198.51.100.15')
        fetch.assert_called_once_with('Evencio', 'Pena', '', '02118')

    def test_name_address_lookup_uses_cache_when_available(self):
        NameAddrLookupCache.objects.create(
            first_name_normalized='evencio',
            last_name_normalized='pena',
            location_normalized='zip:02118',
            address='',
            zipcode='02118',
            full_name='Evencio Pena',
            status='success',
            message='Found 1 result(s)',
            result_count=1,
            raw_response=SAMPLE_RESPONSE,
        )

        with (
            patch('lookups.views.validate_turnstile_token', return_value={'success': True}),
            patch('lookups.services.fetch_name_address_lookup') as fetch,
        ):
            response = self.client.post(
                '/api/v1/lookups/name-address/',
                {'full_name': ' Evencio   Pena ', 'address_or_zip': '02118', 'turnstile_token': 'test-token'},
                format='json',
                HTTP_HOST='localhost',
            )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data['source'], 'cache')
        self.assertEqual(response.data['query']['zipcode'], '02118')
        fetch.assert_not_called()

    def test_name_address_lookup_sends_address_payload_for_non_zip_location(self):
        with (
            patch('lookups.views.validate_turnstile_token', return_value={'success': True}),
            patch('lookups.services.fetch_name_address_lookup', return_value=SAMPLE_RESPONSE) as fetch,
        ):
            response = self.client.post(
                '/api/v1/lookups/name-address/',
                {'full_name': 'Evencio Pena', 'address_or_zip': 'Boston, MA', 'turnstile_token': 'test-token'},
                format='json',
                HTTP_HOST='localhost',
            )

        self.assertEqual(response.status_code, 200)
        cache = NameAddrLookupCache.objects.first()
        self.assertEqual(cache.address, 'Boston, MA')
        self.assertEqual(cache.zipcode, '')
        self.assertEqual(cache.location_normalized, 'address:boston, ma')
        fetch.assert_called_once_with('Evencio', 'Pena', 'Boston, MA', '')

    def test_name_address_lookup_rejects_missing_last_name(self):
        with patch('lookups.views.validate_turnstile_token', return_value={'success': True}):
            response = self.client.post(
                '/api/v1/lookups/name-address/',
                {'full_name': 'Evencio', 'address_or_zip': '02118', 'turnstile_token': 'test-token'},
                format='json',
                HTTP_HOST='localhost',
            )

        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.data['status'], 'error')


class SecondaryRelayConfigurationTests(APITestCase):
    def test_configuration_rejects_insecure_or_wrong_paths(self):
        insecure = SecondaryRelayConfiguration(
            phone_endpoint='http://relay.example/v1/lookups/phone',
            name_endpoint='https://relay.example/v1/lookups/name',
            api_token='relay-token-with-at-least-thirty-two-characters',
        )
        wrong_path = SecondaryRelayConfiguration(
            phone_endpoint='https://relay.example/v1/lookups/phone',
            name_endpoint='https://relay.example/api/name',
            api_token='relay-token-with-at-least-thirty-two-characters',
        )

        with self.assertRaises(ValidationError):
            insecure.full_clean()
        with self.assertRaises(ValidationError):
            wrong_path.full_clean()

    def test_only_one_relay_configuration_can_exist(self):
        SecondaryRelayConfiguration.objects.create(
            phone_endpoint='https://one.example/v1/lookups/phone',
            name_endpoint='https://one.example/v1/lookups/name',
            api_token='relay-token-with-at-least-thirty-two-characters',
        )

        with self.assertRaises(ValidationError):
            SecondaryRelayConfiguration.objects.create(
                phone_endpoint='https://two.example/v1/lookups/phone',
                name_endpoint='https://two.example/v1/lookups/name',
                api_token='another-token-with-at-least-thirty-two-characters',
            )

    def test_admin_form_keeps_existing_token_when_left_blank(self):
        configuration = SecondaryRelayConfiguration.objects.create(
            phone_endpoint='https://one.example/v1/lookups/phone',
            name_endpoint='https://one.example/v1/lookups/name',
            api_token='relay-token-with-at-least-thirty-two-characters',
        )
        form = SecondaryRelayConfigurationForm(
            instance=configuration,
            data={
                'enabled': True,
                'phone_endpoint': 'https://two.example/v1/lookups/phone',
                'name_endpoint': 'https://two.example/v1/lookups/name',
                'api_token': '',
                'timeout_seconds': 20,
            },
        )

        self.assertTrue(form.is_valid(), form.errors)
        saved = form.save()
        self.assertEqual(saved.api_token, 'relay-token-with-at-least-thirty-two-characters')
        self.assertEqual(saved.phone_endpoint, 'https://two.example/v1/lookups/phone')

    def test_name_relay_uses_database_endpoint_and_compacts_response(self):
        SecondaryRelayConfiguration.objects.create(
            phone_endpoint='https://relay.example/v1/lookups/phone',
            name_endpoint='https://relay.example/v1/lookups/name',
            api_token='relay-token-with-at-least-thirty-two-characters',
        )
        relay_response = MagicMock()
        relay_response.read.return_value = json.dumps(
            {
                'status': 'success',
                'message': 'Found 1 result(s)',
                'result_count': 1,
                'persons': [
                    {
                        'id': 'relay-name-1',
                        'name': 'Jane Doe',
                        'age': 42,
                        'zipcode': '10001',
                        'state': 'ny',
                        'email': 'jane@example.com',
                        'relatives': ['must not pass through'],
                    }
                ],
            }
        ).encode()
        relay_response.__enter__.return_value = relay_response

        with patch('lookups.services.urlopen', return_value=relay_response) as relay_request:
            result = fetch_secondary_name_lookup('Jane', 'Doe', 'NY')

        request = relay_request.call_args.args[0]
        self.assertEqual(request.full_url, 'https://relay.example/v1/lookups/name')
        self.assertEqual(
            json.loads(request.data),
            {'first_name': 'Jane', 'last_name': 'Doe', 'state': 'NY'},
        )
        self.assertEqual(
            result['data']['persons'][0],
            {
                'id': 'relay-name-1',
                'name': 'Jane Doe',
                'age': 42,
                'zipcode': '10001',
                'state': 'NY',
                'email': 'jane@example.com',
                'is_secondary': True,
            },
        )

    def test_disabled_or_missing_relay_is_unavailable(self):
        SecondaryRelayConfiguration.objects.create(
            enabled=False,
            phone_endpoint='https://relay.example/v1/lookups/phone',
            name_endpoint='https://relay.example/v1/lookups/name',
            api_token='relay-token-with-at-least-thirty-two-characters',
        )

        with self.assertRaisesRegex(UpstreamLookupError, 'not configured'):
            fetch_secondary_phone_lookup('2025550123')


class NameAddressValidationTests(APITestCase):
    def test_name_address_lookup_rejects_invalid_name_characters(self):
        with (
            patch('lookups.views.validate_turnstile_token', return_value={'success': True}),
            patch('lookups.services.fetch_name_address_lookup') as fetch,
        ):
            response = self.client.post(
                '/api/v1/lookups/name-address/',
                {'full_name': 'Evencio <script>', 'address_or_zip': '02118', 'turnstile_token': 'test-token'},
                format='json',
                HTTP_HOST='localhost',
            )

        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.data['status'], 'error')
        fetch.assert_not_called()

    def test_name_address_lookup_rejects_numeric_name(self):
        with (
            patch('lookups.views.validate_turnstile_token', return_value={'success': True}),
            patch('lookups.services.fetch_name_address_lookup') as fetch,
        ):
            response = self.client.post(
                '/api/v1/lookups/name-address/',
                {'full_name': 'Evencio123 Pena', 'address_or_zip': '02118', 'turnstile_token': 'test-token'},
                format='json',
                HTTP_HOST='localhost',
            )

        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.data['status'], 'error')
        fetch.assert_not_called()

    def test_name_address_lookup_rejects_invalid_location_characters(self):
        with (
            patch('lookups.views.validate_turnstile_token', return_value={'success': True}),
            patch('lookups.services.fetch_name_address_lookup') as fetch,
        ):
            response = self.client.post(
                '/api/v1/lookups/name-address/',
                {
                    'full_name': 'Evencio Pena',
                    'address_or_zip': '<script>alert(1)</script>',
                    'turnstile_token': 'test-token',
                },
                format='json',
                HTTP_HOST='localhost',
            )

        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.data['status'], 'error')
        fetch.assert_not_called()

    def test_name_address_lookup_rejects_overlong_location(self):
        with patch('lookups.views.validate_turnstile_token', return_value={'success': True}):
            response = self.client.post(
                '/api/v1/lookups/name-address/',
                {
                    'full_name': 'Evencio Pena',
                    'address_or_zip': 'A' * 256,
                    'turnstile_token': 'test-token',
                },
                format='json',
                HTTP_HOST='localhost',
            )

        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.data['status'], 'error')

    def test_name_address_lookup_rejects_missing_turnstile_token(self):
        response = self.client.post(
            '/api/v1/lookups/name-address/',
            {'full_name': 'Evencio Pena', 'address_or_zip': '02118'},
            format='json',
            HTTP_HOST='localhost',
        )

        self.assertEqual(response.status_code, 403)
        self.assertEqual(response.data['status'], 'error')
