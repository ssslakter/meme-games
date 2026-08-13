import asyncio
import hmac
import json
import os

from meme_games.core import *
from meme_games.domain import *
from meme_games.apps.shared import register_route
from meme_games.apps.codenames.actions import ActionRejected, codenames_actions
from meme_games.apps.codenames.domain import CODENAMES, GamePhase, TeamColor


rt = APIRouter('/internal/agents')
register_route(rt)

lobbies = DI.get(LobbyService)
users = DI.get(UserManager)
access_service = DI.get(AgentAccessService)


def _service_auth(req: Request):
    configured = os.environ.get('MCP_GATEWAY_SECRET', '')
    supplied = req.headers.get('x-meme-games-gateway', '')
    if not configured: raise HTTPException(404)
    if not hmac.compare_digest(configured, supplied): raise HTTPException(401, 'Invalid gateway credential')


def _bearer(req: Request) -> str:
    scheme, _, token = req.headers.get('authorization', '').partition(' ')
    if scheme.lower() != 'bearer' or not token: raise HTTPException(401, 'Missing agent credential')
    return token


async def _agent(req: Request):
    _service_auth(req)
    access = access_service.verify(_bearer(req))
    if not access: raise HTTPException(401, 'Invalid agent credential')
    lobby = lobbies.get_lobby(access.lobby_id)
    user = users.get(access.user_uid)
    if not lobby or not user: raise HTTPException(404, 'Lobby no longer exists')
    member = lobby.get_member(user.uid)
    if not member:
        member = lobby.create_member(user)
        lobbies.update(lobby)
        await lobby_events.publish(lobby, 'roster')
    return access, lobby, member


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


@rt('/identity', methods=['get'])
async def identity(req: Request):
    access, lobby, member = await _agent(req)
    return {'lobby_id': lobby.id, 'agent_id': member.uid, 'name': member.name,
            'game': lobby.current_game,
            'resource_uri': f'game://lobbies/{lobby.id}/agents/{member.uid}/state'}


@rt('/state', methods=['get'])
async def state(req: Request):
    _, lobby, member = await _agent(req)
    if lobby.current_game != CODENAMES: raise HTTPException(409, f'Lobby is playing {lobby.current_game}')
    return codenames_snapshot(lobby, member)


@rt('/action', methods=['post'])
async def action(req: Request):
    _, lobby, member = await _agent(req)
    if lobby.current_game != CODENAMES: raise HTTPException(409, f'Lobby is playing {lobby.current_game}')
    data = await req.json()
    try:
        result = await codenames_action(lobby, member, str(data.get('action', '')), data.get('arguments') or {})
    except ActionRejected as error:
        return JSONResponse({'ok': False, 'message': str(error), 'revision': lobby.revision}, status_code=409)
    return asdict(result)


@rt('/presence', methods=['post'])
async def presence(req: Request):
    access, _, member = await _agent(req)
    data = await req.json()
    if data.get('connected', True): access_service.connected_users.add(member.uid)
    else: access_service.connected_users.discard(member.uid)
    return {'ok': True, 'access_id': access.id}


@rt('/events', methods=['get'])
async def events(req: Request):
    _service_auth(req)
    queue = asyncio.Queue(maxsize=256)
    def enqueue(event: LobbyChanged, _lobby):
        if queue.full(): queue.get_nowait()
        queue.put_nowait(event)
    unsubscribe = lobby_events.subscribe(enqueue)

    async def stream():
        try:
            while True:
                try: event = await asyncio.wait_for(queue.get(), 15)
                except TimeoutError:
                    yield ': keep-alive\n\n'
                    continue
                payload = {'lobby_id': event.lobby_id, 'game': event.game,
                           'revision': event.revision, 'topics': sorted(event.topics)}
                yield f'data: {json.dumps(payload)}\n\n'
        finally: unsubscribe()

    return StreamingResponse(stream(), media_type='text/event-stream', headers={
        'Cache-Control': 'no-cache', 'X-Accel-Buffering': 'no'})
