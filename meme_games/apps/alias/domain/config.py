from meme_games.apps.word_packs import WordPack, WordPackRepo
from meme_games.core import *

@dataclass
class GameConfig:
    wordpack: Optional[WordPack] = field(default_factory=lambda: DI.get(WordPackRepo).find('default'))
    time_limit: int = 5000  # Time limit for each round in seconds
    max_score: int = 100  # Maximum score a team can achieve
    max_teams: int = 4    # Maximum number of teams allowed in the game
    min_team_players: int = 1 # Minimum number of members in a team
    min_teams: int = 1    # Minimum number of teams required to start the game
    correct_guess_score: int = 1
    mistake_penalty: int = -1