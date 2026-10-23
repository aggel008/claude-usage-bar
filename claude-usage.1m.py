#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# <xbar.title>Claude Usage</xbar.title>
# <xbar.version>v3.0</xbar.version>
# <xbar.author>aggel008</xbar.author>
# <xbar.author.github>aggel008</xbar.author.github>
# <xbar.desc>Live Claude.ai session (5h) and weekly usage in your menu bar — no API keys, reads directly from your browser</xbar.desc>
# <xbar.image>https://raw.githubusercontent.com/aggel008/claude-usage-bar/main/screenshot.png</xbar.image>
# <xbar.dependencies>python3</xbar.dependencies>
# <xbar.abouturl>https://github.com/aggel008/claude-usage-bar</xbar.abouturl>
# <swiftbar.title>Claude Usage</swiftbar.title>
# <swiftbar.version>3.0</swiftbar.version>
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
CACHE  = os.path.expanduser('~/.claude-usage-cache.json')
MAX_STALE = 6 * 3600          # show cached numbers for up to 6h when a fetch fails

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

def load_cache():
    """{account_uuid: {ts, email, data}}. Caches from single-account versions are ignored."""
    try:
        with open(CACHE) as f:
            c = json.load(f)
        return c.get('accounts', {}) if isinstance(c, dict) else {}
    except Exception:
        return {}

def save_cache(accounts):
    try:
        with open(CACHE, 'w') as f:
            json.dump({'accounts': accounts}, f)
    except Exception:
        pass

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

# Runs inside each claude.ai tab. A tab carries the cookies of its browser
# profile, so tabs in different profiles (or browsers) answer for different
# accounts.
#
# The tab remembers which account and org it belongs to in a page global, so
# /api/bootstrap is only fetched when that is missing (first run, page
# reload), when claude.ai's active org changed, or when /usage fails.
# The org is the one claude.ai has active (lastActiveOrg cookie), else the
# first that can chat: memberships[0] is often an API (Console) org.
#
# SEEN, prepended by the AppleScript, lists the account uuids already read
# this run so further tabs of the same account skip the usage call.
# Returns "OK\t<uuid>\t<json>", "SEEN" or "ERR\t<status>\t<detail>".
TAB_JS = r"""(function(){
function g(p){var x=new XMLHttpRequest();x.open('GET',p,false);
x.setRequestHeader('Accept','application/json');x.send();return x;}
var c=(document.cookie.match(/(?:^|; )lastActiveOrg=([^;]+)/)||[])[1]||'';
function who(){
  var b=g('/api/bootstrap');
  if(b.status!=200)return 'HTTP\t'+b.status;
  var a=JSON.parse(b.responseText).account;
  if(!a||!a.uuid)return 'HTTP\t401';
  var ms=(a.memberships||[]).map(function(m){return m.organization;});
  var o=ms.filter(function(o){return o.uuid==c;})[0]
    ||ms.filter(function(o){return (o.capabilities||[]).indexOf('chat')>=0;})[0]
    ||ms[0];
  if(!o)return 'NO_ORG\t'+a.email_address;
  window.__claudeUsage={uuid:a.uuid,email:a.email_address,org:o.uuid,cookie:c};
  return null;
}
var k=window.__claudeUsage,fresh=false,e;
if(!k||k.cookie!=c){e=who();if(e)return 'ERR\t'+e;k=window.__claudeUsage;fresh=true;}
if(SEEN.indexOf(k.uuid)>=0)return 'SEEN';
var u=g('/api/organizations/'+k.org+'/usage');
if(u.status!=200&&!fresh){e=who();if(e)return 'ERR\t'+e;k=window.__claudeUsage;
  u=g('/api/organizations/'+k.org+'/usage');}
if(u.status!=200)return 'ERR\tHTTP\t'+u.status;
return 'OK\t'+k.uuid+'\t'+JSON.stringify({email:k.email,data:JSON.parse(u.responseText)});
})()"""

