from meme_games.core import *
from meme_games.domain import *
from meme_games.apps.shared import *
from meme_games.apps.shared.spectators import register_game_view
from meme_games.apps.user import UserInfo
from meme_games.apps.word_packs.domain import WordPackRepo

from ..domain import *


TEAM_STYLE = {
    TeamColor.RED: 'border-red-300/70 bg-red-50/70 dark:border-red-900 dark:bg-red-950/25',
    TeamColor.BLUE: 'border-blue-300/70 bg-blue-50/70 dark:border-blue-900 dark:bg-blue-950/25',
}

CARD_STYLE = {
    CardColor.RED: 'border-red-500 bg-red-100 text-red-950 dark:bg-red-950 dark:text-red-50',
    CardColor.BLUE: 'border-blue-500 bg-blue-100 text-blue-950 dark:bg-blue-950 dark:text-blue-50',
    CardColor.NEUTRAL: 'border-stone-400 bg-stone-100 text-stone-950 dark:bg-stone-800 dark:text-stone-50',
    CardColor.BOMB: 'border-slate-950 bg-slate-900 text-white',
}


def TeamPanel(reciever: LobbyMember | User, lobby: Lobby, team: TeamColor):
    from ..routes import join_team, toggle_spymaster
    state: CodenamesState = lobby.state
    members = [lobby.members[uid] for uid in state.team_uids(team) if uid in lobby.members]
    mine = isinstance(reciever, LobbyMember) and state.team_of(reciever) == team
    return Card(
        Div(H4(f'{team.value.title()} team'), Span(len(members), cls='tabular-nums'),
            cls='flex items-center justify-between'),
        Div(*[
            Div(
                UserInfo(reciever, member.user,
                         member.is_connected or member.uid in DI.get(AgentAccessService).connected_users,
                         avatar_cls='h-11 w-11'),
                Span('Spymaster', cls='rounded-full border px-2 py-1 text-xs') if member.uid in state.spymasters else None,
                cls='flex items-center justify-between gap-2')
            for member in members], cls='space-y-3'),
        Button('Switch here' if state.team_of(reciever) else 'Join team',
               hx_post=join_team.to(team=team.value), hx_swap='none', cls=(ButtonT.default, 'w-full'))
            if state.phase == GamePhase.WAITING and isinstance(reciever, LobbyMember) and not mine else None,
        Button(UkIcon('eye', cls='mr-2'),
               'Become operative' if reciever.uid in state.spymasters else 'Become spymaster',
               hx_post=toggle_spymaster, hx_swap='none', cls=(ButtonT.default, 'w-full'))
            if state.phase == GamePhase.WAITING and mine else None,
        cls=f'mg-game-card mg-codenames-team {TEAM_STYLE[team]}', body_cls='space-y-4 p-4',
        data_ui='codenames-team', data_team=team.value)


def TeamsRail(reciever, lobby):
    return GameRail(
        H3('Teams'),
        TeamPanel(reciever, lobby, TeamColor.RED),
        TeamPanel(reciever, lobby, TeamColor.BLUE),
        cls='mg-codenames-teams', data_ui='codenames-teams')


def BoardCard(reciever: LobbyMember | User, state: CodenamesState, card: WordCard):
    from ..routes import reveal_card
    uid = reciever.uid
    known = card.revealed or uid in state.spymasters
    visible_color = card.color if known else None
    clickable = (isinstance(reciever, LobbyMember) and state.phase == GamePhase.GUESSING and
                 state.team_of(reciever) == state.turn and uid not in state.spymasters and not card.revealed)
    classes = CARD_STYLE[visible_color] if visible_color else 'border-border bg-card hover:border-primary/60'
    content = (Span(card.word, cls='text-lg font-semibold'),
               Span(visible_color.value if visible_color else '', cls='text-xs uppercase opacity-60'))
    kwargs = dict(
        cls=f'mg-game-card mg-word-card flex aspect-[5/3] min-w-0 flex-col items-center justify-center gap-1 border p-3 text-center shadow-sm transition {classes}',
        data_ui='word-card', data_card=card.id,
        data_color=visible_color.value if visible_color else 'hidden',
        data_revealed=str(card.revealed).lower())
    return Button(*content, type='button', hx_post=reveal_card.to(card_id=card.id), hx_swap='none', **kwargs) if clickable else Div(*content, **kwargs)


