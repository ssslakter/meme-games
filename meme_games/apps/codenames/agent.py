from meme_games.apps.shared.actions import ActionRejected
from meme_games.apps.shared.agent import AgentGame, register_agent_game
from meme_games.domain import Lobby, LobbyMember

from .actions import codenames_actions
from .domain import CODENAMES, GamePhase, TeamColor

__all__ = ['CodenamesAgentGame']


class CodenamesAgentGame(AgentGame):
    @staticmethod
    def available_actions(member: LobbyMember, state) -> list[str]:
        team = state.team_of(member)
        spymaster = member.uid in state.spymasters
        if state.phase == GamePhase.WAITING:
            actions = ['codenames_join_team']
            if team: actions.append('codenames_set_role')
            if member.is_player: actions.append('codenames_spectate')
            return actions
        if state.phase == GamePhase.CLUE and team == state.turn and spymaster:
            return ['codenames_give_clue']
        if state.phase == GamePhase.GUESSING and team == state.turn and not spymaster:
            return ['codenames_reveal_card', 'codenames_end_turn']
        return []

    def snapshot(self, lobby: Lobby, member: LobbyMember):
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
            'available_actions': self.available_actions(member, state),
        }

    async def action(self, lobby: Lobby, member: LobbyMember, name: str, arguments: dict):
        if name == 'codenames_give_clue':
            try: number = int(arguments.get('number'))
            except (TypeError, ValueError): raise ActionRejected('number must be an integer')
            return await codenames_actions.give_clue(
                lobby, member, str(arguments.get('clue', '')), number)
        actions = {
            'codenames_join_team': lambda: codenames_actions.join_team(
                lobby, member, arguments.get('team', '')),
            'codenames_set_role': lambda: codenames_actions.set_role(
                lobby, member, arguments.get('role', '')),
            'codenames_reveal_card': lambda: codenames_actions.reveal_card(
                lobby, member, str(arguments.get('card_id', ''))),
            'codenames_end_turn': lambda: codenames_actions.end_turn(lobby, member),
            'codenames_spectate': lambda: codenames_actions.spectate(lobby, member),
        }
        handler = actions.get(name)
        if not handler: raise ActionRejected('Unknown action')
        return await handler()


register_agent_game(CODENAMES, CodenamesAgentGame())
