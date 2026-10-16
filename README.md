# aiusage

Prints how much of each AI coding subscription is left, and when it resets. Claude Code, Codex and OpenCode Go on one screen.

I got tired of checking three dashboards before starting a long agent run, so this reads the same local credentials and endpoints the CLIs use and puts the result in one place.

```
$ aiusage
aiusage v0.2.0 · Fri 16 Oct 16:05 UTC · 21:35 IST

Claude (pro) · oauth usage endpoint
  session   █████████░  90%  in 15m (16:20 UTC)  ⚠ critical
  weekly    ███░░░░░░░  31%  in 2d 2h (Sun 18 Oct)

Codex (plus) · live · codex app-server
  5h        ████████░░  85%  in 1h 52m (16:57 UTC)
  weekly    ███░░░░░░░  29%  in 6d 16h (Thu 22 Oct)

OpenCode Go · zen/go/v1/usage
  rolling   █░░░░░░░░░   6%  in 6m (13:07 UTC)
  weekly    ██████░░░░  63%  in 2d 8h (Mon 19 Oct)
  monthly   ███░░░░░░░  32%  in 10d 13h (Tue 27 Oct)

Plans
  Claude Pro               renews in 8d (24 Oct)
```

## Commands

| command | output |
|---|---|
| `aiusage` | all three providers, pretty |
| `aiusage claude` / `codex` / `opencode` | one provider |
| `aiusage plans` | renewal countdowns only |
| `aiusage --json` | machine readable, exit 1 if any provider errored |
| `aiusage -v` | extras plus the `ccusage` token and cost table |

Colours switch off when the output is piped; force with `--no-color`, or set `NO_COLOR`.

## Where the numbers come from

| provider | source | freshness |
|---|---|---|
| Claude Code | `~/.claude/.credentials.json`, then `api.anthropic.com/api/oauth/usage` (the same data as `/usage`) | live |
| Codex | `codex app-server` JSON-RPC `account/rateLimits/read`, falling back to the newest `rate_limits` snapshot in `$CODEX_HOME/sessions` | live, about 2s |
| OpenCode Go | key from `~/.local/share/opencode/opencode.db`, then `opencode.ai/zen/go/v1/usage` | live |

Nothing is uploaded anywhere. The only network calls are to those provider endpoints, with the credentials already on the machine.

## Install

Needs Python 3.11 or newer (for `tomllib`), and any of the CLIs you want a section for must be logged in.

```sh
git clone https://github.com/Ranjit2111/aiusage.git ~/repos/aiusage
chmod +x ~/repos/aiusage/aiusage
mkdir -p ~/.local/bin ~/.config/aiusage
ln -sf ~/repos/aiusage/aiusage ~/.local/bin/aiusage
cp ~/repos/aiusage/config.example.toml ~/.config/aiusage/config.toml   # then set renew_day per plan
```

`~/.local/bin` has to be on `PATH`. `git pull` updates in place, the symlink keeps working.

## Tests

```sh
python3 tests/test_parsers.py
```

The parsers are the fragile part, so those are what the tests cover, using recorded provider responses.

## Caveats

- The Anthropic usage endpoint and the OpenCode usage endpoint are undocumented. They are the ones the CLIs and console call, so they can change without notice. When one does, only that section errors out and the rest still print.
- Claude access tokens expire hourly. aiusage refreshes the token itself and writes the rotated credentials back to `~/.claude/.credentials.json`, the same file Claude Code uses, so both stay valid. If a refresh is rejected, run `claude` once to log in again.
- `aiusage plans` reads `~/.config/aiusage/config.toml`. `renew_day` is the day of the month the plan renews, and 0 means unset.
- The OpenCode section reports the Go plan of the account logged into the console on that machine.
- Tested on Linux. It relies on the Unix `select` call, which macOS also has.
