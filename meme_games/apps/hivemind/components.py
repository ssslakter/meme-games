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
        body = (H3('Everyone answers the same questions'),
                P('Up to six words each round. Every word somebody else also wrote scores '
                  'you a point; a word nobody shares scores nothing - so the most ordinary '
                  'answer wins.', cls=TextT.muted))
    else:
        body = (Div(Span(f'Round {state.round_number} of {state.total_rounds}',
                         cls='text-xs uppercase tracking-wide opacity-60'),
                    CircleTimer(state.timer.time, total=state.timer.total)
                        if state.seconds and state.phase == HivePhase.WRITING else None,
                    cls='flex items-center justify-between gap-3'),
                H2(state.question, cls='m-0'))
    return Card(*body, id='hivemind-question', cls='mg-panel text-center',
                body_cls='space-y-3 p-6', data_ui='hivemind-question', **kwargs)


def Status(reciever: LobbyMember | User, lobby: Lobby, **kwargs):
    """Who is done, as a count only: a name would hint at what they wrote."""
    state: HiveMindState = lobby.state
    uids = player_uids(lobby)
    done = sum(1 for uid in uids if state.is_ready(uid))
    count = ('Everyone is done' if state.all_ready(uids) else
             f'{done} of {len(uids)} done' if uids else 'Nobody is playing yet')
    return Div(Span(count, cls='font-medium'),
               Span('the round closes when everyone is done, or when the clock runs out',
                    cls=(TextT.muted, TextT.sm)),
               id='hivemind-status', cls='space-y-1', data_ui='hivemind-status', **kwargs)


def AnswerArea(reciever: LobbyMember | User, lobby: Lobby, **kwargs):
    """Six cells that save as you type, and one button that says you are finished."""
    from .routes import set_ready, set_word
    state: HiveMindState = lobby.state
    if state.phase != HivePhase.WRITING or not is_player(reciever): return None
    words = state.words(reciever.uid)
    ready = state.is_ready(reciever.uid)
    cells = [Input(name='text', value=words[index] if index < len(words) else '',
                   maxlength=ANSWER_MAX, autocomplete='off', readonly=ready,
                   placeholder=f'word {index + 1}',
                   hx_post=None if ready else set_word.to(index=index),
                   hx_trigger=None if ready else 'input changed delay:600ms',
                   hx_swap='none', cls=classes('uk-input w-full', 'opacity-60' if ready else None),
                   data_ui='hivemind-cell')
             for index in range(ANSWERS_PER_ROUND)]
    return Card(
        DivLAligned(H3('Your list', cls='m-0'),
                    Span(f'{len(words)} of {ANSWERS_PER_ROUND} filled',
                         cls=(TextT.muted, TextT.sm))),
        Div(*cells, cls='grid grid-cols-2 gap-2 sm:grid-cols-3'),
        Button('Done' if not ready else 'Not done yet',
               hx_post=set_ready.to(is_ready=not ready), hx_swap='none',
               cls=(ButtonT.primary if not ready else ButtonT.default, 'w-full')),
        Status(reciever, lobby),
        id='hivemind-answers', cls='mg-panel mg-hivemind-answer', body_cls='space-y-3 p-4',
        data_ui='hivemind-answer', **kwargs)


