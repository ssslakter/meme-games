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
register_lobby_type(AliasLobby)