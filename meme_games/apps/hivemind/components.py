from ..shared import *
from ..user import *
from meme_games.domain import Lobby as _Lobby, LobbyMember, User, is_player
from ..word_packs.components import PacksSelect, WordPackEditor, wordpack_manager
from .domain import *

Lobby = _Lobby[HiveMindState]


def player_uids(lobby: Lobby) -> list[str]:
    return [member.uid for member in lobby.sorted_members() if member.is_player]


def QuestionCard(lobby: Lobby, **kwargs):
    state: HiveMindState = lobby.state
    if state.phase == HivePhase.WAITING:
        body = (H3('Everyone answers the same question'),
                P('You score by agreeing with somebody else: the most ordinary answer wins, '
                  'and an answer nobody else gave scores nothing.', cls=TextT.muted))
    else:
        body = (Span(f'Round {state.round_number} of {state.total_rounds}',
                     cls='text-xs uppercase tracking-wide opacity-60'),
                H2(state.question, cls='m-0'))
    return Card(*body, id='hivemind-question', cls='mg-panel text-center',
                body_cls='space-y-2 p-6', data_ui='hivemind-question', **kwargs)


def Status(reciever: LobbyMember | User, lobby: Lobby, **kwargs):
    """How many answers are in. A count only: a name would give the round away."""
    state: HiveMindState = lobby.state
    uids = player_uids(lobby)
    answered = state.answered(uids)
    count = ('Everyone has answered' if state.all_answered(uids) else
             f'{answered} of {len(uids)} answered' if uids else 'Nobody is playing yet')
    hint = ('Your answer is in - submit again to change it.'
            if is_player(reciever) and state.has_answer(reciever.uid) else
            'Your answer stays hidden until everyone is in.' if is_player(reciever) else
            'Answers stay hidden until everyone is in.')
    return Div(Div(UkIcon('users', width=16, height=16), Span(count, cls='font-medium'),
                   cls='flex items-center gap-2'),
               P(hint, cls=(TextT.muted, TextT.sm, 'm-0')),
               id='hivemind-status', cls='space-y-1', data_ui='hivemind-status', **kwargs)


def AnswerArea(reciever: LobbyMember | User, lobby: Lobby, **kwargs):
    from .routes import submit_answer
    if lobby.state.phase != HivePhase.WRITING: return None
    return Card(
        Status(reciever, lobby),
        Form(Input(name='answer', required=True, maxlength=ANSWER_MAX, autocomplete='off',
                   placeholder='One answer', cls='uk-input min-w-0 flex-1'),
             Button(UkIcon('send', cls='mr-2'), 'Submit', type='submit',
                    cls=(ButtonT.primary, 'shrink-0')),
             hx_post=submit_answer, hx_swap='none', cls='flex gap-2')
            if is_player(reciever) else None,
        id='hivemind-answers', cls='mg-panel mg-hivemind-answer', body_cls='space-y-2 p-4',
        data_ui='hivemind-answer', **kwargs)


def RevealBoard(reciever: LobbyMember | User, lobby: Lobby, **kwargs):
    """The round just played: what agreed first, then who went nobody's way."""
    state: HiveMindState = lobby.state
    played = state.last()
    if state.phase != HivePhase.REVEAL or not played: return None

    def name(uid: str):
        return MemberName(reciever, lobby.members[uid], cls='mg-hivemind-name') if uid in lobby.members else None

    matches = [Div(Span(answer, cls='font-medium'),
                   Span(f'+1 each · {len(uids)}', cls='text-sm tabular-nums'),
                   Div(*[name(uid) for uid in uids], cls='text-sm'), cls='space-y-1',
                   data_ui='hivemind-match')
               for answer, uids in played.groups().items()]
    uniques = [Div(name(uid), Span(text), Span('0', cls=TextT.muted),
                   cls='flex items-center justify-between gap-2', data_ui='hivemind-unique')
               for uid, text in played.uniques().items()]
    return Card(H5(f'What everyone wrote: {played.question}'),
                Div(*matches or [P('Nobody agreed with anybody - no points this round.',
                                   cls=TextT.muted)], cls='space-y-3'),
                Div(*uniques, cls='space-y-1') if uniques else None,
                id='hivemind-reveal', cls='mg-panel', body_cls='space-y-3 p-4',
                data_ui='hivemind-reveal', **kwargs)


