import json

from ..shared import *
from ..user import *
from meme_games.domain import Lobby as _Lobby, is_host, is_player
from ..word_packs.components import PacksSelect, WordPackEditor, wordpack_manager
from .domain import *

Lobby = _Lobby[HiveMindState]


def player_uids(lobby: Lobby) -> list[str]:
    return [member.uid for member in lobby.sorted_members() if member.is_player]


def players(lobby: Lobby) -> list:
    return [member for member in lobby.sorted_members() if member.is_player]


def Question(lobby: Lobby):
    state: HiveMindState = lobby.state
    if state.phase == HivePhase.WAITING: return None
    ticking = state.seconds and state.phase == HivePhase.WRITING
    goal = None
    if state.alternate:
        unique = (state.last().unique if state.phase == HivePhase.REVEAL and state.last()
                  else state.round_is_unique())
        goal = Span('Different' if unique else 'Same', data_ui='hivemind-goal',
                    cls='text-xs font-semibold uppercase tracking-wide')
    return Div(
        Div(Span(f'{state.round_number} / {state.total_rounds}',
                 cls='text-xs uppercase tracking-wide opacity-60'),
            goal,
            CircleTimer(state.timer.time, total=state.timer.total) if ticking else None,
            cls='flex items-center justify-between gap-3'),
        H2(state.question, cls='m-0 text-center'),
        id='hivemind-question', cls='space-y-2', data_ui='hivemind-question')


def Status(lobby: Lobby, **kwargs):
    """A count only. A name would say who has already stopped writing."""
    state: HiveMindState = lobby.state
    if state.phase != HivePhase.WRITING: return None
    uids = player_uids(lobby)
    done = sum(1 for uid in uids if state.is_ready(uid))
    text = ('Everyone is done' if state.all_ready(uids) else
            f'{done} of {len(uids)} done' if uids else 'Nobody is playing yet')
    return Span(text, id='hivemind-status', cls='text-sm opacity-60', data_ui='hivemind-status', **kwargs)


def AnswerArea(reciever: LobbyMember | User, lobby: Lobby):
    from .routes import set_ready, set_word
    state: HiveMindState = lobby.state
    if state.phase != HivePhase.WRITING or not is_player(reciever): return None
    words = state.answers.get(reciever.uid, [])
    ready = state.is_ready(reciever.uid)
    cells = [Input(name='words', value=words[index] if index < len(words) else '',
                   maxlength=ANSWER_MAX, autocomplete='off', readonly=ready,
                   placeholder=str(index + 1),
                   hx_post=None if ready else set_word.to(index=index),
                   hx_trigger=None if ready else 'input changed delay:400ms, blur',
                   hx_swap='none', cls=classes('uk-input w-full', 'opacity-60' if ready else None),
                   data_ui='hivemind-cell')
             for index in range(ANSWERS_PER_ROUND)]
    grid = Div(*cells, cls='grid grid-cols-2 gap-2 sm:grid-cols-3')
    if ready:
        controls = (grid, Button('Not done yet', hx_post=set_ready.to(is_ready='false'),
                                 hx_target='#hivemind-answers', hx_swap='outerHTML',
                                 cls=(ButtonT.default, 'w-full')))
    else:
        # Done posts the cells themselves, so the last keystrokes are not lost to the debounce.
        controls = (Form(grid, Button('Done', type='submit', cls=(ButtonT.primary, 'w-full')),
                         hx_post=set_ready.to(is_ready='true'),
                         hx_target='#hivemind-answers', hx_swap='outerHTML', cls='space-y-3'),)
    return Div(*controls, id='hivemind-answers', cls='space-y-3', data_ui='hivemind-answer')


def _slots(words) -> list[str]:
    words = list(words or [])[:ANSWERS_PER_ROUND]
    return words + [''] * (ANSWERS_PER_ROUND - len(words))


def RevealSync(lobby: Lobby, oob: bool = False):
    """The cells and the scores, without the inputs. A focused cell is left alone."""
    state: HiveMindState = lobby.state
    played = state.last()
    if state.phase != HivePhase.REVEAL or not played: return None
    agreed, scored = played.matched_positions(), played.scored_positions()
    points = played.points()
    cells = []
    for member in players(lobby):
        for index, word in enumerate(_slots(played.answers.get(member.uid, []))):
            cells.append({'id': f'hive-word-{member.uid}-{index}', 'value': word,
                          'matched': (member.uid, index) in agreed,
                          'scored': (member.uid, index) in scored})
    totals = state.totals()
    payload = json.dumps({
        'cells': cells,
        'round': {member.uid: points.get(member.uid, 0) for member in players(lobby)},
        'total': {member.uid: totals.get(member.uid, 0) for member in players(lobby)},
        'winners': [member.uid for member in players(lobby)
                    if state.finished and totals.get(member.uid, 0)
                    and totals.get(member.uid, 0) == max(totals.values(), default=0)],
    })
    return Div(id='hive-sync', data_payload=payload, data_ui='hive-sync',
               hx_swap_oob='outerHTML' if oob else None,
               _='init call hiveSync(my.dataset.payload)')


