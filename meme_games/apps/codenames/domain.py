from enum import Enum
from meme_games.core import *
from meme_games.domain import *

__all__ = ['CODENAMES', 'CardColor', 'WordCard', 'CodenamesState']


class CardColor(Enum):
    TEAM_RED = "team_red"
    TEAM_BLUE = "team_blue"
    NEUTRAL = "neutral"
    BOMB = "bomb"

    def to_css_color(self):
        return {
            CardColor.TEAM_RED: 'red',
            CardColor.TEAM_BLUE: 'blue',
            CardColor.NEUTRAL: 'gray',
            CardColor.BOMB: 'black',
        }[self]

@dataclass
class WordCard:
    word: str
    color: CardColor
    is_revealed: bool = False

    def __ft__(self):
        return Card(H4(self.word), style=f'background-color: {self.color.to_css_color()}',
                    cls='mg-game-card mg-word-card', data_ui='word-card',
                    data_color=self.color.value, data_revealed=str(self.is_revealed).lower())


@dataclass
class CodenamesState:
    explainers: set[str] = field(default_factory=set)

    def is_explainer(self, uid: str) -> bool: return uid in self.explainers

    def remove_player(self, uid: str): self.explainers.discard(uid)


CODENAMES = 'codenames'
register_game(CODENAMES, CodenamesState)
