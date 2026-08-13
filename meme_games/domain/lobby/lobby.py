
__all__ = ['Lobby', 'LobbyRepo', 'MemberRepo', 'is_player', 'is_host',
           'GameSpec', 'GAME_REGISTRY', 'register_game', 'BASIC_GAME']

import json
from meme_games.core import *
from ..user import *
from .member import *


logger = logging.getLogger(__name__)


@dataclass
class GameSpec:
    '''How a lobby runs one game: what its state looks like and whether it outlives memory.'''
    name: str
    state_cls: Optional[type] = None
    persist: bool = False

    def new_state(self): return self.state_cls() if self.state_cls else None

    def to_dict(self, state) -> dict:
        return state.to_dict() if hasattr(state, 'to_dict') else asdict(state)

    def from_dict(self, data: dict):
        if hasattr(self.state_cls, 'from_dict'): return self.state_cls.from_dict(data)
        return self.state_cls(**data)


BASIC_GAME = 'lobby'
GAME_REGISTRY: dict[str, GameSpec] = {BASIC_GAME: GameSpec(BASIC_GAME)}


def register_game(name: str, state_cls: Optional[type] = None, persist: bool = False) -> GameSpec:
    '''Register a game a lobby can switch to. `persist` keeps its state in the database.'''
    GAME_REGISTRY[name] = GameSpec(name, state_cls, persist)
    return GAME_REGISTRY[name]



@dataclass
class Lobby(Model):
    '''A room of members that can switch between games, keeping everyone in place.'''
    _ignore = ('members', 'host', 'states')

    id: str = field(default_factory=random_id)
    locked: bool = False # TODO move locked to game state
    background_url: Optional[str] = None
    host: Optional[LobbyMember] = None
    members: dict[str, LobbyMember] = field(default_factory=dict)
    last_active: dt.datetime = field(default_factory=dt.datetime.now)
    current_game: str = BASIC_GAME
    states: dict[str, Any] = field(default_factory=dict)
    states_json: str = ''
    persistent: bool = False # whether the lobby should be saved in the database

    def __post_init__(self):
        if isinstance(self.last_active, str):
            self.last_active = dt.datetime.fromisoformat(self.last_active)

    @property
    def state(self):
        '''State of the game currently being played, or None for a plain lobby.'''
        return self.states.get(self.current_game)

    def play_game(self, name: str):
        '''Switch to `name`, keeping every member and the state of the game they left.'''
        if name not in GAME_REGISTRY: raise ValueError(f'Unknown game {name}, available: {list(GAME_REGISTRY)}')
        self.current_game = name
        if name not in self.states:
            state = GAME_REGISTRY[name].new_state()
            if state is not None: self.states[name] = state
        return self.state

    def sorted_members(self):
        '''lobby members sorted by `joined_at` date'''
        for m in sorted(self.members.values(), key=lambda m: m.joined_at): yield m

    def set_host(self, member: LobbyMember):
        '''Sets a member as the lobby host.'''
        if self.host: self.host.is_host_ = False
        member.is_host_ = True
        self.host = member

    def create_member(self, user: User, send: FunctionType = None, **kwargs) -> LobbyMember:
        '''Create a new member and add it to the lobby'''
        self.last_active = dt.datetime.now()
        m = LobbyMember(user=user, send=send, **kwargs)
        self.add_member(m)
        return m

    def add_member(self, member: LobbyMember):
        '''Adds a member to the lobby.'''
        member.lobby_id = self.id
        self.members[member.uid] = member

    def get_member(self, uid: str) -> Optional[LobbyMember]:
        self.last_active = dt.datetime.now()
        return self.members.get(uid)

    def remove_member(self, uid: str) -> Optional[LobbyMember]:
        '''Removes a member from the lobby and from every game state.'''
        self.last_active = dt.datetime.now()
        for state in self.states.values():
            if hasattr(state, 'remove_player'): state.remove_player(uid)
        return self.members.pop(uid, None)

    def lock(self): self.locked = True
    def unlock(self): self.locked = False

    @fc.delegates(create_member)
    def get_or_create_member(self, user: User, **kwargs) -> LobbyMember:
        '''get member from the lobby or create a new with `create_member`'''
        self.last_active = dt.datetime.now()
        m = self.members.get(user.uid)
        if not m: m = self.create_member(user, **kwargs)
        return m

    def dump_states(self) -> str:
        '''Serialize the states of games that asked to be persisted.'''
        data = {name: GAME_REGISTRY[name].to_dict(state) for name, state in self.states.items()
                if GAME_REGISTRY[name].persist}
        return json.dumps(data) if data else ''

    def load_states(self):
        '''Rebuild persisted game states from `states_json`.'''
        for name, data in json.loads(self.states_json or '{}').items():
            spec = GAME_REGISTRY.get(name)
            if spec and spec.state_cls: self.states[name] = spec.from_dict(data)


class LobbyRepo(DataRepository[Lobby]):
    '''Class to manage lobbies'''

    def _set_tables(self):
        self.lobbies: fl.Table = self.db.t.lobbies.create(**Lobby.columns(), pk='id',
                                                          transform=True, if_not_exists=True)
        return self.lobbies

    def update(self, lobby: Lobby):
        '''Updates a lobby, its members and its game states in the database.'''
        DI.get(MemberRepo).upsert_all(lobby.members.values())
        lobby.states_json = lobby.dump_states()
        return super().update(lobby)

    def insert(self, lobby: Lobby):
        lobby.states_json = lobby.dump_states()
        return super().insert(lobby)

    def get(self, id: str) -> Optional[Lobby]:
        '''Retrieves a lobby, its members and its game states from the database.'''
        if id not in self.lobbies: return
        lobby = Lobby.from_dict(self.lobbies.get(id))
        lobby.members = {m.user_uid: m for m in DI.get(MemberRepo).get_all(id)}
        hosts = [m for m in lobby.members.values() if m.is_host]
        if hosts: lobby.host = hosts[0]
        lobby.load_states()
        return lobby

    def ids(self) -> list[str]: return [el['id'] for el in self.lobbies(select='id', as_cls=False)]

    def delete_stale(self, cutoff: dt.datetime, keep: set[str] = frozenset()) -> int:
        '''Deletes lobbies (and their members) that were last active before `cutoff`.'''
        ids = [r['id'] for r in self.db.q(f'select id from {self.lobbies} where last_active < ?',
                                          [cutoff.isoformat()]) if r['id'] not in keep]
        if not ids: return 0
        qs = ','.join('?' * len(ids))
        members = DI.get(MemberRepo).members
        self.db.q(f'delete from {members} where lobby_id in ({qs})', ids)
        self.db.q(f'delete from {self.lobbies} where id in ({qs})', ids)
        return len(ids)


def is_player(u: LobbyMember|User): return isinstance(u, LobbyMember) and u.is_player

def is_host(u: LobbyMember|User): return isinstance(u, LobbyMember) and u.is_host
