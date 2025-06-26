import ast
from meme_games.common import *
from enum import Enum


class CardColor(Enum):
    TEAM_RED = "team_red"
    TEAM_BLUE = "team_blue"
    NEUTRAL = "neutral"
    BOMB = "bomb"

@dataclass
class WordCard:
    word: str
    color: CardColor
    is_revealed: bool = False




@dataclass
class CodenamesPlayer(LobbyMember):
    _lobby_type = 'codenames'
    is_explainer: bool = False

    @classmethod
    def columns(cls):
        cols = dict(set(super().columns().items()) - set(LobbyMember.columns().items()))
        cols.update({'id': str})
        return cols

    @classmethod
    def from_cols(cls, data: dict):
        data = cols2dict(data)
        data[cls]['user'] = User.from_cols(data.pop(User))
        data[cls].update(data.pop(LobbyMember))
        return super(LobbyMember, cls).from_cols(data[cls])


CodenamesLobby = Lobby[CodenamesPlayer]

class CodenamesManager(DataManager[CodenamesPlayer]):
    
    def __init__(self, member_manager: MemberManager):
        self.mm = member_manager
        self.members_t = self.mm.members
        super().__init__(self.mm.db)
    
    def _set_tables(self):
        self.players = self.db.t.codenames_members.create(**CodenamesPlayer.columns(), 
                                                       pk='id', transform=True, if_not_exists=True,
                                                       foreign_keys=[('id', 'members', 'id')])
        return self.players

    def upsert(self, obj):
        self.mm.upsert(obj._asdict(LobbyMember.columns().keys()))
        return super().upsert(obj._asdict(CodenamesPlayer.columns().keys()))
    
    def upsert_all(self, objs):
        self.mm.upsert_all([o._asdict(LobbyMember.columns().keys()) for o in objs])
        return super().upsert_all([o._asdict(CodenamesPlayer.columns().keys()) for o in objs])
    
    def update(self, obj):
        self.mm.update(obj._asdict(LobbyMember.columns().keys()))
        return super().update(obj._asdict(CodenamesPlayer.columns().keys()))

    def insert(self, obj: CodenamesPlayer):
        self.mm.insert(obj._asdict(LobbyMember.columns().keys()))
        return super().insert(obj._asdict(CodenamesPlayer.columns().keys()))
    
    def get_all(self, lobby_id: str) -> list[CodenamesPlayer]: 
        qry = f'''select {mk_aliases(CodenamesPlayer, self.players)},  
                 {mk_aliases(LobbyMember, self.members_t)},
                 {mk_aliases(User, self.mm.users)}
                  from {self.players} \
                  join {self.members_t} on {self.members_t.c.id} = {self.players.c.id} \
                  join {self.mm.users} on {self.members_t.c.user_uid} = {self.mm.users.c.uid} \
                  where {self.members_t.c.lobby_id} = ?'''
        return list(map(CodenamesPlayer.from_cols, self.db.q(qry, [lobby_id])))




