from typing import Type
from meme_games.core import *
from ..user import *
from .member import *
from .lobby import *


class LobbyService:
    """Manages lobby creation, retrieval, and lifecycle."""
    lobby_lifetime = dt.timedelta(days=5)
    lobby_limit = 50

    def __init__(self, lobby_repo: LobbyRepo):
        self.repo = lobby_repo
        self.lobbies: dict[str, Lobby] = {}

    def __repr__(self): return f'{self.__class__.__name__}(active_lobbies={len(self.lobbies)})'

    def create_lobby[T: LobbyMember, S: Any](
            self, host: User = None, 
            lobby_id: Optional[str] = None, 
            lobby_type: Type[Lobby[T, S]] = BasicLobby,
            **kwargs) -> Lobby[T, S]:
        """Creates a new lobby and sets the user as the host."""
        lobby_id = lobby_id or random_id()
        ids = list(self.lobbies) + self.repo.ids()
        while lobby_id in ids: lobby_id = random_id()
        lobby = lobby_type(lobby_id, current_type=get_lobby_type_str(lobby_type), **kwargs)
        if host: lobby.set_host(lobby.create_member(host))
        self.lobbies[lobby_id] = lobby
        if lobby.persistent: self.repo.insert(lobby)
        return lobby

    def get_lobby[T: LobbyMember, S: Any](self, id: Optional[str] = None, as_type: Optional[Type[Lobby[T, S]]] = None) -> Optional[Lobby[T,S]]:
        """Gets a lobby from cache or the database."""
        lobby = self.lobbies.get(id)
        if lobby: return lobby.cast(as_type) if as_type else lobby
        lobby = self.repo.get(id)
        if lobby: self.lobbies[id] = lobby
        else: return
        return lobby.cast(as_type) if as_type else lobby

    def delete_lobby(self, id: str):
        """Deletes a lobby from cache and the database."""
        self.lobbies.pop(id)
        self.repo.delete(id)

    def get_or_create[T: LobbyMember, S: Any](
            self, 
            host: User = None, 
            id: Optional[str] = None,
            as_type: Optional[Type[Lobby[T, S]]] = None,
            **create_kwargs) -> tuple[Lobby[T, S], bool]:
        '''Returns the lobby if it exists, otherwise creates one if id was valid then casts to `as_type`. Returns (lobby, created)'''
        if not id or not id.isascii(): raise HTTPException(400, 'Invalid lobby id, must be ascii')
        if lobby := self.get_lobby(id): 
            return lobby.cast(as_type) if as_type else lobby, False
        if len(self.lobbies) >= self.lobby_limit: raise HTTPException(
            400, 'Too many lobbies, wait until some are finished')
        return self.create_lobby(host, id, as_type, **create_kwargs), True

    def sync_active_lobbies_user(self, u: User):
        """Synchronizes user information across all active lobbies they are in."""
        for l in self.lobbies.values(): 
            if u.uid in l.members: l.members[u.uid].update_user(u)

    def update(self, lobby: Lobby): 
        if lobby.persistent:
            self.repo.update(lobby)

    def spectate(self, player: LobbyMember, lobby: Lobby):
        player.spectate()
        if lobby.game_state:
            # TODO add generic type for game state
            lobby.game_state.remove_player(player)
        self.update(lobby)


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
