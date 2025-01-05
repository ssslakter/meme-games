from ..common import *


@dataclass
class WhoAmIPlayer(BaseLobbyMember):
    label: str = ''
    notes: str = ''

    def set_note(self, notes: str): self.notes = notes
    def set_label(self, label: str): self.label = label


@dataclass
class WhoAmILobby(BaseLobby[WhoAmIPlayer]):
    @classmethod
    def create_member(cls, user: User, ws=None):
        return WhoAmIPlayer(user, ws=ws)
