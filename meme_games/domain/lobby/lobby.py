
__all__ = ['MEMBER_MANAGER_REGISTRY', 'Lobby',
           'register_lobby_member_manager', 'LobbyRepo', 'MemberRepo', 'is_player']


from meme_games.core import *
from ..user import *
from .member import *


logger = logging.getLogger(__name__)



@dataclass
class Lobby[T: LobbyMember](Model):
    """Represents a game lobby."""
    _ignore = ('members', 'host', 'game_state')
    
    id: str = field(default_factory=random_id)
    lobby_type: str = LobbyMember._lobby_type
    locked: bool = False
    background_url: Optional[str] = None
    host: Optional[T] = None
    members: dict[str, T] = field(default_factory=dict)
    last_active: dt.datetime = field(default_factory=dt.datetime.now)
    game_state: Optional[Any] = None
    

    def __post_init__(self):
        if self.host: self.host_uid = self.host.uid
        if isinstance(self.last_active, str): 
            self.last_active = dt.datetime.fromisoformat(self.last_active)
            
    def __getattr__(self, name): return getattr(self.game_state, name)

    def sorted_members(self):
        '''lobby members sorted by `joined_at` date'''
        for m in sorted(self.members.values(), key=lambda m: m.joined_at): yield m

    def set_host(self, member: T): 
        """Sets a member as the lobby host."""
        if self.host: self.host.is_host_=False
        member.is_host_ = True
        self.host = member

    def create_member(self, user: User, send: FunctionType = None, **kwargs) -> T:
        '''Create a new member for lobby `lobby_type` and add to the lobby'''
        self.last_active = dt.datetime.now()
        m = LOBBY_REGISTRY[self.lobby_type](user=user, send=send, **kwargs)
        self.add_member(m)
        return m
    
    def add_member(self, member: T):
        """Adds a member to the lobby."""
        member.lobby_id = self.id
        self.members[member.uid] = member

    def get_member(self, uid: str) -> Optional[T]:
        self.last_active = dt.datetime.now()
        return self.members.get(uid)
    
    def lock(self): self.locked = True
    def unlock(self): self.locked = False

    @fc.delegates(create_member)
    def get_or_create_member(self, user: User, **kwargs) -> T:
        '''get member from the lobby or create a new with `create_member`'''
        self.last_active = dt.datetime.now()
        m = self.members.get(user.uid)
        if not m: m = self.create_member(user, **kwargs)
        return m

    def convert[T: LobbyMember](self: 'Lobby', lobby_type: str = LobbyMember._lobby_type) -> 'Lobby[T]':
        """Converts the lobby and its members to a different type."""
        if self.lobby_type == lobby_type: return self
        self.lobby_type = lobby_type
        mtype = LOBBY_REGISTRY[self.lobby_type]
        for k in self.members.keys(): self.members[k] = mtype.convert(self.members[k])
        self.host = mtype.convert(self.host)
        return self


MEMBER_MANAGER_REGISTRY = {}


def register_lobby_member_manager[T: DataRepository](manager: T, entity_cls: type) -> T:
    '''Register a manager for an entity class'''
    MEMBER_MANAGER_REGISTRY[entity_cls] = manager
    return manager


class LobbyRepo(DataRepository[Lobby]):
    '''Class to manage lobbies'''
    memm = MEMBER_MANAGER_REGISTRY

    def _set_tables(self):
        self.lobbies: fl.Table = self.db.t.lobbies.create(**Lobby.columns(), pk='id',
                                                          transform=True, if_not_exists=True)
        return self.lobbies

    def update(self, lobby: Lobby[LobbyMember]):
        """Updates a lobby and its members in the database."""
        self.memm[LOBBY_REGISTRY[lobby.lobby_type]].upsert_all(lobby.members.values())
        return super().update(lobby)

    def get(self, id: str) -> Lobby[LobbyMember]:
        """Retrieves a lobby and its members from the database."""
        if id not in self.lobbies: return
        lobby = Lobby.from_dict(self.lobbies.get(id))
        lobby.members = {m.user_uid: m for m in self.memm[LOBBY_REGISTRY[lobby.lobby_type]].get_all(id)}
        hosts = [m for m in lobby.members.values() if m.is_host]
        if hosts: lobby.host = hosts[0]
        return lobby

    def ids(self) -> list[str]: return [el['id'] for el in self.lobbies(select='id', as_cls=False)]


def is_player(u: LobbyMember|User): return isinstance(u, LobbyMember) and u.is_player
