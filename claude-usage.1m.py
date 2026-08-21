#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# <xbar.title>Claude Usage</xbar.title>
# <xbar.version>v2.4</xbar.version>
# <xbar.author>aggel008</xbar.author>
# <xbar.author.github>aggel008</xbar.author.github>
# <xbar.desc>Live Claude.ai session (5h) and weekly usage in your menu bar — no API keys, reads directly from your browser</xbar.desc>
# <xbar.image>https://raw.githubusercontent.com/aggel008/claude-usage-bar/main/screenshot.png</xbar.image>
# <xbar.dependencies>python3</xbar.dependencies>
# <xbar.abouturl>https://github.com/aggel008/claude-usage-bar</xbar.abouturl>
# <swiftbar.title>Claude Usage</swiftbar.title>
# <swiftbar.version>2.4</swiftbar.version>
# <swiftbar.author>aggel008</swiftbar.author>
# <swiftbar.author.github>aggel008</swiftbar.author.github>
# <swiftbar.desc>Live Claude.ai session (5h) and weekly usage in your menu bar — no API keys, reads directly from your browser</swiftbar.desc>
# <swiftbar.image>https://raw.githubusercontent.com/aggel008/claude-usage-bar/main/screenshot.png</swiftbar.image>
# <swiftbar.dependencies>python3</swiftbar.dependencies>
# <swiftbar.refreshTime>1</swiftbar.refreshTime>
# <swiftbar.hideAbout>true</swiftbar.hideAbout>
# <swiftbar.hideRunInTerminal>true</swiftbar.hideRunInTerminal>
# <swiftbar.hideLastUpdated>true</swiftbar.hideLastUpdated>
# <swiftbar.hideDisablePlugin>true</swiftbar.hideDisablePlugin>

import json, subprocess, sys, os, time
from datetime import datetime, timezone

CONFIG = os.path.expanduser('~/.claude-usage.conf')

# ── appearance ────────────────────────────────────────────────────────────────
# SwiftBar renders "light,dark" colour pairs and swaps them the instant the
# system appearance changes. xbar and a plain terminal don't, so there we
# resolve the pair ourselves against the current appearance.
_SWIFTBAR = bool(os.environ.get('SWIFTBAR'))

def _dark_mode():
    try:
        r = subprocess.run(['defaults', 'read', '-g', 'AppleInterfaceStyle'],
                           capture_output=True, text=True, timeout=3)
        return r.returncode == 0 and 'dark' in r.stdout.lower()
    except Exception:
        return True   # assume dark: light text on a dark bar is the safer miss

_DARK = None if _SWIFTBAR else _dark_mode()

def pair(light, dark):
    return f'{light},{dark}' if _SWIFTBAR else (dark if _DARK else light)

#             light mode   dark mode
TEXT   = pair('#1C1C1E',  '#E8E8E8')
DIM    = pair('#6E6E73',  '#9A9A9E')
BLUE   = pair('#0B5FD0',  '#5C8EFF')
RED    = pair('#C5221F',  '#FF5555')
YELLOW = pair('#A66300',  '#F5A623')

# name, engine, where the .app lives
BROWSERS = [
    ('Google Chrome',  'chromium'),
    ('Chromium',       'chromium'),
    ('Brave Browser',  'chromium'),
    ('Microsoft Edge', 'chromium'),
    ('Comet',          'chromium'),
    ('Arc',            'chromium'),
    ('Safari',         'safari'),
]

# ── config / cache ────────────────────────────────────────────────────────────
def load_config():
    cfg = {}
    if not os.path.exists(CONFIG):
        return cfg
    with open(CONFIG) as f:
        for line in f:
            line = line.strip()
            if '=' in line and not line.startswith('#'):
                k, v = line.split('=', 1)
                cfg[k.strip()] = v.strip()
    return cfg

def save_org(org_id):
    cfg = load_config()
    cfg['ORG_ID'] = org_id
    with open(CONFIG, 'w') as f:
        for k, v in cfg.items():
            f.write(f'{k}={v}\n')

# ── browser plumbing ──────────────────────────────────────────────────────────
def as_str(s):
    """Quote a Python string as an AppleScript string literal."""
    return '"' + s.replace('\\', '\\\\').replace('"', '\\"') + '"'

def osa(script, timeout=12):
    return subprocess.run(['osascript', '-e', script],
                          capture_output=True, text=True, timeout=timeout)

