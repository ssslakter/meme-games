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

    # handled below with their own wording, so the generic one-liners are dropped
    DETAILED = frozenset({'game', 'roster', 'turn'})

    def capture(self, lobby: Lobby, topics: frozenset[str]) -> dict:
        state = lobby.state
        name = lambda uid: lobby.members[uid].name if uid in lobby.members else 'someone'
        facts = super().capture(lobby, topics)
        facts.update({
            'phase': state.phase.value,
            'turn': state.turn.value if state.turn else None,
            'winner': state.winner.value if state.winner else None,
            'clue': {'word': state.clue, 'number': state.clue_number,
                     'guesses_left': state.guesses_left} if state.clue else None,
            'teams': {team.value: [{'name': name(uid),
                                    'role': 'spymaster' if uid in state.spymasters else 'operative'}
                                   for uid in state.team_uids(team) if uid in lobby.members]
                      for team in TeamColor},
            # a revealed card is public, and so is how many each team has left
            'remaining': {team.value: sum(not card.revealed and card.color == team.card_color
                                          for card in state.board)
                          for team in TeamColor},
        })
        if 'clue' in topics and state.turn:
            giver = next((uid for uid in state.team_uids(state.turn) if uid in state.spymasters), None)
            if giver: facts['clue_by'] = name(giver)
        if 'reveal' in topics and state.last_revealed:
            card = next((card for card in state.board if card.id == state.last_revealed), None)
            if card: facts['revealed'] = {'word': card.word, 'color': card.color.value,
                                          'team': state.last_revealed_by}
        return facts

    def render(self, member: LobbyMember, topics: set[str], facts: dict) -> list[str]:
        '''Everything a player at the table would see happen. The key stays out of it:
        only cards already turned over are named with their colour.'''
        lines = super().render(member, topics - self.DETAILED, facts)
        turn, phase = facts.get('turn'), facts.get('phase')
        if 'start' in topics: lines.append(f'the game started, {turn} team goes first')
        if 'restart' in topics: lines.append('the game was reset, teams are open again')
        if 'clue' in topics and facts.get('clue'):
            clue, giver = facts['clue'], facts.get('clue_by', f'the {turn} spymaster')
            lines.append(f'{giver} gave the {turn} team the clue "{clue["word"]}" for {clue["number"]}')
        if revealed := facts.get('revealed'):
            lines.append(f'the {revealed["team"]} team turned over "{revealed["word"]}"'
                         f' - it was {revealed["color"]}')
            # a wrong colour ends the turn inside the same event
            if not facts.get('winner') and revealed['team'] != turn:
                lines.append(f'that ended their turn, it passes to the {turn} team')
        elif 'turn' in topics and not facts.get('winner'):
            lines.append(f'it is now the {turn} team\'s turn to give a clue')
        if facts.get('winner'): lines.append(f'the game is over - {facts["winner"]} team won')
        if topics & {'roster', 'roles', 'start'}:
            lines.append('teams: ' + '; '.join(
                f'{color} - ' + (', '.join(f'{p["name"]} ({p["role"]})' for p in players) or 'nobody')
                for color, players in facts.get('teams', {}).items()))
        if phase in ('clue', 'guessing') and (remaining := facts.get('remaining')):
            lines.append('cards still hidden: ' +
                         ', '.join(f'{color} {count}' for color, count in remaining.items()))
        return lines

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