def Scoreboard(reciever: LobbyMember | User, lobby: Lobby, **kwargs):
    state: HiveMindState = lobby.state
    totals = state.totals()
    players = sorted((lobby.members[uid] for uid in player_uids(lobby) if uid in lobby.members),
                     key=lambda member: (-totals.get(member.uid, 0), member.name))
    top = max((totals.get(member.uid, 0) for member in players), default=0)
    winners = [member for member in players
               if state.finished and top and totals.get(member.uid, 0) == top]
    rows = [Div(MemberName(reciever, member, cls='mg-hivemind-name'),
                Span(totals.get(member.uid, 0), cls='tabular-nums font-semibold'),
                cls='flex items-center justify-between gap-2',
                data_ui='hivemind-score-row', data_points=str(totals.get(member.uid, 0)),
                data_winner='true' if member in winners else None)
            for member in players]
    result = None
    if state.finished:
        result = P(f"Winner: {', '.join(member.name for member in winners)} with "
                   f"{top} point{'' if top == 1 else 's'}." if winners
                   else 'Nobody matched anyone - no points this game.', cls=TextT.muted)
    return Card(Div(H5('Scoreboard', cls='m-0'),
                    Span(f'{len(state.revealed)} of {state.total_rounds} rounds',
                         cls=(TextT.muted, TextT.sm)),
                    cls='flex items-baseline justify-between gap-2'),
                Div(*rows or [P('Nobody is playing yet.', cls=(TextT.muted, 'm-0'))],
                    cls='space-y-2'), result,
                id='hivemind-scoreboard', cls='mg-panel', body_cls='space-y-3 p-4',
                data_ui='hivemind-scoreboard', **kwargs)


def JoinCard(reciever: LobbyMember | User, lobby: Lobby, **kwargs):
    from .routes import play
    if is_player(reciever) or lobby.locked: return None
    return Card(H3('Hive Mind', cls='m-0'),
                P('Each round everyone answers the same question in secret. Answers that agree '
                  'score a point; answers nobody else gave score nothing.', cls=TextT.muted),
                Button(UkIcon('play', cls='mr-2'), 'Join the game', type='button',
                       hx_post=play, hx_swap='none', cls=(ButtonT.primary, 'w-full')),
                id='hivemind-join', cls='mg-panel', body_cls='space-y-3 p-4',
                data_ui='hivemind-join', **kwargs)


def SelectEditor(member: LobbyMember | User, pack, state: HiveMindState):
    from .routes import select_pack
    waiting = state.phase == HivePhase.WAITING
    allowed = is_host(member) and waiting
    label = ('Select this deck' if allowed else
             'Game in progress' if not waiting else 'Must be host to select')
    return WordPackEditor(pack, readonly=True,
                          form_kwargs=dict(hx_post=select_pack, hx_swap='none'),
                          submit_button=Button(label, disabled=not allowed),
                          cls='mg-pack-select-editor',
                          hx_on__after_request="UIkit.modal('#pack-select').hide()")


def PackSelectContents(member: LobbyMember | User, state: HiveMindState):
    from .routes import editor_readonly
    return Div(Div(PacksSelect(wordpack_manager.get_all(), editor_readonly,
                               hx_target='#editor', hx_swap='outerHTML'),
                   cls='mg-pack-select-list overflow-auto'),
               SelectEditor(member, state.wordpack, state),
               ModalCloseButton(), cls='mg-pack-select-layout')


