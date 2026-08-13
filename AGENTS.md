# CLAUDE.md

This file provides guidance to Agents when working with code in this repository.

## Commands

```sh
pixi run app                          # serve on 0.0.0.0:8000
pixi run app --host 127.0.0.1 --port 9000   # use this instead of hand-rolling uvicorn
pixi run test                         # full suite (the task lives in the dev feature)
pixi run -e dev pytest tests/test_whoami.py::test_name -q   # one test
DEV=TRUE pixi run app                 # autoreload on meme_games/**
DB_PATH=/tmp/x.db pixi run app        # defaults to data/data.db; data_dir is its parent
```

Startup takes ~10s before the port answers. Never run two servers against one
`DB_PATH`: each keeps lobbies in memory and `lobby_service.update()` writes each
member's cached `User` back to the users table, so the second process silently
reverts renames made by the first.

## Architecture

A **lobby** is a room of members that switches between games while keeping
everyone in place; a game is just a state object plus a view. Four registries
wire a game in, and a new game touches all of them:

| Registry | Where | Purpose |
|---|---|---|
| `register_game(name, state_cls, persist)` | `domain/lobby/lobby.py` | state class; `persist` stores it as JSON on the lobby row |
| `register_game_view(game, fn)` | `apps/shared/spectators.py` | how to re-render the board for one member |
| `register_game_page(game, name, url)` | `apps/shared/utils.py` | navbar entry + "switch game" target |
| `register_route(rt)` | `apps/shared/utils.py` | mounts an `APIRouter` |

`main.py` sorts each router so `/{lobby_id}` is matched last — otherwise
`GET /alias/vote` is read as a lobby named "vote" and creates one.

**Rendering is per-receiver.** `notify_all(lobby, fn)` calls `fn(member, lobby)`
for every connected member, so the same update renders differently per person —
this is what keeps a Who Am I player from seeing their own label. Push updates
land as htmx OOB swaps (`hx_swap_oob`) or, for high-frequency board moves, as
JSON handled in JS. `lobby_state(req, GAME)` is the standard handler preamble and
raises if the session's lobby is playing something else.

`LobbyMember` forwards unknown attributes to its `User` (fastcore `GetAttr`), so
`member.name` and `member.needs_name` work on either type. State classes get
`remove_player(uid)` called automatically when someone leaves or spectates.

Persistence goes through `lobby_service.update(lobby)`; state is serialised with
`asdict` and rebuilt by the state class's `from_dict`, which must tolerate rows
written before a field existed.

## Traps that cost real time here

**Requests without a browser User-Agent get a stub page.** `BotFilterMiddleware`
answers lobby routes with an unfurl preview for UAs matching `curl`,
`python-requests`, `httpx` etc. Always pass `-A "Mozilla/5.0 Chrome/120"` when
driving a lobby with curl, and a matching header in `TestClient`. The page looks
plausible, so this fails silently.

**Themes are not stylesheets.** `static/styles/themes/*.css` are loaded by the
user through Settings into `localStorage['meme-games.custom-css']` and injected
as `<style id="custom-css">`. Editing a theme file changes nothing in an open
browser until it is re-imported:

```js
const r = await fetch('/static/styles/themes/sakura.css?t=' + Date.now(), {cache: 'no-store'});
localStorage.setItem('meme-games.custom-css', await r.text());
localStorage.setItem('meme-games.custom-css-enabled', 'true');  // 'false' to test the default theme
```

`static/styles/*.css` (top level) *is* served as a real stylesheet. Both it and
the JS under `static/scripts/**` are picked up by glob in `main.py`, so a new
file loads with no registration — and a deleted one 404s until restart.

**Theme CSS wins on source order, so component rules need scope.** Custom CSS is
injected after `app.css`. Themes restyle `.uk-textarea`/`.uk-btn` wholesale with
`!important`, which will repaint a component over the colour its own tokens just
set — scope such rules (`.mg-label .mg-label-input`, not `.mg-label-input`).
Tailwind's JIT `uk-theme-yellow` block is injected later still, so a theme's
`--primary` and friends need `!important` to stick.

**Franken UI / MonsterUI sharp edges**

- `Range` renders `<uk-input-range>`, a web component with a *closed* shadow
  root — no CSS can reach it. Use a native `<input type="range" class="uk-range">`.
- `.uk-checkbox:checked` draws its tick as a baked-in SVG background image tied
  to the theme swatch class, not `accent-color`; override
  `background-image: none` and draw your own.
- `stringify` joins with `str()`, so a *nested* group renders as a Python tuple
  repr inside the class attribute and the class silently never exists. Compose
  with `classes()` from `apps/shared/general.py`.
- `Modal(hx_open=True)` emits `hx-on--load`, which is not valid htmx syntax and
  never fires. Open with hyperscript `init ... call UIkit.modal(me).show()`.
- A modal rendered inside `.mg-page` is trapped by its `isolate` stacking
  context and paints under the navbar; `LobbyPage` returns it as a sibling.

**HTML responses are `no-store`** (`core/middleware/no_store.py`). These pages are
per-user and live, and a cached one replayed on Back resurrects state the server
has moved past. Static files set their own `Cache-Control` and are left alone.

## Testing

`tests/conftest.py` points `DB_PATH` at a temp file *before* `meme_games` is
imported, so it must stay the first import. `tests/client.py` provides a sync
wrapper with websocket support for flows that need a live server.

Components are tested by rendering them with `to_xml()` and asserting on the
markup — the cheapest way to pin down per-receiver visibility rules (that a
player's own label never reaches their own page, that private notes are not just
hidden but absent).

To exercise multiplayer by hand, drive a second player over curl with its own
cookie jar and a browser UA while watching the first in a browser: hit the lobby
URL once to get a session, `PUT /me/name`, then the game's join route.