def run_all_tabs(app, engine):
    """Run TAB_JS in every claude.ai tab of one browser, across all windows.

    Returns (status, lines). status in OK / NO_TAB / JS_DISABLED / NO_AUTOMATION / ERROR.
    """
    exec_line = ('set r to (do JavaScript js in t) as text' if engine == 'safari'
                 else 'set r to (execute t javascript js) as text')
    script = f'''set body to {as_str(TAB_JS)}
tell application {as_str(app)}
	set out to ""
	set seen to ""
	set found to false
	repeat with w in windows
		try
			set ts to tabs of w
		on error
			set ts to {{}}
		end try
		repeat with t in ts
			set u to ""
			try
				set u to URL of t
			end try
			if u contains "claude.ai" then
				set found to true
				set js to "var SEEN='" & seen & "';" & body
				try
					{exec_line}
				on error msg
					set r to "ASERR" & tab & msg
				end try
				if r starts with "OK" then set seen to seen & (text 4 thru 39 of r) & ","
				set out to out & r & linefeed
			end if
		end repeat
	end repeat
	if not found then return "__NO_TAB__"
	return out
end tell'''
    try:
        r = osa(script, timeout=25)
    except subprocess.TimeoutExpired:
        return 'ERROR', [f'{app} timed out']
    if r.returncode != 0:
        return classify(r.stderr), [r.stderr.strip()]
    out = r.stdout.strip()
    if out == '__NO_TAB__':
        return 'NO_TAB', []
    return 'OK', [l for l in out.split('\n') if l]

def fetch_accounts():
    """Read every signed-in account from every running browser.

    Returns ({uuid: {email, data}}, Fetch or None). The Fetch is the most
    actionable problem seen, even when other tabs succeeded.
    """
    accounts = {}
    problems = []   # (rank, browser, status, detail)
    RANK = {'JS_DISABLED': 0, 'NO_AUTOMATION': 1, 'HTTP': 2, 'ERROR': 2, 'NO_TAB': 3}

    for app, engine in BROWSERS:
        if not app_installed(app) or not app_running(app):
            continue
        status, lines = run_all_tabs(app, engine)
        if status != 'OK':
            problems.append((RANK.get(status, 2), app, status, lines[0] if lines else None))
            continue
        for line in lines:
            kind, _, rest = line.partition('\t')
            if kind == 'OK':
                uuid, _, body = rest.partition('\t')
                try:
                    accounts.setdefault(uuid, json.loads(body))
                except Exception:
                    problems.append((2, app, 'BADJSON', body[:60]))
            elif kind == 'ERR':
                st, _, detail = rest.partition('\t')
                problems.append((RANK.get(st, 2), app, st, detail))
            elif kind == 'ASERR':
                st = classify(rest)
                problems.append((RANK.get(st, 2), app, st, rest))

    if problems:
        problems.sort(key=lambda p: p[0])
        _, app, status, detail = problems[0]
        return accounts, Fetch(status, detail, app)
    if not accounts:
        return accounts, Fetch('NO_BROWSER', 'No browser with claude.ai is running')
    return accounts, None

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

