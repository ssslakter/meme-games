
__all__ = ['Lobby', 'LobbyRepo', 'MemberRepo', 'is_player', 'register_lobby_type', 'get_lobby_type_str', 'BasicLobby']

from typing import Type, get_args
from meme_games.core import *
from ..user import *
from .member import *


logger = logging.getLogger(__name__)

LOBBY_REGISTRY = {}
MEMBER_REPO_REGISTRY: dict[str, Type[MemberRepo]] = {}

def register_lobby_type[T: LobbyMember, State: Any](target_type: Type['Lobby[T,State]'], 
                                                    member_repo: Optional[Type[MemberRepo]] = None):
    name = target_type.__name__.lower() + '_' + get_args(target_type)[0].__name__.lower()
    LOBBY_REGISTRY[name] = target_type
    if member_repo:
        MEMBER_REPO_REGISTRY[name] = member_repo

def get_lobby_type_str[T: LobbyMember, State: Any](target_type: Type['Lobby[T,State]']) -> str:
    name = target_type.__name__.lower() + '_' + get_args(target_type)[0].__name__.lower()
    if name in LOBBY_REGISTRY:
        return name
    raise ValueError(f'Lobby type {name} is not registered. Available types: {list(LOBBY_REGISTRY.keys())}')


@dataclass
class Lobby[T: LobbyMember, S = None](Model):
    '''Represents a game lobby.'''
    _ignore = ('members', 'host', 'game_state')
    
    id: str = field(default_factory=random_id)
    locked: bool = False
    background_url: Optional[str] = None
    host: Optional[T] = None
    members: dict[str, T] = field(default_factory=dict)
    last_active: dt.datetime = field(default_factory=dt.datetime.now)
    current_type: str = 'lobby' # defines current type of the lobby for specific game
    game_state: Optional[S] = None
    persistent: bool = False # whether the lobby should be saved in the database


    def __post_init__(self):
        if self.host: self.host_uid = self.host.uid
        if isinstance(self.last_active, str): 
            self.last_active = dt.datetime.fromisoformat(self.last_active)
            
    def __getattr__(self, name): return getattr(self.game_state, name)

    def sorted_members(self):
        '''lobby members sorted by `joined_at` date'''
        for m in sorted(self.members.values(), key=lambda m: m.joined_at): yield m

    def set_host(self, member: T): 
        '''Sets a member as the lobby host.'''
        if self.host: self.host.is_host_=False
        member.is_host_ = True
        self.host = member

    def create_member(self, user: User, send: FunctionType = None, **kwargs) -> T:
        '''Create a new member for lobby `current_type` and add to the lobby'''
        self.last_active = dt.datetime.now()
        member_type = get_args(LOBBY_REGISTRY[self.current_type])[0]
        m = member_type(user=user, send=send, **kwargs)
        self.add_member(m)
        return m
    
    def add_member(self, member: T):
        '''Adds a member to the lobby.'''
        member.lobby_id = self.id
        self.members[member.uid] = member

    def get_member(self, uid: str) -> Optional[T]:
        self.last_active = dt.datetime.now()
        return self.members.get(uid)
    
    def remove_member(self, uid: str) -> Optional[T]:
        '''Removes a member from the lobby.'''
        self.last_active = dt.datetime.now()
        return self.members.pop(uid, None)
    
    def lock(self): self.locked = True
    def unlock(self): self.locked = False

    @fc.delegates(create_member)
    def get_or_create_member(self, user: User, **kwargs) -> T:
        '''get member from the lobby or create a new with `create_member`'''
        self.last_active = dt.datetime.now()
        m = self.members.get(user.uid)
        if not m: m = self.create_member(user, **kwargs)
        return m
    
    def cast[T: LobbyMember, S: Any](self, target_type: Type['Lobby[T,S]']) -> 'Lobby[T, S]':
        member_type: Type[T] = get_args(target_type)[0]
        state_type = get_args(target_type)[1]
        print('casting to', member_type, state_type)
        target_type_str = get_lobby_type_str(target_type)
        if self.current_type == target_type_str: return self
        self.current_type = target_type_str
        for k in self.members.keys(): self.members[k] = member_type.convert(self.members[k])
        self.host = member_type.convert(self.host)
        return self
    
    def set_default_game_state(self, state):
        if not self.game_state:
            self.game_state = state


BasicLobby = Lobby[LobbyMember]
register_lobby_type(BasicLobby, member_repo=MemberRepo)


class LobbyRepo(DataRepository[Lobby]):
    '''Class to manage lobbies'''

    def _set_tables(self):
        self.lobbies: fl.Table = self.db.t.lobbies.create(**Lobby.columns(), pk='id',
                                                          transform=True, if_not_exists=True)
        return self.lobbies

    def update(self, lobby: Lobby[LobbyMember]):
        '''Updates a lobby and its members in the database.'''
        DI.get(MEMBER_REPO_REGISTRY[lobby.current_type]).upsert_all(lobby.members.values())
        return super().update(lobby)

    def get(self, id: str) -> Lobby[LobbyMember]:
        '''Retrieves a lobby and its members from the database.'''
        if id not in self.lobbies: return
        lobby = Lobby.from_dict(self.lobbies.get(id))
        lobby.members = {m.user_uid: m for m in 
                         DI.get(MEMBER_REPO_REGISTRY.get(lobby.current_type, MemberRepo)
                                ).get_all(id)}
        hosts = [m for m in lobby.members.values() if m.is_host]
        if hosts: lobby.host = hosts[0]
        return lobby

    def ids(self) -> list[str]: return [el['id'] for el in self.lobbies(select='id', as_cls=False)]


def is_player(u: LobbyMember|User): return isinstance(u, LobbyMember) and u.is_player
