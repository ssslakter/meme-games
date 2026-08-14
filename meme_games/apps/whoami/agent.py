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
        actions = []
        if target_uid: actions.append('whoami_write_card')
        actions.append('whoami_write_note')
        if state.phase == WhoAmIPhase.PLAYING and member.uid == state.current_turn_uid:
            if not state.ask_rejection(member, '?'):
                actions.append('whoami_ask_question')
            actions.append('whoami_end_turn')
        if state.question and state.question.answer is None and state.question.answerer_uid == member.uid:
            actions.append('whoami_answer_question')
        return actions

    def snapshot(self, lobby: Lobby, member: LobbyMember):
        state = lobby.state
        order = state.turn_order if state.phase == WhoAmIPhase.PLAYING else whoami_actions.order(lobby)
        target_uid = state.next_player(member.uid, order)

        def player_data(uid):
            candidate, data = lobby.members[uid], state.player(uid)
            result = {'id': uid, 'name': candidate.name, 'kind': candidate.user.kind,
                      'is_current_turn': uid == state.current_turn_uid,
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
                    'card_to_write': {'id': target_uid, 'name': lobby.members[target_uid].name,
                                      'text': state.player(target_uid).label_text} if target_uid else None},
            'players': [player_data(uid) for uid in order if uid in lobby.members],
            'question': asdict(state.question) if state.question else None,
            'questions_asked': state.questions_asked,
            'available_actions': self.available_actions(member, state, target_uid),
        }

    async def action(self, lobby: Lobby, member: LobbyMember, name: str, arguments: dict):
        actions = {
            'whoami_write_card': lambda: whoami_actions.write_card(
                lobby, member, str(arguments.get('text', ''))),
            'whoami_write_note': lambda: whoami_actions.write_note(
                lobby, member, str(arguments.get('text', ''))),
            'whoami_ask_question': lambda: whoami_actions.ask_question(
                lobby, member, str(arguments.get('question', ''))),
            'whoami_answer_question': lambda: whoami_actions.answer_question(
                lobby, member, str(arguments.get('answer', ''))),
            'whoami_end_turn': lambda: whoami_actions.end_turn(lobby, member),
        }
        handler = actions.get(name)
        if not handler: raise ActionRejected('Unknown action')
        return await handler()


register_agent_game(WHOAMI, WhoAmIAgentGame())
