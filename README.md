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
| `MENUBAR` | `session`, `both` | `session` | `both` also shows the weekly figure: `✦ 42% · 18%` |
| `MENUBAR_COLOR` | `true`, `false` | `true` | `false` leaves the menu bar text uncolored so it follows the system menu bar color |

```
MENUBAR=both
MENUBAR_COLOR=false
```

With `MENUBAR=both`, the color reflects whichever limit is tightest, so a
weekly squeeze is visible even when the session window is fresh.

The file also caches `ORG_ID` after the first run. The dropdown is unaffected
by these settings.

---

## How it works

SwiftBar runs the script every minute. The script uses AppleScript to execute a `XMLHttpRequest` inside your open claude.ai browser tab — calling Anthropic's internal `/api/organizations/{id}/usage` endpoint with your existing session. The response is parsed and displayed.

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
