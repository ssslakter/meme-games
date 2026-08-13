from meme_games.domain import Lobby, LobbyMember

__all__ = ['AgentGame', 'agent_games', 'register_agent_game']


class AgentGame:
    """The transport-facing boundary implemented by each agent-supported game."""

    def join(self, lobby: Lobby, member: LobbyMember):
        pass

    def snapshot(self, lobby: Lobby, member: LobbyMember) -> dict:
        raise NotImplementedError

    async def action(self, lobby: Lobby, member: LobbyMember, name: str, arguments: dict):
        raise NotImplementedError


agent_games: dict[str, AgentGame] = {}


def register_agent_game(game: str, adapter: AgentGame):
    agent_games[game] = adapter
