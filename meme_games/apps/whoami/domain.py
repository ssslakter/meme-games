__all__ = ['WHOAMI', 'PlayerLabel', 'CardPos', 'PlayerNotes', 'WhoAmIConfig', 'WhoAmIState']

from ...core import *
from ...domain import *


@dataclass
class PlayerLabel:
    '''A label's placement, as an offset from the card it belongs to, so it follows the card.'''
    x: int = 0
    y: int = 0
    width: int = 0
    height: int = 0


@dataclass
class CardPos:
    '''Where a player's card sits on the board.'''
    x: int = 0
    y: int = 0


@dataclass
class PlayerNotes:
    '''What a player owns in a Who Am I round: the label others gave them, and their own notes.'''
    label_text: str = ''
    label_tfm: Optional[PlayerLabel] = None
    card_pos: Optional[CardPos] = None
    notes: str = ''

    def set_notes(self, notes: str) -> None: self.notes = notes
    def set_label(self, label: str) -> None: self.label_text = label
    def set_label_transform(self, tfm: Optional[dict] = None) -> None:
        self.label_tfm = PlayerLabel(**(tfm or {}))
    def set_card_pos(self, x: int, y: int) -> None: self.card_pos = CardPos(x=x, y=y)


@dataclass
class WhoAmIConfig:
    private_notes: bool = False


@dataclass
class WhoAmIState:
    players: dict[str, PlayerNotes] = field(default_factory=dict)
    config: WhoAmIConfig = field(default_factory=WhoAmIConfig)

    def player(self, uid: str) -> PlayerNotes: return self.players.setdefault(uid, PlayerNotes())

    def remove_player(self, uid: str) -> None: self.players.pop(uid, None)

    @classmethod
    def from_dict(cls, data: dict) -> 'WhoAmIState':
        def sub(sub_cls: type, raw: Optional[dict]): return sub_cls(**raw) if raw else None
        players = {uid: PlayerNotes(**{**p,
                                       'label_tfm': sub(PlayerLabel, p.get('label_tfm')),
                                       'card_pos': sub(CardPos, p.get('card_pos'))})
                   for uid, p in data.get('players', {}).items()}
        return cls(players=players, config=WhoAmIConfig(**data.get('config', {})))


WHOAMI = 'whoami'
register_game(WHOAMI, WhoAmIState, persist=True)