def PackSelectButton(state: HiveMindState, **kwargs):
    """Opens the pack browser for everyone; picking one stays host-only, in the modal."""
    return Div(Button(UkIcon('book-open', cls='mr-2 shrink-0'), 'Question deck',
                      cls=(ButtonT.default, 'w-full justify-start'),
                      data_uk_toggle='target: #pack-select'),
               P(state.wordpack.name if state.wordpack else 'No deck selected',
                 cls=(TextT.muted, 'truncate text-sm')),
               cls='space-y-1', data_ui='hivemind-deck', **kwargs)


def PackSelectModal() -> FT:
    from .routes import pack_select
    return Modal(ModalTitle('Question deck'),
                 Div(P('Loading wordpacks…', cls=TextT.muted), id='pack-select-content'),
                 id='pack-select', hx_get=pack_select, hx_trigger='shown',
                 hx_target='#pack-select-content', hx_swap='innerHTML', cls='mg-pack-select-modal')


def HiveMindSettings(reciever: LobbyMember | User, lobby: Lobby, **kwargs):
    """Host controls: start, move the round on, restart, and the deck itself."""
    if not is_host(reciever): return None
    from .routes import advance, restart_game, start_game, update_settings
    state: HiveMindState = lobby.state
    waiting = state.phase == HivePhase.WAITING
    if waiting:
        control = Button(UkIcon('play', cls='mr-2'), 'Start game', hx_post=start_game,
                         hx_swap='none', disabled=len(player_uids(lobby)) < 2,
                         cls=(ButtonT.primary, 'w-full'))
    else:
        label = 'Reveal answers' if state.phase == HivePhase.WRITING else (
            'Start a new game' if state.finished else 'Next round')
        control = Div(
            Button(label, hx_post=advance, hx_swap='none', disabled=state.finished,
                   cls=(ButtonT.primary, 'w-full')) if not state.finished else None,
            Button(UkIcon('rotate-ccw', cls='mr-2'), 'New game', hx_post=restart_game,
                   hx_swap='none', hx_confirm='Start a new game and clear the scores?',
                   cls=(ButtonT.destructive, 'w-full')),
            cls='space-y-2')
    return Div(
        control,
        Div(H5('Question deck', cls='m-0'),
            PackSelectButton(state),
            P(f'{len(state.deck())} questions. Rounds past the end of the deck start over '
              'at the top.', cls=(TextT.muted, TextT.sm)),
            Form(LabelInput('Rounds', name='total_rounds', type='number', min=1, max=ROUNDS_MAX,
                            value=str(state.total_rounds), disabled=not waiting),
                 Button('Save rounds', type='submit', disabled=not waiting,
                        cls=(ButtonT.default, 'w-full')),
                 hx_post=update_settings, hx_swap='none', cls='space-y-2'),
            cls='space-y-2'),
        id='hivemind-settings', cls='space-y-3', data_ui='hivemind-settings', **kwargs)


def Game(reciever: LobbyMember | User, lobby: Lobby, **kwargs):
    """The board: what a receiver may see depends on the phase, and answers are on the
    table only once the round has closed."""
    state: HiveMindState = lobby.state
    return Div(
        Div(QuestionCard(lobby), AnswerArea(reciever, lobby), RevealBoard(reciever, lobby),
            JoinCard(reciever, lobby), cls='min-w-0 space-y-4'),
        Scoreboard(reciever, lobby),
        id='game',
        cls=classes('mg-game mg-game-hivemind grid min-w-0 items-start gap-6 lg:grid-cols-[minmax(0,1fr)_18rem]',
                    kwargs.pop('cls', '')),
        data_ui='game', data_game=HIVEMIND, data_phase=state.phase.value, **kwargs)


def MainBlock(reciever: LobbyMember | User, lobby: Lobby):
    from .routes import ws_url
    # the modal sits beside the page: .mg-page's stacking context paints it under the navbar
    return (*LobbyPage(
        GameShell(Game(reciever, lobby),
                  LobbyTools(reciever, lobby, HiveMindSettings(reciever, lobby))),
        hx_ext='ws', ws_connect=ws_url, user=reciever, no_image=True,
        title=f'Hive Mind lobby: {lobby.id}', page='hivemind'), PackSelectModal())
