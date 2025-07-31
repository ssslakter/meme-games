from meme_games.core import *
from ..user import *


__all__ = ["LobbyMember", "MemberRepo"]

@dataclass
class LobbyMember(fc.GetAttr, Model):
    """Represents a member in a lobby, usually associated with a websocket connection."""
    _ignore = ('user', 'send', 'ws')
    _default= ('user') # forward __getattr__ to user (fc.GetAttr)

    user: User = None
    user_uid: str = None
    lobby_id: str = None
    is_player: bool = False
    is_host_: bool = False
    joined_at: dt.datetime = field(default_factory=dt.datetime.now)
    score: int = 0
    id: str = field(default_factory=lambda: random_id(8))

    send: Optional[FunctionType] = None
    ws: Optional[WebSocket] = None

    def __post_init__(self):
        if self.user: self.user_uid = self.user.uid
        if isinstance(self.joined_at, str):
            self.joined_at = dt.datetime.fromisoformat(self.joined_at)

    def spectate(self): 
        """Sets the member to be a spectator."""
        self.is_player = False

    def play(self):
        """Sets the member to be a player."""
        self.joined_at = dt.datetime.now()
        self.is_player = True

    def connect(self, send: FunctionType, ws: Optional[WebSocket] = None): 
        """Connects the member with a websocket."""
        self.send, self.ws = send, ws
    def disconnect(self): 
        """Disconnects the member."""
        self.send, self.ws = None, None
    def add_score(self, score: int): 
        """Adds a score to the member."""
        self.score += score
    def reset_score(self): 
        """Resets the member's score."""
        self.score = 0
    def sync_user(self, u: User): 
        """Synchronizes user data for the member."""
        self.user = u

    @property
    def is_connected(self): 
        """Checks if the member is connected."""
        return self.send is not None
    @property
    def is_host(self): 
        """Checks if the member is the host."""
        return self.is_host_

    def __eq__(self, other: Union[User, 'LobbyMember']): return self.uid == other.uid

    @classmethod
    def from_dict(cls, data: dict):
        data = cols2dict(data)
        data[cls]['user'] = User.from_dict(data.pop(User))
        return super().from_dict(data[cls])

    @classmethod
    def convert(cls, member: Optional['LobbyMember'] = None):
        """Converts a member to a different lobby type."""
        cf = dataclasses.fields(cls)
        if member: return cls(**{f.name: getattr(member, f.name) for f in dataclasses.fields(member) if f in cf})

    def update_user(self, u: User): 
        """Updates the user associated with this member."""
        # TODO the same as sync_user
        self.user = u


class MemberRepo(DataRepository[LobbyMember]):
    '''Class to manage lobby members'''

    def __init__(self, user_manager: UserManager):
        self.um, self.users = user_manager, user_manager.users
        super().__init__(self.um.db)

    def _set_tables(self):
        self.members: fl.Table = self.db.t.members.create(**LobbyMember.columns(), pk='id',
                                                          foreign_keys=[('user_uid', 'user', 'uid'),
                                                                        ('lobby_id', 'lobbies', 'id'),],
                                                          transform=True, if_not_exists=True)
        return self.members

    def update(self, member: LobbyMember):
        """Updates a member and their user data in the database."""
        self.um.update(member.user)
        return super().update(member)

    def get_all(self, lobby_id: str) -> list[LobbyMember]:
        """Gets all members for a given lobby ID from the database."""
        cols = self.members.c
        qry = f"""select {mk_aliases(LobbyMember, self.members)},
                  {mk_aliases(User, self.users)}
                  from {self.members} join {self.users}
                  on {cols.user_uid} = {self.users.c.uid} where {cols.lobby_id} = ?"""
        return list(map(LobbyMember.from_dict, self.db.q(qry, [lobby_id])))

