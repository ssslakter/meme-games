from ...shared import *
from ...user import *
from ..domain import *
from meme_games.domain import User, LobbyMember
from .basic import *


def NotesCard(reciever: LobbyMember | User, owner: LobbyMember, data: PlayerNotes, state: WhoAmIState):
    from ..routes import notes
    if not notes_visible(reciever, owner, state): return None
    own = reciever == owner
    body = (TextArea(data.notes, name='text', placeholder='Your notes', maxlength=NOTES_MAX, cls='mg-notes-input',
                     hx_post=notes, hx_trigger='input changed delay:500ms', hx_swap='none')
            if own else
            Div(data.notes, cls='mg-notes-text'))
    return Div(
        Div('Notes' if own else Span(MemberName(reciever, owner), "'s notes"), cls='mg-notes-title'),
        body,
        cls='mg-notes', data_notes=owner.uid, data_ui='player-notes', data_nodrag='true',
    )


def SharedNotesCard(reciever: LobbyMember | User, owner: LobbyMember, data: PlayerNotes, state: WhoAmIState):
    if reciever == owner: return None
    note = NotesCard(reciever, owner, data, state)
    if not note: return None
    return Div(UkIcon('file-text', width=24, height=24), note,
               cls='mg-shared-notes', title=f"{owner.name}'s notes", data_nodrag='true')


def NotesBlock(reciever: LobbyMember | User, lobby: Lobby):
    if not isinstance(reciever, LobbyMember) or not reciever.is_player: return None
    note = NotesCard(reciever, reciever, lobby.state.player(reciever.uid), lobby.state)
    return Div(note, id='notes-block', cls='draggable-panel mg-floating-notes')


def QuestionPanel(reciever: LobbyMember | User, owner: LobbyMember, lobby: Lobby, **kwargs):
    from ..routes import answer_question, ask_question
    state: WhoAmIState = lobby.state
    content = None
    if state.phase == WhoAmIPhase.PLAYING and owner.uid == state.current_turn_uid:
        answerer_uid = state.previous_player(owner.uid)
        answerer = lobby.members.get(answerer_uid)
        structured = owner.user.kind == 'agent' or answerer and answerer.user.kind == 'agent'
        question = state.question
        can_type = (structured and isinstance(reciever, LobbyMember) and reciever == owner and
                    owner.user.kind != 'agent' and answerer and answerer.user.kind == 'agent' and
                    not state.ask_rejection(owner, '?'))
        ask_form = (Form(
            Input(name='text', required=True, maxlength=QUESTION_MAX, autocomplete='off', placeholder='Ask a yes/no question',
                  cls='uk-input min-w-0 flex-1'),
            Button('Ask', cls=(ButtonT.primary, 'shrink-0 px-3')),
            hx_post=ask_question, hx_swap='none', cls='flex gap-2') if can_type else None)
        if structured and question:
            answer = question.answer.replace('_', ' ').title() if question.answer else None
            buttons = None
            if (question.answer is None and isinstance(reciever, LobbyMember) and
                    reciever.uid == answerer_uid and owner.user.kind == 'agent'):
                buttons = Div(*[
                    Button(label, hx_post=answer_question.to(answer=value), hx_swap='none',
                           cls=(ButtonT.default, 'px-3 py-1.5'))
                    for value, label in [('yes', 'Yes'), ('no', 'No'), ('not_sure', 'Not sure')]],
                    cls='flex flex-wrap justify-center gap-2')
            content = Div(P(question.text, cls='m-0 font-medium'),
                          Span(answer, cls='text-sm font-semibold') if answer else buttons, ask_form,
                          cls='space-y-2')
        elif ask_form: content = ask_form
    return Div(content, id=f'whoami-question-{owner.uid}',
               cls='mg-question-bubble' if content else '', data_nodrag='true', **kwargs)
