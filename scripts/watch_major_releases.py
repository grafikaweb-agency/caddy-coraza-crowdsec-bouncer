#!/usr/bin/env python3
"""Watch upstream releases across Go module major paths. Default: read-only."""
import argparse
import json
import os
from pathlib import Path
import re
import urllib.request

COMPONENTS = {
    'caddyserver/caddy': ('Caddy', r'xcaddy build (v\d+\.\d+\.\d+)'),
    'corazawaf/coraza-caddy': ('Coraza Caddy', r'corazawaf/coraza-caddy(?:/v\d+)?@(v\d+\.\d+\.\d+)'),
    'hslatman/caddy-crowdsec-bouncer': ('CrowdSec bouncer', r'hslatman/caddy-crowdsec-bouncer/http(?:/v\d+)?@(v\d+\.\d+\.\d+)'),
}


def version(tag):
    match = re.fullmatch(r'v?(\d+)\.(\d+)\.(\d+)(?:\+[\w.-]+)?', tag)
    return tuple(map(int, match.groups())) if match else None


def candidates(current, releases):
    """One stable release per newer major, regardless of publication order."""
    result = {}
    for release in releases:
        number = version(release['tag_name'])
        if release.get('draft') or release.get('prerelease') or number is None:
            continue
        if number[0] > version(current)[0]:
            old = result.get(number[0])
            if old is None or number > version(old['tag_name']):
                result[number[0]] = release
    return [result[major] for major in sorted(result)]


def api(path, data=None):
    headers = {'Accept': 'application/vnd.github+json', 'User-Agent': 'waf-major-release-watch'}
    if os.environ.get('GH_TOKEN'):
        headers['Authorization'] = 'Bearer ' + os.environ['GH_TOKEN']
    payload = None if data is None else json.dumps(data).encode()
    request = urllib.request.Request('https://api.github.com/' + path, data=payload, headers=headers)
    with urllib.request.urlopen(request, timeout=30) as response:
        return json.load(response)


def pages(path):
    page = 1
    while True:
        items = api(path + ('&' if '?' in path else '?') + f'per_page=100&page={page}')
        yield from items
        if len(items) < 100:
            return
        page += 1


def marker(repo, release):
    return f'<!-- major-release-watch:{repo}:{version(release["tag_name"])[0]} -->'


def already_reported(issues, key):
    # Closed issues count too: closing an alert acknowledges this major.
    return any(key in (issue.get('body') or '') for issue in issues if 'pull_request' not in issue)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--create-issues', action='store_true')
    args = parser.parse_args()
    target = os.environ.get('GITHUB_REPOSITORY', 'grafikaweb-agency/caddy-coraza-crowdsec-bouncer')
    source = Path(__file__).resolve().parents[1].joinpath('Containerfile').read_text()
    # Fetch all upstream results before creating alerts; API failures fail the job.
    findings = []
    for repo, (name, pattern) in COMPONENTS.items():
        match = re.search(pattern, source)
        if not match:
            raise ValueError(f'Cannot find pinned version for {name}')
        current = match.group(1)
        releases = candidates(current, list(pages(f'repos/{repo}/releases')))
        print(f'{name}: pinned {current}; newer stable majors: {[r["tag_name"] for r in releases]}')
        findings.extend((repo, name, current, release) for release in releases)
    if not args.create_issues or not findings:
        return
    issues = list(pages(f'repos/{target}/issues?state=all'))
    for repo, name, current, release in findings:
        key = marker(repo, release)
        if already_reported(issues, key):
            continue
        body = (f'{key}\n\nUne nouvelle version majeure stable de **{name}** est disponible.\n\n'
                f'- Version épinglée : `{current}`\n'
                f'- Nouvelle version : [{release["tag_name"]}]({release["html_url"]})\n\n'
                'Migration à examiner :\n'
                '- [ ] Lire les changements incompatibles et vérifier les chemins des modules Go.\n'
                '- [ ] Vérifier la compatibilité Caddy / Coraza / bouncer CrowdSec.\n'
                '- [ ] Préparer une PR avec les nouvelles versions.\n'
                '- [ ] Faire réussir le contrôle obligatoire `WAF compatibility`.\n\n'
                'Cette alerte ne modifie aucune dépendance et ne déploie aucune image. '
                'Fermer cette issue acquitte cette version majeure : elle ne sera pas recréée.')
        issue = api(f'repos/{target}/issues', {'title': f'Migration à examiner : {name} {version(release["tag_name"])[0]}.x', 'body': body})
        issues.append(issue)
        print('Created:', issue['html_url'])


if __name__ == '__main__':
    main()
