from dataclasses import asdict

from meme_games.apps.shared.actions import ActionRejected
from meme_games.apps.shared.agent import AgentGame, register_agent_game
from meme_games.domain import Lobby, LobbyMember

from .actions import whoami_actions
from .domain import WHOAMI, WhoAmIPhase

__all__ = ['WhoAmIAgentGame']


class WhoAmIAgentGame(AgentGame):
    @staticmethod
    def join(lobby: Lobby, member: LobbyMember):
        member.play()
        lobby.state.player(member.uid)

    @staticmethod
    def available_actions(member: LobbyMember, state, target_uid: str | None) -> list[str]:
        if not member.is_player: return []
        actions = ['whoami_write_notes']
        if target_uid: actions.append('whoami_write_card')
        if state.phase == WhoAmIPhase.PLAYING and member.uid == state.current_turn_uid:
            if not state.ask_rejection(member, '?'):
                actions.append('whoami_ask_question')
            actions.append('whoami_end_turn')
        if state.question and state.question.answer is None and state.question.answerer_uid == member.uid:
            actions.append('whoami_answer_question')
        return actions

    # handled below with their own wording, so the generic one-liners are dropped
    DETAILED = frozenset({'topic', 'turn', 'question', 'game', 'roster'})

    def capture(self, lobby: Lobby, topics: frozenset[str]) -> dict:
        state = lobby.state
        order = state.turn_order if state.phase == WhoAmIPhase.PLAYING else whoami_actions.order(lobby)
        name = lambda uid: lobby.members[uid].name if uid in lobby.members else 'someone'
        facts = super().capture(lobby, topics)
        facts.update({'topic': state.config.topic.strip() or 'Everything', 'phase': state.phase.value,
                      'current_turn': name(state.current_turn_uid) if state.current_turn_uid else None})
        if state.question:
            question = state.question
            facts['question'] = {'text': question.text, 'asked_by': name(question.asker_uid),
                                 'answered_by': name(question.answerer_uid), 'answer': question.answer,
                                 'questions_left': state.questions_left(question.asker_uid)}
        if topics & {'roster', 'game'}:
            facts['players'] = [{'id': p.uid, 'name': p.name, 'guessed': state.player(p.uid).guessed,
                                 'has_card': bool(state.player(p.uid).label_text.strip())}
                                for p in lobby.sorted_members() if p.is_player]
        for topic in sorted(topics):
            kind, _, uid = topic.partition(':')
            if uid not in lobby.members: continue
            if kind == 'card':
                facts.setdefault('cards', {})[uid] = {
                    'owner': name(uid), 'author': name(state.previous_player(uid, order)),
                    'text': state.player(uid).label_text}
            elif kind == 'notes':
                facts.setdefault('notes', {})[uid] = {
                    'owner': name(uid), 'text': state.player(uid).notes,
                    'private': state.config.private_notes}
        return facts

    def render(self, member: LobbyMember, topics: set[str], facts: dict) -> list[str]:
        '''The whole table as this player may hear it: what was said, written and
        answered, with only their own card held back.'''
        lines = super().render(member, topics - self.DETAILED, facts)
        if 'topic' in topics:
            lines.append(f'the topic is now "{facts.get("topic", "Everything")}" - any card written '
                         'under the previous topic no longer fits and should be rewritten')
        for uid, card in facts.get('cards', {}).items():
            if uid == member.uid:
                lines.append(f"{card['author']} wrote your card - you are the one player who cannot see it")
            else:
                lines.append(f"{card['author']} wrote \"{card['text']}\" on {card['owner']}'s card")
        for uid, note in facts.get('notes', {}).items():
            if uid == member.uid: lines.append(f"your notes now read \"{note['text']}\"")
            elif note.get('private'): lines.append(f"{note['owner']} updated their notes, which are private")
            else: lines.append(f"{note['owner']} now has these notes: \"{note['text']}\"")
        question = facts.get('question')
        if 'question' in topics and question:
            if question.get('answer'):
                left = question.get('questions_left', 0)
                consequence = (f"{question['asked_by']} may ask "
                               f"{left} more question{'' if left == 1 else 's'} this turn"
                               if left else f"{question['asked_by']} must end their turn now")
                lines.append(f"{question['answered_by']} answered \"{question['text']}\" with "
                             f"{question['answer'].replace('_', ' ')} - {consequence}")
            else:
                lines.append(f"{question['asked_by']} asked \"{question['text']}\" - "
                             f"{question['answered_by']} has to answer it")
        if 'turn' in topics:
            turn = facts.get('current_turn')
            lines.append(f"it is {'your' if turn == member.name else turn + chr(39) + 's'} turn now"
                         if turn else 'nobody is on turn')
        if topics & {'game', 'roster'}:
            players = facts.get('players', [])
            lines.append(f"the game is {facts.get('phase', 'waiting')}; players: " +
                         ', '.join(f"{p['name']}"
                                   f"{' (guessed)' if p['guessed'] else '' if p['has_card'] else ' (no card yet)'}"
                                   for p in players))
        return lines

    def snapshot(self, lobby: Lobby, member: LobbyMember):
        state = lobby.state
        order = state.turn_order if state.phase == WhoAmIPhase.PLAYING else whoami_actions.order(lobby)
        target_uid = state.next_player(member.uid, order)

        def player_data(uid):
            candidate, data = lobby.members[uid], state.player(uid)
            result = {'id': uid, 'name': candidate.name, 'kind': candidate.user.kind,
                      'is_current_turn': uid == state.current_turn_uid,
                      'guessed': data.guessed,
                      'has_card': bool(data.label_text.strip())}
            if uid != member.uid: result['card'] = data.label_text
            if uid == member.uid or not state.config.private_notes: result['notes'] = data.notes
            return result

        return {
            'lobby_id': lobby.id,
            'game': WHOAMI,
            'revision': lobby.revision,
            'topic': state.config.topic.strip() or 'Everything',
            'phase': state.phase.value,
            'you': {'id': member.uid, 'name': member.name,
                    'is_current_turn': member.uid == state.current_turn_uid,
                    'questions_left': state.questions_left(member.uid),
                    'card_to_write': {
                        'id': target_uid, 'name': lobby.members[target_uid].name,
                        'text': state.player(target_uid).label_text,
                        'written_under_an_older_topic': state.config.card_is_stale(state.player(target_uid)),
                    } if target_uid else None},
            'players': [player_data(uid) for uid in order if uid in lobby.members],
            'question': asdict(state.question) if state.question else None,
            'questions_asked': state.questions_asked,
            'available_actions': self.available_actions(member, state, target_uid),
        }

    async def action(self, lobby: Lobby, member: LobbyMember, name: str, arguments: dict):
        actions = {
            'whoami_write_card': lambda: whoami_actions.write_card(
                lobby, member, str(arguments.get('text', ''))),
            'whoami_ask_question': lambda: whoami_actions.ask_question(
                lobby, member, str(arguments.get('question', ''))),
            'whoami_answer_question': lambda: whoami_actions.answer_question(
                lobby, member, str(arguments.get('answer', ''))),
            'whoami_end_turn': lambda: whoami_actions.end_turn(lobby, member),
            'whoami_write_notes': lambda: whoami_actions.write_note(
                lobby, member, str(arguments.get('text', ''))),
        }
        handler = actions.get(name)
        if not handler: raise ActionRejected('Unknown action')
        return await handler()


register_agent_game(WHOAMI, WhoAmIAgentGame())