def CluePanel(reciever: LobbyMember | User, state: CodenamesState):
    from ..routes import end_turn, start_game, submit_clue
    if state.phase == GamePhase.FINISHED:
        return Card(H2(f'{state.winner.value.title()} team wins!'), P('The host can restart from game settings.'),
                    cls='mg-panel text-center', body_cls='space-y-3 p-5', data_ui='game-result')
    if state.phase == GamePhase.WAITING:
        return Card(H3('Assemble two field teams'),
                    P('Each team needs at least two players and exactly one spymaster.', cls=TextT.muted),
                    Button(UkIcon('play', cls='mr-2'), 'Start game', hx_post=start_game, hx_swap='none',
                           disabled=not state.can_start(), cls=(ButtonT.primary, 'px-8'))
                        if is_host(reciever) else None,
                    cls='mg-panel', body_cls='space-y-3 p-5')
    mine = state.team_of(reciever)
    is_spymaster = reciever.uid in state.spymasters
    if state.phase == GamePhase.CLUE:
        if mine == state.turn and is_spymaster:
            return Form(
                LabelInput('One-word clue', name='clue', required=True, autocomplete='off'),
                LabelInput('Number', name='number', type='number', min=1, max=9, value='1', required=True),
                Button(UkIcon('send', cls='mr-2'), 'Give clue', cls=ButtonT.primary),
                hx_post=submit_clue, hx_swap='none', cls='grid items-end gap-3 sm:grid-cols-[1fr_8rem_auto]')
        return P(f'Waiting for the {state.turn.value} spymaster to give a clue.', cls=TextT.muted)
    return Div(
        Div(P('Clue', cls=TextT.muted), H2(f'{state.clue} · {state.clue_number}'),
            P(f'{state.guesses_left} guesses remaining', cls=TextT.muted), cls='text-center'),
        Button('End guessing', hx_post=end_turn, hx_swap='none', cls=ButtonT.default)
            if mine == state.turn and not is_spymaster else None,
        cls='flex flex-wrap items-center justify-center gap-5')


def Board(reciever, state):
    if state.phase == GamePhase.WAITING: return CluePanel(reciever, state)
    remaining = {team: sum(not card.revealed and card.color == team.card_color for card in state.board)
                 for team in TeamColor}
    return Div(
        Card(
            Div(
                Div(P('Turn', cls=TextT.muted), H3(state.turn.value.title() if state.turn else 'Game over')),
                Div(Span(f'Red {remaining[TeamColor.RED]}', cls='text-red-600'),
                    Span(f'Blue {remaining[TeamColor.BLUE]}', cls='text-blue-600'), cls='flex gap-4'),
                cls='flex flex-wrap items-center justify-between gap-4'),
            CluePanel(reciever, state), cls='mg-panel', body_cls='space-y-5 p-5'),
        Div(*[BoardCard(reciever, state, card) for card in state.board],
            cls='mg-codenames-board grid grid-cols-2 gap-3 sm:grid-cols-3 lg:grid-cols-5', data_ui='codenames-board'),
        cls='min-w-0 space-y-5')


