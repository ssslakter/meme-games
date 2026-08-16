from meme_games.core import *
from meme_games.domain import *
from meme_games.apps.shared import *
from meme_games.apps.shared.spectators import register_game_view
from meme_games.apps.user import UserInfo
from meme_games.apps.word_packs.domain import WordPackRepo
from meme_games.apps.word_packs.components import PacksSelect

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
        Div(H4(f'{team.value.title()} team', cls='mg-codenames-team-name'),
            Span(len(members), cls='mg-codenames-team-count tabular-nums'),
            cls='mg-codenames-team-head flex items-center justify-between'),
        Div(*[
            Div(
                UserInfo(reciever, member.user,
                         member.is_connected, member.is_host,
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


def LogLine(entry: LogEntry):
    team = Span(entry.team, cls='mg-log-team') if entry.team else None
    word = Span(f'"{entry.word}"', cls='mg-log-word')
    match entry.kind:
        case 'start': body = (team, ' opens the game')
        case 'turn': body = (team, ' is up')
        case 'timeout': body = (team, ' ran out of time')
        case 'win': body = (team, ' wins')
        case 'clue': body = (team, ' clue ', word, Span(entry.number, cls='mg-log-number'))
        case 'reveal': body = (team, ' opened ', word, ' — ',
                               Span(entry.card, cls='mg-log-card', data_card=entry.card))
        case _: body = (team, f' {entry.kind}')
    return P(*body, cls='mg-log-line', data_team=entry.team, data_ui='codenames-log-line')


def EventLog(state: CodenamesState):
    '''The public sequence of play. Only cards already turned over are named with a colour.'''
    return Card(
        H5('Event log'),
        Div(*([LogLine(entry) for entry in reversed(state.log)]
              or [P('Nothing yet.', cls=TextT.muted)]),
            cls='mg-codenames-log overflow-y-auto', data_ui='codenames-log'),
        cls='mg-panel mg-codenames-log-panel', body_cls='space-y-2 p-4')


def TeamsRail(reciever, lobby):
    return GameRail(
        H3('Teams'),
        TeamPanel(reciever, lobby, TeamColor.RED),
        TeamPanel(reciever, lobby, TeamColor.BLUE),
        EventLog(lobby.state),
        cls='mg-codenames-teams', data_ui='codenames-teams')


def BoardCard(reciever: LobbyMember | User, state: CodenamesState, card: WordCard):
    from ..routes import vote_card
    uid = reciever.uid
    known = card.revealed or uid in state.spymasters or state.phase == GamePhase.FINISHED
    visible_color = card.color if known else None
    clickable = (isinstance(reciever, LobbyMember) and state.phase == GamePhase.GUESSING and
                 state.team_of(reciever) == state.turn and uid not in state.spymasters and not card.revealed)
    classes = CARD_STYLE[visible_color] if visible_color else 'border-border bg-card hover:border-primary/60'
    voters = state.voters(card.id)
    committing = state.consensus() == card.id
    content = (Span(card.word, cls='text-lg font-semibold'),
               Span(visible_color.value if visible_color else '', cls='text-xs uppercase opacity-60'),
               Div(*[Span(cls='mg-vote-dot', data_mine=str(voter == uid).lower()) for voter in voters],
                   cls='mg-vote-dots') if voters else None)
    return Div(
        *content,
        cls=f'mg-game-card mg-word-card flex aspect-[5/3] min-w-0 flex-col items-center justify-center gap-1 border p-3 text-center shadow-sm transition {classes}'
            + (' cursor-pointer' if clickable else ''),
        data_ui='word-card', data_card=card.id,
        data_color=visible_color.value if visible_color else 'hidden',
        data_revealed=str(card.revealed).lower(),
        data_votes=str(len(voters)) if voters else None,
        data_commit='true' if committing else None,
        style=f'--mg-commit:{COMMIT_SECONDS}s' if committing else None,
        role='button' if clickable else None, tabindex='0' if clickable else None,
        hx_post=vote_card.to(card_id=card.id) if clickable else None,
        hx_swap='none' if clickable else None)


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
                LabelInput('Clue', name='clue', required=True, autocomplete='off',
                           placeholder='one or more words'),
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
                Div(P('Turn', cls=TextT.muted),
                    H3(state.turn.value.title() if state.turn else 'Game over',
                       cls='mg-codenames-turn', data_team=state.turn.value if state.turn else None)),
                CircleTimer(state.timer.time, total=state.timer.total, paused=state.timer.paused)
                    if state.turn_seconds() else None,
                Div(*[Span(f'{team.value.title()} {remaining[team]}',
                           cls='mg-codenames-remaining', data_team=team.value) for team in TeamColor],
                    cls='flex gap-4'),
                cls='flex flex-wrap items-center justify-between gap-4'),
            CluePanel(reciever, state), cls='mg-panel', body_cls='space-y-5 p-5'),
        Div(*[BoardCard(reciever, state, card) for card in state.board],
            cls='mg-codenames-board grid grid-cols-2 gap-3 sm:grid-cols-3 lg:grid-cols-5', data_ui='codenames-board'),
        cls='min-w-0 space-y-5')


def PackSelect(state: CodenamesState):
    from ..routes import editor_readonly
    packs = DI.get(WordPackRepo).get_all()
    return Div(
        Button(UkIcon('book-open', cls='mr-2'), 'Select wordpack',
               cls=(ButtonT.default, 'w-full justify-start'), data_uk_toggle='target: #pack-select'),
        Modal(ModalTitle('Wordpack selection'),
              Grid(Div(PacksSelect(packs, editor_readonly, hx_target='#editor', hx_swap='outerHTML'),
                       cls='overflow-auto col-span-2 border-r-2'),
                   Div(hx_post=editor_readonly.to(id=state.wordpack.id) if state.wordpack else None,
                       hx_trigger='load' if state.wordpack else None, cls='col-span-3 h-full'),
                   ModalCloseButton(),
                   cols=5),
              id='pack-select'))


def HostSettings(reciever, lobby, oob=False):
    from ..routes import pause_game, restart_game, shuffle_teams, update_settings
    if not is_host(reciever): return None
    state: CodenamesState = lobby.state
    waiting = state.phase == GamePhase.WAITING
    return Div(
        H5('Host controls'),
        PackSelect(state),
        Form(
            LabelInput('Clue seconds (0 = no limit)', name='clue_seconds', type='number', min=0, max=600,
                       value=str(state.clue_seconds)),
            LabelInput('Guess seconds (0 = no limit)', name='guess_seconds', type='number', min=0, max=600,
                       value=str(state.guess_seconds)),
            Button('Update settings', cls=(ButtonT.primary, 'w-full')),
            hx_post=update_settings, hx_swap='none', cls='space-y-3'),
        Div(
            Button(UkIcon('play' if state.timer.paused else 'pause', cls='mr-2 shrink-0'),
                   'Resume' if state.timer.paused else 'Pause', hx_post=pause_game, hx_swap='none',
                   disabled=not state.turn_seconds(),
                   cls=(ButtonT.default, 'w-full justify-start px-3 py-2')),
            Button(UkIcon('shuffle', cls='mr-2 shrink-0'), 'Shuffle teams', hx_post=shuffle_teams, hx_swap='none',
                   disabled=not waiting or not state.players,
                   cls=(ButtonT.default, 'w-full justify-start px-3 py-2')),
            Button(UkIcon('rotate-ccw', cls='mr-2 shrink-0'), 'Restart', hx_post=restart_game, hx_swap='none',
                   hx_confirm='Restart Codenames and keep the current teams?',
                   cls=(ButtonT.destructive, 'w-full justify-start px-3 py-2')),
            cls='grid grid-cols-2 gap-3'),
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
