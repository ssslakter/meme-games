__all__ = ['WHOAMI', 'PlayerLabel', 'PlayerNotes', 'WhoAmIState']

from ...core import *
from ...domain import *


@dataclass
class PlayerLabel:
    x: int = 0
    y: int = 0
    width: int = 0
    height: int = 0


@dataclass
class PlayerNotes:
    '''What a player owns in a Who Am I round: the label others gave them, and their own notes.'''
    label_text: str = ''
    label_tfm: Optional[PlayerLabel] = None
    notes: str = ''

    def set_notes(self, notes: str): self.notes = notes
    def set_label(self, label: str): self.label_text = label
    def set_label_transform(self, tfm: dict = None): self.label_tfm = PlayerLabel(**(tfm or {}))


@dataclass
class WhoAmIState:
    players: dict[str, PlayerNotes] = field(default_factory=dict)

    def player(self, uid: str) -> PlayerNotes: return self.players.setdefault(uid, PlayerNotes())

    def remove_player(self, uid: str): self.players.pop(uid, None)

    @classmethod
    def from_dict(cls, data: dict):
        return cls(players={uid: PlayerNotes(**{**p, 'label_tfm': PlayerLabel(**p['label_tfm']) if p.get('label_tfm') else None})
                            for uid, p in data.get('players', {}).items()})


WHOAMI = 'whoami'
register_game(WHOAMI, WhoAmIState, persist=True)