def app_installed(name):
    for base in ('/Applications', os.path.expanduser('~/Applications')):
        if os.path.isdir(os.path.join(base, name + '.app')):
            return True
    return False

def app_running(name):
    """Ask without launching the app."""
    try:
        r = osa(f'application {as_str(name)} is running', timeout=5)
        return r.returncode == 0 and r.stdout.strip() == 'true'
    except Exception:
        return False

def classify(stderr):
    """Map an osascript failure to a cause we can give a fix for.

    Wording differs per browser, so match on concepts rather than one
    vendor's sentence. Authorisation is checked first: those messages
    mention Apple events but never JavaScript.
    """
    s = stderr.lower()
    if 'not authorized to send apple events' in s or '-1743' in s:
        return 'NO_AUTOMATION'
    if 'javascript' in s and ('apple event' in s or 'appleevent' in s
                             or 'applescript' in s):
        return 'JS_DISABLED'
    if "isn't running" in s or 'is not running' in s:
        return 'NOT_RUNNING'
    return 'ERROR'

def run_js(app, engine, js):
    """Return (status, payload). status in OK / NO_TAB / JS_DISABLED / NO_AUTOMATION / ERROR."""
    lit = as_str(js)
    exec_line = (f'return (do JavaScript {lit} in theTab) as text' if engine == 'safari'
                 else f'return (execute theTab javascript {lit}) as text')
    script = f'''tell application {as_str(app)}
	set theTab to missing value
	repeat with w in windows
		try
			repeat with t in tabs of w
				if URL of t contains "claude.ai" then
					set theTab to t
					exit repeat
				end if
			end repeat
		end try
		if theTab is not missing value then exit repeat
	end repeat
	if theTab is missing value then return "__NO_TAB__"
	{exec_line}
end tell'''
    try:
        r = osa(script)
    except subprocess.TimeoutExpired:
        return 'ERROR', f'{app} timed out'
    if r.returncode != 0:
        return classify(r.stderr), r.stderr.strip()
    out = r.stdout.strip()
    if out == '__NO_TAB__':
        return 'NO_TAB', None
    return 'OK', out

def xhr(path):
    """Fetch a claude.ai API path from an open tab. Raises Fetch with a diagnosis."""
    js = ("var x=new XMLHttpRequest();"
          f"x.open('GET','{path}',false);"
          "x.setRequestHeader('Accept','application/json');"
          "x.send();"
          "x.status+'|||'+x.responseText")

    problems = []   # (rank, browser, status, detail)
    RANK = {'JS_DISABLED': 0, 'NO_AUTOMATION': 1, 'ERROR': 2, 'NO_TAB': 3}

    for app, engine in BROWSERS:
        if not app_installed(app) or not app_running(app):
            continue
        status, payload = run_js(app, engine, js)
        if status == 'OK':
            code, _, body = payload.partition('|||')
            code = code.strip()
            if code != '200':
                problems.append((2, app, 'HTTP', code))
                continue
            try:
                return json.loads(body)
            except Exception:
                problems.append((2, app, 'BADJSON', body[:60]))
                continue
        problems.append((RANK.get(status, 2), app, status, payload))

    if not problems:
        raise Fetch('NO_BROWSER', 'No browser with claude.ai is running')
    problems.sort(key=lambda p: p[0])
    _, app, status, detail = problems[0]
    raise Fetch(status, detail, app)

class Fetch(Exception):
    def __init__(self, status, detail=None, app=None):
        super().__init__(status)
        self.status, self.detail, self.app = status, detail, app

# ── formatting ────────────────────────────────────────────────────────────────
def until(iso):
    try:
        dt = datetime.fromisoformat(iso.replace('Z', '+00:00'))
        s  = int((dt - datetime.now(timezone.utc)).total_seconds())
        if s <= 0: return 'soon'
        h, m = s // 3600, (s % 3600) // 60
        return f'{h}h {m}m' if h else f'{m}m'
    except Exception:
        return '?'

def bar(pct, width=22):
    if pct is None:
        return '░' * width, DIM
    n = round(width * max(0, min(100, pct)) / 100)
    color = BLUE
    if pct >= 90: color = RED
    elif pct >= 70: color = YELLOW
    return '█' * n + '░' * (width - n), color

def session_exhausted(pct):
    return pct is not None and pct >= 100

