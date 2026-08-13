import os
import re
import signal
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path


TUNNEL_URL_PATTERN = re.compile(r'https://[a-z0-9-]+\.trycloudflare\.com')
ORIGIN_URL = os.environ.get('TUNNEL_ORIGIN_URL', 'http://relay:8000')
STATE_FILE = Path(os.environ.get('TUNNEL_STATE_FILE', '/tunnel-state/current-tunnel.env'))


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

    return_code = process.wait()
    write_state('stopped', current_url)
    return return_code


if __name__ == '__main__':
    sys.exit(main())
