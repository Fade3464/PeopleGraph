import importlib
import os
import json
import asyncio
from unittest.mock import MagicMock, patch

import httpx
import pytest


os.environ.setdefault('RELAY_API_TOKEN', 'test-token-with-at-least-thirty-two-characters')
relay = importlib.import_module('app')
tunnel_manager = importlib.import_module('tunnel_manager')


class ASGITestClient:
    def request(self, method, path, **kwargs):
        async def send_request():
            transport = httpx.ASGITransport(app=relay.app)
            async with httpx.AsyncClient(transport=transport, base_url='http://testserver') as session:
                return await session.request(method, path, **kwargs)

        return asyncio.run(send_request())

    def get(self, path, **kwargs):
        return self.request('GET', path, **kwargs)

    def post(self, path, **kwargs):
        return self.request('POST', path, **kwargs)


client = ASGITestClient()


@pytest.fixture(autouse=True)
def run_blocking_calls_inline(monkeypatch):
    async def inline(function, *args, **kwargs):
        return function(*args, **kwargs)

    monkeypatch.setattr(relay.asyncio, 'to_thread', inline)


def auth_headers():
    return {'Authorization': f'Bearer {os.environ["RELAY_API_TOKEN"]}'}


def test_health_is_available():
    response = client.get('/health')
    assert response.status_code == 200
    assert response.json()['status'] == 'ok'


def test_upstream_diagnostics_requires_authentication():
    response = client.post('/v1/diagnostics/upstream')
    assert response.status_code == 401


def test_upstream_diagnostics_probe_both_apis_without_returning_records():
    relay.diagnostic_cached_at = 0
    relay.diagnostic_cached_response = None
    with (
        patch.object(relay, 'DIAGNOSTIC_PHONE_NUMBER', '2025550123'),
        patch.object(relay, 'DIAGNOSTIC_FIRST_NAME', 'Jane'),
        patch.object(relay, 'DIAGNOSTIC_LAST_NAME', 'Doe'),
        patch.object(relay, 'DIAGNOSTIC_STATE', 'NY'),
        patch.object(relay, 'fetch_infolookup_phone', return_value={'status': 'ok', 'person': [{'name': 'Hidden'}]}),
        patch.object(relay, 'fetch_infolookup_name', return_value={'status': 'ok', 'results': [{'name': 'Hidden'}]}),
    ):
        response = client.post('/v1/diagnostics/upstream', headers=auth_headers())

    assert response.status_code == 200
    assert response.json()['status'] == 'ok'
    assert response.json()['checks']['phone']['status'] == 'ok'
    assert response.json()['checks']['name']['status'] == 'ok'
    assert 'person' not in response.text
    assert 'Hidden' not in response.text


def test_lookup_requires_authentication():
    response = client.post('/v1/lookups/phone', json={'phone_number': '2025550123'})
    assert response.status_code == 401

    response = client.post(
        '/v1/lookups/name',
        json={'first_name': 'Jane', 'last_name': 'Doe', 'state': 'NY'},
    )
    assert response.status_code == 401


def test_lookup_rejects_invalid_or_extra_input():
    invalid = client.post('/v1/lookups/phone', headers=auth_headers(), json={'phone_number': '123'})
    extra = client.post(
        '/v1/lookups/phone',
        headers=auth_headers(),
        json={'phone_number': '2025550123', 'url': 'https://example.com'},
    )
    assert invalid.status_code == 422
    assert extra.status_code == 422


def test_lookup_returns_only_compact_fields():
    upstream = {
        'status': 'ok',
        'person': [
            {
                'name': 'Test Person',
                'age': '40',
                'addresses': [{'state': 'PA', 'zip': '19000', 'home': 'Hidden'}],
                'emails': ['test@example.com'],
                'relatives': ['Hidden Relative'],
            }
        ],
    }
    with patch.object(relay, 'fetch_infolookup_phone', return_value=upstream):
        response = client.post(
            '/v1/lookups/phone',
            headers=auth_headers(),
            json={'phone_number': '(202) 555-0123'},
        )

    assert response.status_code == 200
    person = response.json()['persons'][0]
    assert person['name'] == 'Test Person'
    assert person['zipcode'] == '19000'
    assert person['state'] == 'PA'
    assert person['email'] == 'test@example.com'
    assert 'addresses' not in person
    assert 'relatives' not in person


def test_lookup_returns_stable_empty_response():
    with patch.object(relay, 'fetch_infolookup_phone', return_value={'status': 'ok', 'person': []}):
        response = client.post(
            '/v1/lookups/phone',
            headers=auth_headers(),
            json={'phone_number': '2025550123'},
        )

    assert response.status_code == 200
    assert response.json() == {
        'status': 'not_found',
        'message': 'No records found.',
        'result_count': 0,
        'persons': [],
    }


def test_lookup_converts_upstream_failure_to_502():
    error = relay.RelayUpstreamError('need_turnstile', 'Lookup provider requires interactive verification.')
    with patch.object(relay, 'fetch_infolookup_phone', side_effect=error):
        response = client.post(
            '/v1/lookups/phone',
            headers=auth_headers(),
            json={'phone_number': '2025550123'},
        )

    assert response.status_code == 502
    assert response.json()['detail'] == 'Lookup provider requires interactive verification.'