def AgentPlayers(reciever, lobby, token=None, oob=False):
    from ..routes import create_agent_invite, revoke_agent, show_host_settings
    if not is_host(reciever): return None
    service = DI.get(AgentAccessService)
    invited = [access for access in service.repo.for_lobby(lobby.id) if not access.revoked]
    return Div(
        Div(H5('Agent players'),
            Button('Back to game settings', hx_get=show_host_settings, hx_target='#codenames-host-controls',
                   hx_swap='outerHTML', cls=(ButtonT.ghost, 'px-2 py-1 text-xs')),
            cls='flex items-center justify-between gap-3'),
        P('Create a lobby-scoped MCP credential. The token is shown once.', cls=TextT.muted),
        InviteToken(token) if token else None,
        Div(*[
            Div(
                Div(Span(service.users.get(access.user_uid).name, cls='font-medium'),
                    Span('Connected' if access.user_uid in service.connected_users else 'Invited',
                         cls='text-xs text-muted-foreground'), cls='min-w-0'),
                Button('Revoke', hx_post=revoke_agent.to(access_id=access.id), hx_swap='none',
                       hx_confirm='Revoke this agent and remove it from the lobby?',
                       cls=(ButtonT.destructive, 'shrink-0 px-3 py-1.5')),
                cls='flex items-center justify-between gap-3')
            for access in invited], cls='space-y-2'),
        Form(
            LabelInput('Agent name', name='name', maxlength=40, required=True, autocomplete='off'),
            Button(UkIcon('bot', cls='mr-2'), 'Create invite', cls=(ButtonT.default, 'w-full')),
            hx_post=create_agent_invite, hx_target='#codenames-host-controls', hx_swap='outerHTML',
            cls='space-y-3'),
        id='codenames-host-controls', hx_swap_oob='true' if oob else None,
        cls='space-y-4', data_ui='agent-invites')


def InviteToken(token: str):
    import json, os
    config = {'url': os.environ.get('MCP_PUBLIC_URL', 'http://127.0.0.1:8001/mcp'),
              'headers': {'Authorization': f'Bearer {token}'}}
    return Div(
        P('Copy this now—it will not be shown again.', cls='font-medium'),
        Input(value=token, readonly=True, cls='uk-input w-full font-mono text-xs', onclick='this.select()'),
        Pre(Code(json.dumps(config, indent=2)), cls='overflow-auto rounded border p-3 text-xs'),
        cls='space-y-2 rounded border border-primary/40 bg-primary/5 p-3', role='status')


def HostSettings(reciever, lobby, oob=False):
    from ..routes import restart_game, select_pack, show_agent_players
    if not is_host(reciever): return None
    state = lobby.state
    packs = DI.get(WordPackRepo).get_all()
    return Div(
        H5('Host controls'),
        Form(
            FormLabel('Wordpack', fr='codenames-wordpack'),
            Select(*[Option(pack.name, value=pack.id, selected=state.wordpack and pack.id == state.wordpack.id)
                     for pack in packs], id='codenames-wordpack', name='pack_id', cls='uk-select'),
            Button('Use wordpack', cls=(ButtonT.default, 'w-full')),
            hx_post=select_pack, hx_swap='none', cls='space-y-3'),
        Button(UkIcon('rotate-ccw', cls='mr-2'), 'Restart game', hx_post=restart_game, hx_swap='none',
               hx_confirm='Restart Codenames and keep the current teams?', cls=(ButtonT.destructive, 'w-full'))
            if state.phase != GamePhase.WAITING else None,
        Div(cls='border-t pt-4'),
        Button(UkIcon('bot', cls='mr-2'), 'Agent players', hx_get=show_agent_players,
               hx_target='#codenames-host-controls', hx_swap='outerHTML', cls=(ButtonT.default, 'w-full')),
        id='codenames-host-controls', hx_swap_oob='true' if oob else None,
        cls='space-y-4', data_ui='codenames-host-controls')


def Game(reciever: LobbyMember | User, lobby: Lobby, **kwargs):
    state: CodenamesState = lobby.state
    return Div(
        TeamsRail(reciever, lobby),
        Board(reciever, state),
        id='game', cls=stringify(('mg-game mg-game-codenames grid min-w-0 items-start gap-6 lg:grid-cols-[20rem_minmax(0,1fr)]', kwargs.pop('cls', ''))),
        data_ui='game', data_game=CODENAMES, data_phase=state.phase.value, **kwargs)


def Page(reciever: LobbyMember | User, lobby: Lobby):
    from ..routes import ws_url
    return LobbyPage(
        GameShell(Game(reciever, lobby), LobbyTools(reciever, lobby, HostSettings(reciever, lobby))),
        hx_ext='ws', ws_connect=ws_url, no_image=True, user=reciever,
        title=f'Codenames lobby: {lobby.id}', page='codenames')


register_game_view(CODENAMES, Game)
