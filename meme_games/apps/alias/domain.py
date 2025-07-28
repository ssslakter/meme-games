from enum import auto
from meme_games.domain import * 
from meme_games.core import *

class GameState(Enum):
    def _generate_next_value_(name: str, start, count, last_values): return name.lower()
    WAITING_FOR_PLAYERS = auto()      # Waiting for all required players to connect
    VOTING_TO_START = auto()          # Team members voting to start their round
    ROUND_PLAYING = auto()            # Active round in progress
    REVIEWING = auto()                # Another team reviewing the just-finished round


@dataclass
class AliasPlayer(LobbyMember):
    _lobby_type = 'alias'

@dataclass
class Team:
    id: str = field(default_factory=random_id)
    members: List[AliasPlayer] = field(default_factory=list)
    
    def __contains__(self, member: AliasPlayer):
        return any(m==member for m in self.members)
    
    def __len__(self): return len(self.members)
    
    def __bool__(sel): return True
    
    def append(self, player): self.members.append(player)
    
    def remove_member(self, player): 
        self.members.pop(self.members.index(player))

@dataclass
class AliasGameState:
    state: GameState = field(default=GameState.WAITING_FOR_PLAYERS)
    teams: Dict[int, Team] = field(default_factory=dict)
    
    def create_team(self) -> Team:
        team = Team()
        return self.teams.setdefault(team.id, team)
        
    def delete_team(self, id: str): self.teams.pop(id, None)
        
    def team_by_player(self, player: AliasPlayer) -> Optional[Team]:
        return next((t for t in self.teams.values() if player in t), None)
    
    def remove_player(self, p: AliasPlayer):
        team = self.team_by_player(p)
        if not team: return
        team.remove_member(p)
        if not len(team): self.delete_team(team.id)
        


AliasLobby = Lobby[AliasPlayer]

class AliasManager(DataRepository[AliasPlayer]):
    
    def __init__(self, member_manager: MemberRepo):
        self.mm = member_manager
        self.members_t = self.mm.members
        super().__init__(self.mm.db)
    
    def _set_tables(self):
        self.players = self.db.t.alias_members.create(**AliasPlayer.columns(), 
                                                       pk='id', transform=True, if_not_exists=True,
                                                       foreign_keys=[('id', 'members', 'id')])
        return self.players

    def upsert(self, obj):
        self.mm.upsert(obj._asdict(LobbyMember.columns().keys()))
        return super().upsert(obj._asdict(AliasPlayer.columns().keys()))
    
    def upsert_all(self, objs):
        self.mm.upsert_all([o._asdict(LobbyMember.columns().keys()) for o in objs])
        return super().upsert_all([o._asdict(AliasPlayer.columns().keys()) for o in objs])
    
    def update(self, obj):
        self.mm.update(obj._asdict(LobbyMember.columns().keys()))
        return super().update(obj._asdict(AliasPlayer.columns().keys()))

    def insert(self, obj: AliasPlayer):
        self.mm.insert(obj._asdict(LobbyMember.columns().keys()))
        return super().insert(obj._asdict(AliasPlayer.columns().keys()))
    
    def get_all(self, lobby_id: str) -> list[AliasPlayer]: 
        qry = f'''select {mk_aliases(AliasPlayer, self.players)},  
                 {mk_aliases(LobbyMember, self.members_t)},
                 {mk_aliases(User, self.mm.users)}
                  from {self.players} \
                  join {self.members_t} on {self.members_t.c.id} = {self.players.c.id} \
                  join {self.mm.users} on {self.members_t.c.user_uid} = {self.mm.users.c.uid} \
                  where {self.members_t.c.lobby_id} = ?'''
        return list(map(AliasPlayer.from_dict, self.db.q(qry, [lobby_id])))