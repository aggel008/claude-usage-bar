# Claude Usage Bar

A [SwiftBar](https://swiftbar.app) plugin that shows your **Claude.ai usage in the macOS menu bar** — session (5-hour window) and weekly limits, live.

No API keys. No tokens. Reads directly from your already-logged-in browser.

Also available in the official [xbar-plugins](https://github.com/matryer/xbar-plugins) collection.

![screenshot](screenshot.png)

---

## What it shows

- **Menu bar**: current session usage % (color-coded: blue → yellow at 70% → red at 90%)
- **Dropdown**: session progress bar + time until reset
- **Dropdown**: weekly progress bar + time until reset

Colors adapt to light and dark appearance. The menu bar item is
[configurable](#configuration).

**Several accounts** are shown side by side — see
[Multiple accounts](#multiple-accounts).

---

## Requirements

- macOS
- [SwiftBar](https://swiftbar.app) (free, open source)
- Python 3 (comes with macOS or install via `brew install python3`)
- Claude.ai open in one of: **Chrome, Brave, Edge, Chromium, Comet, or Safari**
- You must be logged in to claude.ai in that browser
- **"Allow JavaScript from Apple Events" enabled** in that browser (see step 4)

---

## Install

**1. Install SwiftBar** if you haven't:
```
brew install --cask swiftbar
```

**2. Download the plugin:**
```bash
curl -o ~/your-swiftbar-plugins-folder/claude-usage.1m.py \
  https://raw.githubusercontent.com/aggel008/claude-usage-bar/main/claude-usage.1m.py

chmod +x ~/your-swiftbar-plugins-folder/claude-usage.1m.py
```

Or just clone this repo and copy the `.py` file to your SwiftBar plugins folder.

**3. Make it executable:**
```bash
chmod +x claude-usage.1m.py
```

**4. Allow JavaScript from Apple Events.** This is off by default and the
plugin cannot read anything without it:

> **Chrome / Brave / Edge / Chromium / Comet** — menu bar ▸ **View** ▸
> **Developer** ▸ **Allow JavaScript from Apple Events**
>
> **Safari** — **Settings** ▸ **Advanced** ▸ enable **"Show features for web
> developers"**, then menu bar ▸ **Develop** ▸ **Allow JavaScript from Apple
> Events**

This is a one-time, per-browser setting. It lets AppleScript run JavaScript in
your tabs, which is how the plugin reads your usage without any API key.

**5. Open claude.ai** in that browser — and stay logged in.

**6. Click Refresh** in SwiftBar or wait up to 1 minute.

The first time it runs, macOS asks whether SwiftBar may control your browser.
Allow it, or the plugin gets no data.

---

## Configuration

Optional. Create `~/.claude-usage.conf` with `KEY=value` lines:

| Key | Values | Default | Effect |
|---|---|---|---|
| `MENUBAR` | `session`, `weekly`, `both` | `session` | Which limit the menu bar shows. `both`: `✦ 42% · 18%` |
| `MENUBAR_COLOR` | `true`, `false` | `true` | `false` leaves the menu bar text uncolored so it follows the system menu bar color |
| `LABEL.<email>` | any short text | — | Tag shown before that account's figure when several accounts are signed in |

```
MENUBAR=both
MENUBAR_COLOR=false
```

With `MENUBAR=both`, the color reflects whichever limit is tightest, so a
weekly squeeze is visible even when the session window is fresh.

The dropdown is unaffected by these settings.

---

## Multiple accounts

Signed in to more than one Claude account — say in two Chrome profiles, or
Chrome and Safari? Keep a claude.ai tab open for each and the plugin shows
them all: one figure per account in the menu bar, joined by `·` and sorted by
email, and a section per account in the dropdown.

```
✦ 42% · 7%          MENUBAR=session (default)
✦ 18% · 95%         MENUBAR=weekly
✦ 42%/18% · 7%/95%  MENUBAR=both
```

To tell them apart in the menu bar, give each a label:

```
LABEL.me@work.com=W
LABEL.me@home.com=P
```

which reads `✦ W 42% · P 7%`. Several tabs of the same account are counted
once. If an account's tab is closed, its last reading stays in the dropdown,
marked stale, for up to six hours.

With a single account everything looks exactly as before.

---

## How it works

SwiftBar runs the script every minute. The script uses AppleScript to execute a `XMLHttpRequest` inside each open claude.ai browser tab — calling Anthropic's internal `/api/organizations/{id}/usage` endpoint with that tab's existing session. Each tab answers for the account signed in to its browser profile. The response is parsed and displayed.

Which account and organization a tab belongs to is looked up once via `/api/bootstrap` and remembered in the page until it reloads, so a normal refresh costs one request per account. The organization is the one claude.ai has active, so the figures match claude.ai's own usage page even if you also belong to an API (Console) organization.

Your credentials never leave your machine. The script does not store session tokens.

---

## Privacy

- Runs entirely on your Mac
- No external backend
- No telemetry or analytics
- No API keys, cookies, or session tokens are sent to the author or any third party
- All requests are made locally from your machine using your own logged-in Claude session

---

## Supported browsers

| Browser | Supported |
|---|---|
| Google Chrome | ✓ |
| Brave Browser | ✓ |
| Microsoft Edge | ✓ |
| Chromium | ✓ |
| Comet | ✓ |
| Safari | ✓ |
| Firefox | ✗ (no AppleScript JS execution) |
| Arc | not tested |

---

## Troubleshooting

**`✦` or `✦ !` with no number** — click the icon; the dropdown names the exact
cause and its fix. The common ones:

- *JavaScript from Apple Events is off* — do step 4 above.
- *SwiftBar is not allowed to control &lt;browser&gt;* — System Settings ▸ Privacy
  & Security ▸ Automation ▸ SwiftBar ▸ enable your browser.
- *&lt;browser&gt; is running but has no claude.ai tab* — open one.
- *claude.ai returned 401* — sign in again.

**Numbers look dimmed** — the last fetch failed and you're seeing cached values.
The dropdown shows how old they are and why the refresh failed.

**Wrong Python path** — the shebang line uses `/usr/bin/env python3`. If `python3` is not on your `PATH`:
```bash
which python3
# then edit the first line of claude-usage.1m.py
```

**Permission denied** — run `chmod +x claude-usage.1m.py`

---

## License

MIT
