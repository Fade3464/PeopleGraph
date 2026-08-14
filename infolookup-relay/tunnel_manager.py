import json
import os
import re
import signal
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import urlsplit
from urllib.request import Request, urlopen


TUNNEL_URL_PATTERN = re.compile(r'https://[a-z0-9-]+\.trycloudflare\.com')
ORIGIN_URL = os.environ.get('TUNNEL_ORIGIN_URL', 'http://relay:8000')
STATE_FILE = Path(os.environ.get('TUNNEL_STATE_FILE', '/tunnel-state/current-tunnel.env'))
DISCORD_WEBHOOK_URL = os.environ.get('DISCORD_WEBHOOK_URL', '').strip()
RELAY_API_TOKEN = os.environ.get('RELAY_API_TOKEN', '').strip()


def extract_tunnel_url(line: str) -> str | None:
    match = TUNNEL_URL_PATTERN.search(line.lower())
    return match.group(0) if match else None


def write_state(status: str, tunnel_url: str | None = None) -> None:
    lines = [
        f'TUNNEL_STATUS={status}',
        f'UPDATED_AT={datetime.now(timezone.utc).isoformat()}',
    ]
    if tunnel_url:
        lines.extend(
            [
                f'TUNNEL_BASE_URL={tunnel_url}',
                f'PHONE_RELAY_ENDPOINT={tunnel_url}/v1/lookups/phone',
                f'NAME_RELAY_ENDPOINT={tunnel_url}/v1/lookups/name',
            ]
        )

    STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
    temporary = STATE_FILE.with_name(f'.{STATE_FILE.name}.{os.getpid()}')
    temporary.write_text('\n'.join(lines) + '\n', encoding='utf-8')
    os.replace(temporary, STATE_FILE)


def notify_discord(tunnel_url: str) -> bool:
    if not DISCORD_WEBHOOK_URL:
        return False

    parsed = urlsplit(DISCORD_WEBHOOK_URL)
    if (
        parsed.scheme != 'https'
        or parsed.hostname not in {'discord.com', 'discordapp.com'}
        or not parsed.path.startswith('/api/webhooks/')
        or parsed.username
        or parsed.password
    ):
        print('Discord notification skipped: webhook URL is invalid.', flush=True)
        return False

    message = '\n'.join(
        [
            '**PeopleGraph relay tunnel updated**',
            f'API token: `{RELAY_API_TOKEN or "(not configured)"}`',
            f'Phone endpoint: `{tunnel_url}/v1/lookups/phone`',
            f'Name endpoint: `{tunnel_url}/v1/lookups/name`',
        ]
    )
    payload = json.dumps(
        {
            'username': 'PeopleGraph Relay',
            'allowed_mentions': {'parse': []},
            'content': message,
        }
    ).encode('utf-8')
    request = Request(
        DISCORD_WEBHOOK_URL,
        data=payload,
        headers={'Content-Type': 'application/json', 'User-Agent': 'PeopleGraph-Tunnel-Manager/1.0'},
        method='POST',
    )
    try:
        with urlopen(request, timeout=10) as response:
            response.read(1024)
        print('Discord tunnel notification sent.', flush=True)
        return True
    except (HTTPError, URLError, OSError):
        print('Discord tunnel notification failed.', flush=True)
        return False


def main() -> int:
    write_state('starting')
    command = [
        '/usr/local/bin/cloudflared',
        'tunnel',
        '--no-autoupdate',
        '--loglevel',
        'info',
        '--metrics',
        '0.0.0.0:2000',
        '--url',
        ORIGIN_URL,
    ]
    process = subprocess.Popen(
        command,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        bufsize=1,
    )

    def stop_child(signum, _frame):
        if process.poll() is None:
            process.send_signal(signum)

    signal.signal(signal.SIGTERM, stop_child)
    signal.signal(signal.SIGINT, stop_child)

    current_url = None
    assert process.stdout is not None
    for line in process.stdout:
        print(line, end='', flush=True)
        discovered_url = extract_tunnel_url(line)
        if discovered_url and discovered_url != current_url:
            current_url = discovered_url
            write_state('ready', current_url)
            print(f'Current tunnel endpoints saved to {STATE_FILE}', flush=True)
            notify_discord(current_url)

    return_code = process.wait()
    write_state('stopped', current_url)
    return return_code


if __name__ == '__main__':
    sys.exit(main())