def test_fetch_maps_turnstile_response_without_exposing_provider_payload():
    with patch.object(
        relay,
        'run_curl_json',
        side_effect=[
            {'status': 'ok', 'token': 'temporary-token', 'expires': 4102444800},
            {'status': 'error', 'code': 'need_turnstile', 'site_key': 'must-not-leak'},
        ],
    ):
        try:
            relay.fetch_infolookup_phone('2025550123')
        except relay.RelayUpstreamError as exc:
            assert exc.code == 'need_turnstile'
            assert 'site_key' not in exc.public_message
        else:
            raise AssertionError('Expected RelayUpstreamError')


def test_name_lookup_accepts_state_and_returns_only_compact_fields():
    upstream = {
        'status': 'ok',
        'results': [
            {
                'name': 'Jane Doe',
                'age': 42,
                'addressParts': {'state': 'NY', 'zip': '10001', 'city': 'Hidden'},
                'email': 'jane@example.com',
                'phones': ['Hidden'],
                'relatives': ['Hidden Relative'],
            }
        ],
    }
    with patch.object(relay, 'fetch_infolookup_name', return_value=upstream) as fetch:
        response = client.post(
            '/v1/lookups/name',
            headers=auth_headers(),
            json={'first_name': 'Jane', 'last_name': 'Doe', 'state': 'ny'},
        )

    assert response.status_code == 200
    fetch.assert_called_once_with('Jane', 'Doe', 'NY')
    person = response.json()['persons'][0]
    assert person == {
        'id': 'relay-name-0-jane-doe-10001',
        'name': 'Jane Doe',
        'age': 42,
        'zipcode': '10001',
        'state': 'NY',
        'email': 'jane@example.com',
        'is_secondary': True,
    }


def test_name_lookup_rejects_zip_and_invalid_state():
    zip_input = client.post(
        '/v1/lookups/name',
        headers=auth_headers(),
        json={'first_name': 'Jane', 'last_name': 'Doe', 'state': 'NY', 'zipcode': '10001'},
    )
    invalid_state = client.post(
        '/v1/lookups/name',
        headers=auth_headers(),
        json={'first_name': 'Jane', 'last_name': 'Doe', 'state': '10001'},
    )

    assert zip_input.status_code == 422
    assert invalid_state.status_code == 422


def test_name_upstream_request_uses_only_first_last_and_state():
    with patch.object(
        relay,
        'run_curl_json',
        return_value={'status': 'ok', 'count': 0, 'results': []},
    ) as curl:
        result = relay.fetch_infolookup_name('Jane', 'Doe', 'NY')

    arguments = curl.call_args.args[0]
    assert curl.call_args.kwargs['stage'] == 'name_lookup'
    assert 'Referer: https://infolookup.site/name-search' in arguments
    assert 'firstName=Jane' in arguments
    assert 'lastName=Doe' in arguments
    assert 'state=NY' in arguments
    assert not any('zip' in argument.lower() for argument in arguments)
    assert result == {'status': 'ok', 'count': 0, 'results': []}


def test_tunnel_manager_extracts_and_saves_current_endpoints(tmp_path):
    tunnel_url = tunnel_manager.extract_tunnel_url(
        'INF Requesting new quick Tunnel on https://Example-Relay.trycloudflare.com'
    )
    state_file = tmp_path / 'current-tunnel.env'

    with patch.object(tunnel_manager, 'STATE_FILE', state_file):
        tunnel_manager.write_state('ready', tunnel_url)

    assert tunnel_url == 'https://example-relay.trycloudflare.com'
    assert state_file.read_text(encoding='utf-8').splitlines()[0] == 'TUNNEL_STATUS=ready'
    contents = state_file.read_text(encoding='utf-8')
    assert 'PHONE_RELAY_ENDPOINT=https://example-relay.trycloudflare.com/v1/lookups/phone' in contents
    assert 'NAME_RELAY_ENDPOINT=https://example-relay.trycloudflare.com/v1/lookups/name' in contents


def test_discord_notification_sends_endpoints_and_token_in_message_body():
    response = MagicMock()
    response.read.return_value = b''
    response.__enter__.return_value = response
    with (
        patch.object(
            tunnel_manager,
            'DISCORD_WEBHOOK_URL',
            'https://discord.com/api/webhooks/123/secret',
        ),
        patch.object(tunnel_manager, 'RELAY_API_TOKEN', 'relay-secret-token'),
        patch.object(tunnel_manager, 'urlopen', return_value=response) as send,
    ):
        sent = tunnel_manager.notify_discord('https://example-relay.trycloudflare.com')

    assert sent is True
    request = send.call_args.args[0]
    payload = json.loads(request.data)
    message = payload['content']
    assert 'https://example-relay.trycloudflare.com/v1/lookups/phone' in message
    assert 'https://example-relay.trycloudflare.com/v1/lookups/name' in message
    assert 'relay-secret-token' in message
    assert payload['allowed_mentions'] == {'parse': []}