def RevealBoard(reciever: LobbyMember | User, lobby: Lobby, **kwargs):
    """Every player's list with a mark on each word that agreed - and the words are
    editable, so a typo or a paraphrase can be made to count before the scores settle."""
    from .routes import edit_word
    state: HiveMindState = lobby.state
    played = state.last()
    if state.phase != HivePhase.REVEAL or not played: return None
    agreed, points = played.matched_positions(), played.points()

    def cell(uid: str, index: int, word: str):
        matched = (uid, index) in agreed
        editable = isinstance(reciever, LobbyMember) and (reciever.uid == uid or reciever.is_host)
        return Div(
            UkIcon('check' if matched else 'minus', width=14, height=14, cls='shrink-0'),
            Input(name='text', value=word, maxlength=ANSWER_MAX, readonly=not editable,
                  hx_post=edit_word.to(uid=uid, index=index) if editable else None,
                  hx_trigger='input changed delay:600ms' if editable else None,
                  hx_swap='none',
                  cls=classes('mg-hivemind-word w-full bg-transparent px-1',
                              'font-medium' if matched else 'opacity-60')),
            title=('Somebody else wrote this too' if matched
                   else 'Nobody else wrote this - no point'),
            cls=classes('flex items-center gap-1 rounded border px-2 py-1',
                        'border-primary/60 bg-primary/10' if matched else 'border-border'),
            data_ui='hivemind-word', data_matched='true' if matched else 'false')

    rows = [Div(DivLAligned(MemberName(reciever, member, cls='mg-hivemind-name'),
                            Span(f'{points.get(uid, 0)} this round', cls=(TextT.muted, TextT.sm))),
                Div(*[cell(uid, index, word)
                      for index, word in enumerate(played.answers.get(uid, []))],
                    cls='flex flex-wrap gap-1'),
                cls='space-y-1', data_ui='hivemind-row')
            for uid, member in ((member.uid, member) for member in lobby.sorted_members()
                                if member.is_player and member.uid in played.answers)]

    shared = [Div(Span(word, cls='font-medium'),
                  Span(', '.join(member.name for uid, member in
                                 ((uid, lobby.members.get(uid)) for uid in uids) if member),
                       cls=(TextT.muted, TextT.sm)),
                  cls='flex items-center justify-between gap-2', data_ui='hivemind-agreed')
              for word, uids in played.matches().items()]
    return Card(
        H5(f'What everyone wrote: {played.question}'),
        Div(*rows or [P('Nobody wrote anything this round.', cls=TextT.muted)],
            cls='space-y-3'),
        Div(H5('Words that agreed', cls='m-0'), *shared, cls='space-y-1') if shared
            else P('No two players wrote the same word.', cls=TextT.muted),
        P('Any word can be rewritten here: fix a typo, or reword a paraphrase so it counts. '
          'The scores follow the words.', cls=(TextT.muted, TextT.sm)),
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
                P('Each round everyone answers the same question with up to six words. '
                  'A word somebody else also wrote scores you a point; a word nobody '
                  'shares scores nothing.', cls=TextT.muted),
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
    """Host controls: start, move the round on, restart, and the deck and clock."""
    if not is_host(reciever): return None
    from .routes import advance, restart_game, start_game, update_settings
    state: HiveMindState = lobby.state
    waiting = state.phase == HivePhase.WAITING
    if waiting:
        control = Button(UkIcon('play', cls='mr-2'), 'Start game', hx_post=start_game,
                         hx_swap='none', disabled=len(player_uids(lobby)) < 2,
                         cls=(ButtonT.primary, 'w-full'))
    else:
        label = 'Reveal now' if state.phase == HivePhase.WRITING else (
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
                 LabelInput('Seconds per round (0 = no clock)', name='seconds', type='number',
                            min=0, max=SECONDS_MAX, value=str(state.seconds),
                            disabled=not waiting),
                 Button('Save rounds and clock', type='submit', disabled=not waiting,
                        cls=(ButtonT.default, 'w-full')),
                 hx_post=update_settings, hx_swap='none', cls='space-y-2'),
            cls='space-y-2'),
        id='hivemind-settings', cls='space-y-3', data_ui='hivemind-settings', **kwargs)


def Game(reciever: LobbyMember | User, lobby: Lobby, **kwargs):
    """The board. The scoreboard rides on the left; what a receiver may see of the round
    depends on its phase, and words are on the table only once it has closed."""
    state: HiveMindState = lobby.state
    return Div(
        Scoreboard(reciever, lobby),
        Div(QuestionCard(lobby), AnswerArea(reciever, lobby), RevealBoard(reciever, lobby),
            JoinCard(reciever, lobby), cls='mx-auto w-full max-w-3xl space-y-4'),
        id='game',
        cls=classes('mg-game mg-game-hivemind grid min-w-0 items-start gap-6 lg:grid-cols-[18rem_minmax(0,1fr)]',
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
