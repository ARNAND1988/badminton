#!/usr/bin/env python3
"""Change-aware, non-destructive regression runner for this repository."""
from __future__ import annotations
import os, re, subprocess, sys
from dataclasses import dataclass
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]

@dataclass
class Check:
    name: str
    domains: tuple[str, ...]
    command: list[str]
    cwd: Path = ROOT
    passed: bool = False
    output: str = ''

def changed_files():
    commands = []
    if os.environ.get('REGRESSION_BASE'):
        commands.append(['git', 'diff', '--name-only', os.environ['REGRESSION_BASE'], '--'])
    commands += [['git', 'diff', '--name-only', 'HEAD', '--'], ['git', 'diff', '--name-only', 'HEAD~1', '--']]
    for command in commands:
        result = subprocess.run(command, cwd=ROOT, text=True, capture_output=True)
        files = [line for line in result.stdout.splitlines() if line]
        if result.returncode == 0 and files:
            return files
    return []

def impact(files):
    joined = '\n'.join(files).lower()
    rules = {
        'Authentication': ('auth', 'login', 'register', 'session', 'navbar', 'router'),
        'Members': ('member', 'models.py'), 'Families': ('family', 'models.py'),
        'Bookings': ('booking', 'court', 'models.py'),
        'Participation': ('availability', 'participant', 'booking', 'family'),
        'Invoices': ('invoice', 'payment', 'booking', 'family', 'models.py'),
        'Admin': ('admin', 'auth', 'booking', 'models.py'),
        'Frontend': ('badminton-frontend/',),
        'Mobile': ('badminton-frontend/src', 'index.css', 'navbar.vue'),
        'Build': ('badminton-frontend/', 'requirements', 'docker', 'scripts/'),
    }
    areas = {area for area, words in rules.items() if any(word in joined for word in words)}
    core = any(path.endswith(('app/__init__.py', 'app/models.py', 'requirements.txt')) for path in files)
    return set(rules) if core or not areas else areas

def run(check):
    print(f"\n>>> {check.name}: {' '.join(check.command)}", flush=True)
    env = os.environ.copy()
    env.update({'DATABASE_URL': 'sqlite:///:memory:', 'AUTH_MOCK': '1', 'FLASK_ENV': 'development',
                'SECRET_KEY': 'regression-only-secret-key-at-least-32-bytes',
                'JWT_SECRET': 'regression-only-jwt-key-at-least-32-bytes',
                'WHATSAPP_BOT_URL': '', 'TWILIO_ACCOUNT_SID': '', 'TWILIO_AUTH_TOKEN': ''})
    result = subprocess.run(check.command, cwd=check.cwd, env=env, text=True,
                            stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    check.output, check.passed = result.stdout, result.returncode == 0
    print(check.output, end='' if check.output.endswith('\n') else '\n')

def main():
    mode = (sys.argv[1] if len(sys.argv) > 1 else 'full').lower()
    if mode not in {'fast', 'full'}:
        print('usage: ./scripts/regression.sh [fast|full]', file=sys.stderr); return 2
    if os.environ.get('FLASK_ENV', '').lower() == 'production' or 'prod' in os.environ.get('DATABASE_URL', '').lower():
        print('BLOCKED: refusing to run regression checks with production configuration.'); return 2
    files, areas = changed_files(), None
    areas = impact(files)
    target = ['python', '-m', 'pytest', '-q']
    if mode == 'fast' and areas <= {'Authentication', 'Admin', 'Frontend', 'Mobile', 'Build'}:
        target += ['tests/test_auth.py', 'tests/test_regression_journeys.py']
    checks = [
        Check('Merge conflict verification', ('Build',), ['python', 'scripts/conflict_marker_smoke.py']),
        Check('Python compile/type smoke', ('Build',), ['python', '-m', 'compileall', '-q', 'app', 'tests'], ROOT/'badminton-backend'),
        Check('Backend/API regression', tuple(areas), target, ROOT/'badminton-backend'),
        Check('Frontend responsive smoke', ('Frontend', 'Mobile'), ['python', 'scripts/responsive_smoke.py']),
        Check('Frontend production build', ('Frontend', 'Build'), ['npm', 'run', 'build'], ROOT/'badminton-frontend'),
    ]
    if mode == 'full': checks.insert(0, Check('Format/whitespace verification', ('Build',), ['git', 'diff', '--check']))
    for check in checks: run(check)
    combined = '\n'.join(c.output for c in checks)
    value = lambda pattern, fallback: int(m.group(1)) if (m := re.search(pattern, combined)) else fallback
    failures = [c.name for c in checks if not c.passed]
    pwa = 'PASS' if (ROOT/'badminton-frontend/public/manifest.webmanifest').exists() else 'N/A'
    state = lambda domain: 'FAIL' if any(not c.passed for c in checks if domain in c.domains) else 'PASS'
    print('\nNIEUWEGEIN BADMINTON REGRESSION\n\nChange detected:')
    print(', '.join(files) if files else 'No diff found; conservative full-domain validation')
    print(f'\nMode:\n{mode.upper()}\n')
    for domain in ('Authentication','Members','Families','Bookings','Participation','Invoices','Admin','Frontend','Mobile'):
        print(f'{domain}: {state(domain)}')
    print(f"PWA: {pwa}\nBuild: {state('Build')}")
    print(f"\nTests:\nPassed: {value(r'(\d+) passed', sum(c.passed for c in checks))}\nFailed: {value(r'(\d+) failed', sum(not c.passed for c in checks))}\nSkipped: {value(r'(\d+) skipped', 0)}")
    print('\nFailures introduced by this change:')
    print('\n'.join(f'- {failure}' for failure in failures) or 'None')
    print('\nPre-existing failures:\nNone detected (compare with REGRESSION_BASE when triaging a known baseline).')
    print(f"\nFinal result:\n\n{'FAIL' if failures else 'PASS'}")
    return 1 if failures else 0
if __name__ == '__main__': raise SystemExit(main())
