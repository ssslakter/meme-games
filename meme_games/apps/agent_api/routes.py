import asyncio
import hmac
import os

from meme_games.core import *
from meme_games.domain import *
from meme_games.apps.shared.actions import ActionRejected
from meme_games.apps.shared.agent import AgentGame, agent_games
from meme_games.apps.shared.utils import register_route


rt = APIRouter('/internal/agents')
register_route(rt)

lobbies = DI.get(LobbyService)
users = DI.get(UserManager)
sessions = DI.get(AgentPlayerSessionService)


def _service_auth(req: Request):
    configured = os.environ.get('MCP_GATEWAY_SECRET', '')
    supplied = req.headers.get('x-meme-games-gateway', '')
    if not configured: raise HTTPException(404)
    if not hmac.compare_digest(configured, supplied): raise HTTPException(401, 'invalid_gateway_credential')


async def _body(req: Request) -> dict:
    _service_auth(req)
    try: return await req.json()
    except Exception: raise HTTPException(400, 'invalid_request')


def _name(value) -> str:
    name = ' '.join(str(value or '').split())
    if not 1 <= len(name) <= 40: raise HTTPException(422, 'invalid_name')
    return name


def _player(handle: str):
    session = sessions.get(str(handle or ''))
    if not session: raise HTTPException(401, 'invalid_player_session')
    lobby = lobbies.get_lobby(session.lobby_id)
    user = users.get(session.user_uid)
    member = lobby.get_member(session.user_uid) if lobby else None
    if not lobby or not user or not member: raise HTTPException(410, 'player_session_closed')
    return session, lobby, member


def _adapter(lobby: Lobby) -> AgentGame:
    adapter = agent_games.get(lobby.current_game)
    if not adapter: raise HTTPException(409, f'unsupported_game:{lobby.current_game}')
    return adapter


@rt('/join', methods=['post'])
async def join(req: Request):
    data = await _body(req)
    lobby = lobbies.get_lobby(str(data.get('lobby_code', '')))
    if not lobby: return JSONResponse({'detail': 'lobby_not_found'}, status_code=404)
    if not lobby.allow_agents: raise HTTPException(403, 'agents_disabled')
    if lobby.locked: raise HTTPException(409, 'lobby_locked')
    name = _name(data.get('name'))
    if any(member.name.casefold() == name.casefold() for member in lobby.members.values()):
        raise HTTPException(409, 'name_taken')
    session, handle = sessions.create(lobby.id, name)
    user = users.get(session.user_uid)
    member = lobby.create_member(user)
    adapter = agent_games.get(lobby.current_game)
    if adapter: adapter.join(lobby, member)
    lobbies.update(lobby)
    await lobby_events.publish(lobby, 'roster')
    return {'player_session': handle, 'lobby_id': lobby.id, 'name': name, 'cursor': lobby.revision}


@rt('/state', methods=['post'])
async def state(req: Request):
    data = await _body(req)
    _, lobby, member = _player(data.get('player_session'))
    return _adapter(lobby).snapshot(lobby, member)


@rt('/action', methods=['post'])
async def action(req: Request):
    data = await _body(req)
    _, lobby, member = _player(data.get('player_session'))
    try:
        result = await _adapter(lobby).action(
            lobby, member, str(data.get('action', '')), data.get('arguments') or {})
    except ActionRejected as error:
        return JSONResponse({'ok': False, 'message': str(error), 'revision': lobby.revision}, status_code=409)
    return asdict(result)


@rt('/events', methods=['post'])
async def events(req: Request):
    data = await _body(req)
    _, lobby, _ = _player(data.get('player_session'))
    try: after, timeout_seconds = int(data.get('cursor', 0)), int(data.get('timeout_seconds', 25))
    except (TypeError, ValueError): raise HTTPException(400, 'invalid_cursor_or_timeout')
    if after < 0: raise HTTPException(400, 'cursor_must_be_non_negative')
    timeout_seconds = min(max(timeout_seconds, 1), 25)
    repo = DI.get(LobbyEventRepo)

    def payload():
        found = repo.after(lobby.id, after)
        return {'events': [
            {'sequence': event.revision, 'type': 'state_changed', 'revision': event.revision}
            for event in found],
            'next_cursor': found[-1].revision if found else after,
            'hint': 'Read game state before taking an action.' if found else 'No new events. Wait again.'}

    result = payload()
    if result['events']: return result
    queue = asyncio.Queue(maxsize=1)

    def enqueue(event: LobbyChanged, changed_lobby):
        if changed_lobby.id == lobby.id and not queue.full(): queue.put_nowait(event)

    unsubscribe = lobby_events.subscribe(enqueue)
    try:
        result = payload()
        if not result['events']:
            try: await asyncio.wait_for(queue.get(), timeout_seconds)
            except TimeoutError: pass
        return payload()
    finally: unsubscribe()


@rt('/leave', methods=['post'])
async def leave(req: Request):
    data = await _body(req)
    session, lobby, member = _player(data.get('player_session'))
    if lobby.locked: raise HTTPException(409, 'lobby_locked')
    sessions.close(data['player_session'])
    lobby.remove_member(member.uid)
    lobbies.update(lobby)
    await lobby_events.publish(lobby, 'roster')
    return {'ok': True, 'message': 'Left lobby', 'revision': lobby.revision}
