from meme_games.apps.word_packs import WordPack
from meme_games.core import *

@dataclass
class GameConfig:
    wordpack: Optional[WordPack] = None
    time_limit: int = 60  # Time limit for each round in seconds
    max_score: int = 100  # Maximum score a team can achieve
    max_teams: int = 4    # Maximum number of teams allowed in the game
    min_teams: int = 1    # Minimum number of teams required to start the game
    correct_guess_score: int = 1
    mistake_penalty: int = -1