def RevealBoard(reciever: LobbyMember | User, lobby: Lobby):
    from .routes import edit_word
    state: HiveMindState = lobby.state
    played = state.last()
    if state.phase != HivePhase.REVEAL or not played: return None
    agreed, scored = played.matched_positions(), played.scored_positions()
    points = played.points()

    def cell(uid: str, index: int, word: str):
        matched = (uid, index) in agreed
        editable = isinstance(reciever, LobbyMember) and (reciever.uid == uid or reciever.is_host)
        return Input(name='text', value=word, maxlength=ANSWER_MAX, readonly=not editable,
                     id=f'hive-word-{uid}-{index}',
                     hx_post=edit_word.to(uid=uid, index=index) if editable else None,
                     hx_trigger='input changed delay:400ms, blur' if editable else None,
                     hx_swap='none',
                     cls=classes('uk-input mg-hive-word',
                                 'mg-hive-match' if (uid, index) in scored else None),
                     data_ui='hivemind-word', data_matched='true' if matched else 'false')

    rows = []
    for member in players(lobby):
        uid = member.uid
        words = _slots(played.answers.get(uid, []))
        rows.append(Div(
            Div(MemberName(reciever, member, cls='mg-hivemind-name'),
                Span(points.get(uid, 0), id=f'hive-round-{uid}', cls='tabular-nums font-semibold'),
                cls='flex items-center justify-between gap-2'),
            Div(*[cell(uid, index, word) for index, word in enumerate(words)],
                cls='grid grid-cols-2 gap-2 sm:grid-cols-3'),
            cls='space-y-2', data_ui='hivemind-row'))
    return Div(*rows, RevealSync(lobby), id='hivemind-reveal', cls='space-y-4',
               data_ui='hivemind-reveal')


def RoundControl(reciever: LobbyMember | User, lobby: Lobby):
    """The one button that moves a round. New game, while a match is on, stays in settings."""
    if not is_host(reciever): return None
    from .routes import advance, restart_game
    state: HiveMindState = lobby.state
    if state.phase == HivePhase.WRITING:
        return Button('Reveal now', hx_post=advance, hx_swap='none',
                      cls=(ButtonT.default, 'w-full'), data_ui='hivemind-reveal-now')
    if state.phase == HivePhase.REVEAL and not state.finished:
        return Button('Next round', hx_post=advance, hx_swap='none',
                      cls=(ButtonT.primary, 'w-full'), data_ui='hivemind-next')
    if state.finished:
        return Button('New game', hx_post=restart_game, hx_swap='none',
                      cls=(ButtonT.primary, 'w-full'), data_ui='hivemind-new')
    return None


def Waiting(reciever: LobbyMember | User, lobby: Lobby):
    from .routes import play, start_game
    if lobby.state.phase != HivePhase.WAITING: return None
    n = len(player_uids(lobby))
    if not is_player(reciever) and not lobby.locked:
        action = Button('Join', hx_post=play, hx_swap='none',
                        cls=(ButtonT.primary, 'w-full max-w-xs'), data_ui='hivemind-join')
    elif is_host(reciever):
        action = Button('Start', hx_post=start_game, hx_swap='none', disabled=n < 2,
                        cls=(ButtonT.primary, 'w-full max-w-xs'), data_ui='hivemind-start')
    else:
        action = P('Waiting for the host', cls=(TextT.muted, 'm-0'))
    return Div(action, id='hivemind-waiting',
               cls='flex min-h-48 items-center justify-center', data_ui='hivemind-waiting')


def Stage(reciever: LobbyMember | User, lobby: Lobby):
    return Div(Question(lobby), Waiting(reciever, lobby), AnswerArea(reciever, lobby),
               Status(lobby), RevealBoard(reciever, lobby), RoundControl(reciever, lobby),
               cls='mg-hive-stage mx-auto flex w-full max-w-3xl flex-col gap-4')


