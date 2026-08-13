import asyncio
import hmac
import os
from dataclasses import dataclass

from meme_games.core import *
from meme_games.domain import *
from meme_games.apps.shared import register_route
from meme_games.apps.codenames.actions import ActionRejected, codenames_actions
from meme_games.apps.codenames.domain import CODENAMES, GamePhase, TeamColor


rt = APIRouter('/internal/agents')
register_route(rt)

lobbies = DI.get(LobbyService)
users = DI.get(UserManager)
sessions = DI.get(AgentPlayerSessionService)


@dataclass(frozen=True)
class AgentGameAdapter:
    snapshot: Callable
    action: Callable


GAME_ADAPTERS: dict[str, AgentGameAdapter] = {}


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


def _available_actions(member: LobbyMember, state) -> list[str]:
    team = state.team_of(member)
    spymaster = member.uid in state.spymasters
    if state.phase == GamePhase.WAITING:
        actions = ['join_team']
        if team: actions.append('set_role')
        if member.is_player: actions.append('spectate')
        return actions
    if state.phase == GamePhase.CLUE and team == state.turn and spymaster: return ['give_clue']
    if state.phase == GamePhase.GUESSING and team == state.turn and not spymaster:
        return ['reveal_card', 'end_turn']
    return []


def codenames_snapshot(lobby: Lobby, member: LobbyMember):
    state = lobby.state
    knows_key = member.uid in state.spymasters

    def card_data(card):
        result = {'id': card.id, 'word': card.word, 'revealed': card.revealed}
        if card.revealed or knows_key: result['color'] = card.color.value
        return result

    return {
        'lobby_id': lobby.id,
        'game': CODENAMES,
        'revision': lobby.revision,
        'phase': state.phase.value,
        'turn': state.turn.value if state.turn else None,
        'winner': state.winner.value if state.winner else None,
        'clue': {'word': state.clue, 'number': state.clue_number,
                 'guesses_left': state.guesses_left} if state.clue else None,
        'you': {'id': member.uid, 'name': member.name,
                'team': state.team_of(member).value if state.team_of(member) else None,
                'role': 'spymaster' if knows_key else 'operative' if state.team_of(member) else 'spectator'},
        'teams': {
            team.value: [
                {'id': uid, 'name': lobby.members[uid].name,
                 'role': 'spymaster' if uid in state.spymasters else 'operative',
                 'kind': lobby.members[uid].user.kind}
                for uid in state.team_uids(team) if uid in lobby.members]
            for team in TeamColor},
        'spectators': [
            {'id': candidate.uid, 'name': candidate.name, 'kind': candidate.user.kind}
            for candidate in lobby.sorted_members() if not candidate.is_player],
        'board': [card_data(card) for card in state.board],
        'available_actions': _available_actions(member, state),
    }


async def codenames_action(lobby: Lobby, member: LobbyMember, action: str, arguments: dict):
    match action:
        case 'join_team': return await codenames_actions.join_team(lobby, member, arguments.get('team', ''))
        case 'set_role': return await codenames_actions.set_role(lobby, member, arguments.get('role', ''))
        case 'give_clue':
            try: number = int(arguments.get('number'))
            except (TypeError, ValueError): raise ActionRejected('number must be an integer')
            return await codenames_actions.give_clue(lobby, member, str(arguments.get('clue', '')), number)
        case 'reveal_card': return await codenames_actions.reveal_card(lobby, member, str(arguments.get('card_id', '')))
        case 'end_turn': return await codenames_actions.end_turn(lobby, member)
        case 'spectate': return await codenames_actions.spectate(lobby, member)
        case _: raise ActionRejected('Unknown action')


GAME_ADAPTERS[CODENAMES] = AgentGameAdapter(codenames_snapshot, codenames_action)


def _adapter(lobby: Lobby) -> AgentGameAdapter:
    adapter = GAME_ADAPTERS.get(lobby.current_game)
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
    lobby.create_member(user)
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