def join_fields(*parts):
    return '   '.join(p for p in parts if p)

def pct_str(p):
    return f'{int(p)}%' if p is not None else '?'

def rank(p):
    """Severity of a utilisation figure: 0 normal, 1 warn (>=70), 2 critical (>=90)."""
    if p is None: return 0
    if p >= 90:   return 2
    if p >= 70:   return 1
    return 0

def remedy(err):
    app = err.app or 'your browser'
    if err.status == 'JS_DISABLED':
        if app == 'Safari':
            return ["JavaScript from Apple Events is off",
                    f'Safari ▸ Settings ▸ Advanced ▸ "Show features for web developers"',
                    'then Develop ▸ Allow JavaScript from Apple Events']
        return ["JavaScript from Apple Events is off",
                f'Fix: {app} menu ▸ View ▸ Developer ▸',
                'Allow JavaScript from Apple Events']
    if err.status == 'NO_AUTOMATION':
        return ['SwiftBar is not allowed to control ' + app,
                'Fix: System Settings ▸ Privacy & Security ▸',
                'Automation ▸ SwiftBar ▸ enable ' + app]
    if err.status == 'NO_TAB':
        return [f'{app} is running but has no claude.ai tab']
    if err.status == 'NO_BROWSER':
        return ['Open claude.ai in Chrome, Brave, Edge, Comet, or Safari']
    if err.status == 'HTTP':
        if err.detail == '401' or err.detail == '403':
            return [f'claude.ai returned {err.detail} — sign in again']
        return [f'claude.ai returned HTTP {err.detail}']
    return [f'{err.status}: {str(err.detail)[:70]}']

# ── main ──────────────────────────────────────────────────────────────────────
cfg     = load_config()
org_id  = cfg.get('ORG_ID')
err     = None

try:
    if not org_id:
        boot   = xhr('/api/bootstrap')
        org_id = boot['account']['memberships'][0]['organization']['uuid']
        save_org(org_id)
    data = xhr(f'/api/organizations/{org_id}/usage')
except Fetch as e:
    err, data = e, None
except Exception as e:
    err, data = Fetch('ERROR', str(e)), None

if data is None:
    print('✦' if err and err.status in ('NO_TAB', 'NO_BROWSER') else '✦ !')
    print('---')
    for line in remedy(err):
        print(f'{line} | color={RED if line.startswith(("JavaScript", "SwiftBar", "claude.ai")) else DIM} font=Menlo size=11')
    print('---')
    print(f'Open claude.ai | href=https://claude.ai/new color={BLUE}')
    print(f'Refresh | refresh=true color={BLUE}')
    sys.exit(0)

s_pct   = data.get('five_hour', {}).get('utilization')
s_reset = data.get('five_hour', {}).get('resets_at')
w_pct   = data.get('seven_day', {}).get('utilization')
w_reset = data.get('seven_day', {}).get('resets_at')

# ── menu bar icon ─────────────────────────────────────────────────────────
s_head = f'↺ {until(s_reset)}' if session_exhausted(s_pct) and s_reset else pct_str(s_pct)
title  = '✦' if s_pct is None else f'✦ {s_head}'
worst  = rank(s_pct)

if worst == 2:
    print(f'{title} | color={RED}')
elif worst == 1:
    print(f'{title} | color={YELLOW}')
else:
    print(title)

print('---')

# ── session ───────────────────────────────────────────────────────────────────
s_bar, s_color = bar(s_pct)
s_str  = '' if session_exhausted(s_pct) else (f'{int(s_pct)}%' if s_pct is not None else '?')
s_time = f'↺ {until(s_reset)}' if s_reset else ''
print(f'{join_fields("SESSION", s_str, s_time)} | color={TEXT} font=Menlo size=11')
print(f'{s_bar} | color={s_color} font=Menlo size=10')

print('---')

# ── weekly ────────────────────────────────────────────────────────────────────
w_bar, w_color = bar(w_pct)
w_str  = f'{int(w_pct)}%' if w_pct is not None else '?'
w_time = f'↺ {until(w_reset)}' if w_reset else ''
print(f'WEEKLY   {w_str}   {w_time} | color={TEXT} font=Menlo size=11')
print(f'{w_bar} | color={w_color} font=Menlo size=10')

print('---')
print(f'Open claude.ai | href=https://claude.ai/new color={BLUE}')
print(f'Refresh | refresh=true color={BLUE}')