def Scoreboard(reciever: LobbyMember | User, lobby: Lobby):
    state: HiveMindState = lobby.state
    totals = state.totals()
    seated = sorted(players(lobby), key=lambda member: (-totals.get(member.uid, 0), member.name))
    top = max((totals.get(member.uid, 0) for member in seated), default=0)
    winners = {member.uid for member in seated
               if state.finished and top and totals.get(member.uid, 0) == top}
    rows = [Div(MemberName(reciever, member, cls='mg-hivemind-name'),
                Span(totals.get(member.uid, 0), id=f'hive-total-{member.uid}',
                     cls='tabular-nums font-semibold', data_ui='hive-total'),
                cls='flex items-center justify-between gap-2',
                data_ui='hivemind-score-row', data_uid=member.uid,
                data_points=str(totals.get(member.uid, 0)),
                data_winner='true' if member.uid in winners else None)
            for member in seated]
    return Card(Div(H5('Score', cls='m-0'),
                    Span(f'{len(state.revealed)}/{state.total_rounds}',
                         cls='tabular-nums text-sm opacity-60')),
                Div(*rows or [P('No players', cls=(TextT.muted, 'm-0 text-sm'))], cls='space-y-2'),
                id='hivemind-scoreboard', cls='mg-panel mg-hive-score shrink-0',
                body_cls='space-y-3 p-4', data_ui='hivemind-scoreboard')


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
    if not is_host(reciever): return None
    from .routes import restart_game, update_settings
    state: HiveMindState = lobby.state
    waiting = state.phase == HivePhase.WAITING
    return Div(
        Button('New game', hx_post=restart_game, hx_swap='none',
               hx_confirm='Clear the scores?', cls=(ButtonT.destructive, 'w-full'))
            if not waiting and not state.finished else None,
        PackSelectButton(state),
        Form(LabelInput('Rounds', name='total_rounds', type='number', min=1, max=ROUNDS_MAX,
                        value=str(state.total_rounds), disabled=not waiting),
             LabelInput('Seconds (0 = no clock)', name='seconds', type='number',
                        min=0, max=SECONDS_MAX, value=str(state.seconds), disabled=not waiting),
             Div(CheckboxX(id='hive-alternate', name='alternate', value='1',
                           checked=state.alternate, disabled=not waiting),
                 FormLabel('Alternate same / different', fr='hive-alternate', cls='m-0'),
                 cls='flex items-center gap-2'),
             Button('Save', type='submit', disabled=not waiting, cls=(ButtonT.default, 'w-full')),
             hx_post=update_settings, hx_swap='none', cls='space-y-2'),
        id='hivemind-settings', cls='space-y-3', data_ui='hivemind-settings', **kwargs)


def Game(reciever: LobbyMember | User, lobby: Lobby, **kwargs):
    state: HiveMindState = lobby.state
    return Div(
        GameRail(Scoreboard(reciever, lobby),
                 ChatPanel(reciever, lobby, cls='mg-hive-chat'),
                 cls='mg-hive-rail'),
        Stage(reciever, lobby),
        id='game',
        cls=classes('mg-game mg-game-hivemind grid min-w-0 items-start gap-6 lg:grid-cols-[20rem_minmax(0,1fr)]',
                    kwargs.pop('cls', '')),
        data_ui='game', data_game=HIVEMIND, data_phase=state.phase.value, **kwargs)


def MainBlock(reciever: LobbyMember | User, lobby: Lobby):
    from .routes import ws_url
    # the modal sits beside the page: .mg-page's stacking context paints it under the navbar
    return (*LobbyPage(
        GameShell(Game(reciever, lobby),
                  LobbyTools(reciever, lobby, HiveMindSettings(reciever, lobby), show_chat=False)),
        hx_ext='ws', ws_connect=ws_url, user=reciever, no_image=True,
        title=f'Hive Mind lobby: {lobby.id}', page='hivemind'),
        PackSelectModal(),
        # A cell you are typing in is not replaced. Everyone else sees the saved text.
        Script('''function hiveSync(raw) {
  const data = typeof raw === "string" ? JSON.parse(raw) : raw;
  for (const cell of data.cells || []) {
    const el = document.getElementById(cell.id);
    if (!el) continue;
    if (document.activeElement !== el && el.value !== cell.value) el.value = cell.value;
    el.dataset.matched = cell.matched ? "true" : "false";
    el.classList.toggle("mg-hive-match", !!cell.scored);
  }
  const paint = (map, prefix) => { for (const uid in map || {}) {
    const el = document.getElementById(prefix + uid); if (el) el.textContent = map[uid]; } };
  paint(data.round, "hive-round-"); paint(data.total, "hive-total-");
  if (!data.winners) return;
  document.querySelectorAll("[data-ui=hivemind-score-row]").forEach(row => {
    row.dataset.winner = data.winners.indexOf(row.dataset.uid) >= 0 ? "true" : "false"; });
}'''))
