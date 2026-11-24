#!/usr/bin/env python3
"""Exercise the built image with a real isolated CrowdSec LAPI; no public ports."""
import os
import pathlib
import re
import subprocess
import time
import uuid

engine = os.environ.get('CONTAINER_ENGINE', 'docker')
image = os.environ.get('TEST_IMAGE', 'waf:ci')
crowdsec_image = os.environ.get('CROWDSEC_IMAGE', 'docker.io/crowdsecurity/crowdsec:v1.8.2')
prefix = 'waf-ci-' + uuid.uuid4().hex[:10]
network, cs, waf = prefix, prefix + '-cs', prefix + '-waf'


def run(*args, check=True):
    return subprocess.run([engine, *args], text=True, stdout=subprocess.PIPE,
                          stderr=subprocess.PIPE, check=check, timeout=180)


def eventually(check, label, timeout=120):
    end = time.monotonic() + timeout
    while time.monotonic() < end:
        if check():
            print('PASS:', label, flush=True)
            return
        time.sleep(2)
    raise AssertionError('Timed out: ' + label)


def request(path='/', ip='198.51.100.23', data=None):
    args = ['exec', waf, '/bin/busybox', 'wget', '-S', '-O', '-', '-T', '5',
            '--header=X-Forwarded-For: ' + ip]
    if data is not None:
        args += ['--header=Content-Type: application/x-www-form-urlencoded', '--post-data=' + data]
    result = run(*args, 'http://127.0.0.1:8081' + path, check=False)
    codes = re.findall(r'HTTP/\S+\s+(\d{3})', result.stderr)
    return (int(codes[-1]) if codes else 0), result.stdout


try:
    modules = run('run', '--rm', image, 'list-modules').stdout.splitlines()
    for module in ('crowdsec', 'http.handlers.crowdsec', 'http.handlers.waf'):
        assert module in modules, 'Missing module: ' + module
    print('PASS: compiled modules', flush=True)
    run('network', 'create', network)
    run('run', '-d', '--name', cs, '--network', network, '--network-alias', 'crowdsec',
        '-e', 'DISABLE_ONLINE_API=true', crowdsec_image)
    eventually(lambda: run('exec', cs, 'cscli', 'lapi', 'status', check=False).returncode == 0,
               'CrowdSec ready')
    key = run('exec', cs, 'cscli', 'bouncers', 'add', 'integration', '-o', 'raw').stdout.strip()
    assert key, 'Missing bouncer API key'
    config = pathlib.Path(__file__).with_name('Caddyfile').resolve()
    run('run', '-d', '--name', waf, '--network', network,
        '--read-only', '--cap-drop=ALL', '--security-opt=no-new-privileges',
        '--tmpfs', '/tmp:rw,noexec,nosuid,size=16m',
        '-e', 'CROWDSEC_API_KEY=' + key,
        '-v', str(config) + ':/etc/caddy/Caddyfile:ro', image)
    eventually(lambda: request() == (200, 'integration-ok'), 'normal request through both modules')
    assert request('/?q=%3Cscript%3Ealert%281%29%3C%2Fscript%3E')[0] == 403, 'CRS XSS not blocked'
    print('PASS: Coraza CRS blocks XSS', flush=True)
    assert request(data='message=bonjour')[0] == 200, 'Benign POST blocked'
    assert request(data='message=%3Cscript%3Ealert%281%29%3C%2Fscript%3E')[0] == 403, 'POST XSS not blocked'
    print('PASS: normal POST accepted, malicious POST blocked', flush=True)
    run('exec', cs, 'cscli', 'decisions', 'add', '--ip', '198.51.100.23', '--duration', '5m')
    eventually(lambda: request()[0] == 403, 'CrowdSec decision blocks client')
    assert request(ip='198.51.100.24') == (200, 'integration-ok'), 'Unbanned client blocked'
    run('exec', cs, 'cscli', 'decisions', 'delete', '--ip', '198.51.100.23')
    eventually(lambda: request() == (200, 'integration-ok'), 'CrowdSec decision removal restores access')
except Exception:
    for name in (waf, cs):
        result = run('logs', '--tail', '80', name, check=False)
        print(result.stdout + result.stderr)
    raise
finally:
    for name in (waf, cs):
        run('rm', '-f', '-v', name, check=False)
    run('network', 'rm', network, check=False)
