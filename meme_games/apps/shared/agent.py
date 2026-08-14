from meme_games.domain import Lobby, LobbyMember, lobby_events

__all__ = ['AgentGame', 'agent_games', 'register_agent_game']


class AgentGame:
    """The transport-facing boundary implemented by each agent-supported game."""

    # Topics every lobby publishes, whatever it is playing.
    GENERIC_TOPICS = {
        'roster': 'players joined, left, or switched between playing and watching',
        'game': 'the game was started, reset, or reconfigured',
        'turn': 'the turn moved on',
        'question': 'a question was asked or answered',
        'topic': 'the lobby topic changed',
    }

    def capture(self, lobby: Lobby, topics: frozenset[str]) -> dict:
        """What just happened, in full, recorded as it happens. An event may be read
        long afterwards, so nothing here may be deferred to a lookup at read time.
        Subclasses build on this - chat belongs to the lobby, not to any one game."""
        if 'chat' in topics and lobby.chat:
            message = lobby.chat[-1]
            return {'said': {'by': message.name, 'text': message.text}}
        return {}

    def render(self, member: LobbyMember, topics: set[str], facts: dict) -> list[str]:
        """The captured facts as this member is allowed to hear them. An event stream
        is how an agent follows the table, so it carries the content, not a nudge to
        go and fetch it."""
        lines = [text for topic, text in self.GENERIC_TOPICS.items() if topic in topics]
        if said := facts.get('said'):
            lines.append(f'{said["by"]} said in chat: "{said["text"]}"')
        return lines

    def join(self, lobby: Lobby, member: LobbyMember):
        pass

    def snapshot(self, lobby: Lobby, member: LobbyMember) -> dict:
        raise NotImplementedError

    async def action(self, lobby: Lobby, member: LobbyMember, name: str, arguments: dict):
        raise NotImplementedError


agent_games: dict[str, AgentGame] = {}


def register_agent_game(game: str, adapter: AgentGame):
    agent_games[game] = adapter


def _capture(lobby: Lobby, topics: frozenset[str]) -> dict:
    adapter = agent_games.get(lobby.current_game)
    return adapter.capture(lobby, topics) if adapter else {}


lobby_events.capture = _capture