def fmt_age(sec):
    m = int(sec // 60)
    return f'{m}m' if m < 60 else f'{m // 60}h {m % 60}m'

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
cfg = load_config()

def _flag(key, default):
    return cfg.get(key, default).strip().lower()

# Menu bar preferences. Defaults reproduce the long-standing behaviour;
# set these in ~/.claude-usage.conf to change it.
MENUBAR       = _flag('MENUBAR', 'session')       # session / weekly / both
MENUBAR_COLOR = _flag('MENUBAR_COLOR', 'true') not in ('false', '0', 'no', 'off')

def label(acc):
    """Optional short tag per account, from LABEL.<email>=<tag>."""
    return cfg.get(f'LABEL.{acc.get("email", "")}', '')

cache = load_cache()
now   = time.time()

try:
    live, err = fetch_accounts()
except Exception as e:
    live, err = {}, Fetch('ERROR', str(e))

for uuid, acc in live.items():
    cache[uuid] = dict(acc, ts=now)
# An account whose tab is gone keeps showing its last reading, up to MAX_STALE.
cache = {u: a for u, a in cache.items() if now - a.get('ts', 0) <= MAX_STALE}
save_cache(cache)

# Sorted so the menu bar figures keep their places between refreshes.
accounts = sorted(cache.items(), key=lambda kv: kv[1].get('email', ''))
multi    = len(accounts) > 1

if not accounts:
    print('✦' if err and err.status in ('NO_TAB', 'NO_BROWSER') else '✦ !')
    print('---')
    for line in remedy(err):
        print(f'{line} | color={RED if line.startswith(("JavaScript", "SwiftBar", "claude.ai")) else DIM} font=Menlo size=11')
    print('---')
    print(f'Open claude.ai | href=https://claude.ai/new color={BLUE}')
    print(f'Refresh | refresh=true color={BLUE}')
    sys.exit(0)

def limits(acc):
    d = acc['data']
    return ((d.get('five_hour') or {}).get('utilization'),
            (d.get('five_hour') or {}).get('resets_at'),
            (d.get('seven_day') or {}).get('utilization'),
            (d.get('seven_day') or {}).get('resets_at'))

# ── menu bar icon ─────────────────────────────────────────────────────────────
# One account:  "✦ 42%", MENUBAR=weekly "✦ 18%", MENUBAR=both "✦ 42% · 18%".
# Several: one figure per account joined by " · " ("42%/18%" each with both),
# prefixed by its LABEL if set. The colour follows the tightest limit shown.
# MENUBAR_COLOR=false leaves the title uncoloured so it follows the system
# menu bar colour. Never use "|" here, SwiftBar treats it as the delimiter.
heads, worst = [], 0
for uuid, acc in accounts:
    s_pct, s_reset, w_pct, _ = limits(acc)
    s_head = f'↺ {until(s_reset)}' if session_exhausted(s_pct) and s_reset else pct_str(s_pct)
    if MENUBAR == 'both':
        head  = f'{s_head}{"/" if multi else " · "}{pct_str(w_pct)}'
        if s_pct is None and w_pct is None: head = ''
        worst = max(worst, rank(s_pct), rank(w_pct))
    elif MENUBAR == 'weekly':
        head  = pct_str(w_pct) if w_pct is not None else ''
        worst = max(worst, rank(w_pct))
    else:
        head  = s_head if s_pct is not None else ''
        worst = max(worst, rank(s_pct))
    if multi:
        head = ' '.join(p for p in (label(acc), head or '?') if p)
    heads.append(head)

title = ' '.join(p for p in ('✦', ' · '.join(h for h in heads if h)) if p)

if not MENUBAR_COLOR:
    print(title)
elif not live:
    print(f'{title} | color={DIM}')
elif worst == 2:
    print(f'{title} | color={RED}')
elif worst == 1:
    print(f'{title} | color={YELLOW}')
else:
    print(title)

print('---')

if err is not None and any(uuid not in live for uuid, _ in accounts):
    if not multi:
        print(f'Stale — {fmt_age(now - accounts[0][1]["ts"])} old | color={YELLOW} font=Menlo size=11')
    for line in remedy(err):
        print(f'{line} | color={DIM} font=Menlo size=11')
    print('---')

for uuid, acc in accounts:
    s_pct, s_reset, w_pct, w_reset = limits(acc)

    if multi:
        tag = label(acc)
        print(f'{tag + "  " if tag else ""}{acc.get("email", "?")} | color={TEXT} font=Menlo size=12')
        if uuid not in live:
            print(f'Stale — {fmt_age(now - acc["ts"])} old | color={YELLOW} font=Menlo size=11')

    # ── session ───────────────────────────────────────────────────────────────
    s_bar, s_color = bar(s_pct)
    s_str  = '' if session_exhausted(s_pct) else (f'{int(s_pct)}%' if s_pct is not None else '?')
    s_time = f'↺ {until(s_reset)}' if s_reset else ''
    print(f'{join_fields("SESSION", s_str, s_time)} | color={TEXT} font=Menlo size=11')
    print(f'{s_bar} | color={s_color} font=Menlo size=10')

    if not multi:
        print('---')

    # ── weekly ────────────────────────────────────────────────────────────────
    w_bar, w_color = bar(w_pct)
    w_str  = f'{int(w_pct)}%' if w_pct is not None else '?'
    w_time = f'↺ {until(w_reset)}' if w_reset else ''
    print(f'WEEKLY   {w_str}   {w_time} | color={TEXT} font=Menlo size=11')
    print(f'{w_bar} | color={w_color} font=Menlo size=10')

    print('---')

print(f'Open claude.ai | href=https://claude.ai/new color={BLUE}')
print(f'Refresh | refresh=true color={BLUE}')
