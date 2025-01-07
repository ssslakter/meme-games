from ..common import *


@dataclass
class WhoAmIPlayer(BaseLobbyMember):
    label: str = ''
    notes: str = ''

    def set_notes(self, notes: str): self.notes = notes
    def set_label(self, label: str): self.label = label


@dataclass
class WhoAmILobby(BaseLobby[WhoAmIPlayer]):
    @classmethod
    def create_member(cls, user: User, send=None, ws=None):
        return WhoAmIPlayer(user, send=send, ws=ws)
