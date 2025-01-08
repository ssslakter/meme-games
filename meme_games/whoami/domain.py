from ..common import *

@dataclass
class PlayerLabel:
    x: int = 0
    y: int = 0
    width: int = 0
    height: int = 0

@dataclass
class WhoAmIPlayer(BaseLobbyMember):
    label_text: str = ''
    label_tfm: Optional[PlayerLabel] = None
    notes: str = ''

    def set_notes(self, notes: str): self.notes = notes
    def set_label(self, label: str): self.label_text = label
    def set_label_transform(self, **kwargs): self.label_tfm = PlayerLabel(**kwargs)

@dataclass
class WhoAmILobby(BaseLobby[WhoAmIPlayer]):
    @classmethod
    def create_member(cls, user: User, send=None, ws=None):
        return WhoAmIPlayer(user, send=send, ws=ws)
