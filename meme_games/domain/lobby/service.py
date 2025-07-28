from meme_games.core import *
from ..user import *
from .member import *
from .lobby import *


class LobbyService:
    """Manages lobby creation, retrieval, and lifecycle."""
    lobby_lifetime = dt.timedelta(hours=5)
    lobby_limit = 50

    def __init__(self, lobby_manager: LobbyRepo):
        self.lm = lobby_manager
        self.lobbies: dict[str, Lobby] = {}

    def __repr__(self): return f'{self.__class__.__name__}(active_lobbies={len(self.lobbies)})'

    def create_lobby[T: LobbyMember](self, u: User, lobby_id: Optional[str] = None, lobby_type: str = LobbyMember._lobby_type) -> Lobby[T]:
        """Creates a new lobby and sets the user as the host."""
        lobby_id = lobby_id or random_id()
        ids = list(self.lobbies) + self.lm.ids()
        while lobby_id in ids: lobby_id = random_id()
        lobby = Lobby[LOBBY_REGISTRY[lobby_type]](lobby_id, lobby_type=lobby_type)
        lobby.set_host(lobby.create_member(u))
        self.lobbies[lobby_id] = lobby
        self.lm.insert(lobby)
        return lobby

    def get_lobby(self, id: Optional[str] = None) -> Optional[Lobby]:
        """Gets a lobby from cache or the database."""
        lobby = self.lobbies.get(id)
        if lobby: return lobby
        lobby = self.lm.get(id)
        if lobby: self.lobbies[id] = lobby
        return lobby

    def delete_lobby(self, id: str):
        """Deletes a lobby from cache and the database."""
        self.lobbies.pop(id)
        self.lm.delete(id)

    def get_or_create[T: LobbyMember](self, u: User, id: Optional[str] = None,
                                      member_type: type[T] = LobbyMember) -> tuple[Lobby[T], bool]:
        '''Returns the lobby if it exists, otherwise creates one if id was valid. Returns (lobby, created)'''
        if not id or not id.isascii(): raise HTTPException(400, 'Invalid lobby id, must be ascii')
        ltype = dict_inverse(LOBBY_REGISTRY)[member_type]
        if lobby := self.get_lobby(id): return lobby.convert(ltype), False
        if len(self.lobbies) >= self.lobby_limit: raise HTTPException(
            400, 'Too many lobbies, wait until some are finished')
        return self.create_lobby(u, id, ltype), True

    def sync_active_lobbies_user(self, u: User):
        """Synchronizes user information across all active lobbies they are in."""
        for l in self.lobbies.values(): 
            if u.uid in l.members: l.members[u.uid].update_user(u)

    def update(self, lobby: Lobby): self.lm.update(lobby)


DI.register_services([LobbyRepo, MemberRepo, LobbyService])


def lobby_beforeware(service: LobbyService, skip=None):
    '''Makes sure that request always contains valid lobby'''
    def before(req: Request):
        if 'session' not in req.scope: return
        path_lobby_id = req.path_params.get('lobby_id')
        if path_lobby_id: req.session['lobby_id'] = path_lobby_id
        lobby: Lobby = service.get_lobby(req.session.get("lobby_id"))
        if lobby: req.state.lobby = lobby
        
    return Beforeware(before, skip)
