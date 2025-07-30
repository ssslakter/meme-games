from meme_games.core import *
from meme_games.domain.lobby import *

@dataclass
class AliasPlayer(LobbyMember):
    voted: bool = False

    def reset_votes(self): self.voted = False


@dataclass
class Team:
    id: str = field(default_factory=random_id)
    members: List[AliasPlayer] = field(default_factory=list)
    points: int = 0
    
    def __contains__(self, member: AliasPlayer):
        return any(m==member for m in self.members)
    
    def __len__(self): return len(self.members)
    
    # allows to write `if team: ...` when function returns `Optional[Team]`
    def __bool__(self): return True
    
    def append(self, player): 
        if player in self: return
        self.members.append(player)
    
    def remove_member(self, player): 
        self.members.pop(self.members.index(player))

    def __next__(self):
        if not hasattr(self, 'iterator'):
            self.iterator = itertools.cycle(self.members)
        return next(self.iterator)
