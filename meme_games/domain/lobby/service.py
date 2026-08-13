from meme_games.core import *
from ..user import *
from .member import *
from .lobby import *


logger = logging.getLogger(__name__)


class LobbyService:
    """Manages lobby creation, retrieval, and lifecycle."""
    lobby_lifetime = dt.timedelta(minutes=10)
    lobby_limit = 100
    cleanup_interval = 60.0       # seconds between stale-lobby sweeps
    max_lobbies_per_host = 3      # max concurrent lobbies one host may own
    lobby_ttl = dt.timedelta(days=1)  # persistent lobbies are dropped from the db after this

    def __init__(self, lobby_repo: LobbyRepo):
        self.repo = lobby_repo
        self.lobbies: dict[str, Lobby] = {}

    def __repr__(self): return f'{self.__class__.__name__}(active_lobbies={len(self.lobbies)})'

    def create_lobby(self, host: User = None, lobby_id: Optional[str] = None,
                     game: str = BASIC_GAME, **kwargs) -> Lobby:
        """Creates a new lobby and sets the user as the host."""
        lobby_id = lobby_id or random_id()
        ids = list(self.lobbies) + self.repo.ids()
        while lobby_id in ids: lobby_id = random_id()
        lobby = Lobby(lobby_id, **kwargs)
        lobby.play_game(game)
        if host: lobby.set_host(lobby.create_member(host))
        self.lobbies[lobby_id] = lobby
        if lobby.persistent: self.repo.insert(lobby)
        return lobby

    def get_lobby(self, id: Optional[str] = None) -> Optional[Lobby]:
        """Gets a lobby from cache or the database without changing its game."""
        lobby = self.lobbies.get(id)
        if not lobby:
            lobby = self.repo.get(id)
            if not lobby: return
            self.lobbies[id] = lobby
        return lobby

    def delete_lobby(self, id: str):
        """Deletes a lobby from cache and the database."""
        self.lobbies.pop(id, None)
        self.repo.delete(id)

    def evict_lobby(self, id: str):
        """Free a lobby's in-memory slot. Persistent lobbies stay in the DB and reload on demand."""
        self.lobbies.pop(id, None)

    def _is_stale(self, lobby: Lobby) -> bool:
        """No connected members and idle past the lifetime -> safe to evict."""
        if any(m.is_connected for m in lobby.members.values()): return False
        return dt.datetime.now() - lobby.last_active > self.lobby_lifetime

    def _host_lobby_count(self, uid: str) -> int:
        """Only lobbies someone is actually connected to count against the quota.

        `_is_stale` uses a long idle window meant for data retention (so a refresh
        doesn't lose your lobby); reusing it here let a host who merely clicked
        through a few game cards get stuck for up to `lobby_lifetime` before the
        abandoned lobbies stopped counting against them.
        """
        return sum(l.host is not None and l.host.uid == uid
                   and any(m.is_connected for m in l.members.values())
                   for l in self.lobbies.values())

    def cleanup_lobbies(self) -> int:
        """Evict stale lobbies from memory and drop long-dead ones from the db; returns how many were freed."""
        stale = [id for id, l in list(self.lobbies.items()) if self._is_stale(l)]
        for id in stale: self.evict_lobby(id)
        purged = self.repo.delete_stale(dt.datetime.now() - self.lobby_ttl, keep=set(self.lobbies))
        if stale or purged:
            logger.info(f'Evicted {len(stale)} stale lobbies, purged {purged} from db ({len(self.lobbies)} active)')
        return len(stale) + purged

    async def run_cleanup_loop(self):
        """Background task: periodically evict stale lobbies."""
        while True:
            await asyncio.sleep(self.cleanup_interval)
            try: self.cleanup_lobbies()
            except Exception: logger.exception('Lobby cleanup failed')

    def get_or_create(self, host: User = None, id: Optional[str] = None,
                      game: str = BASIC_GAME, **create_kwargs) -> tuple[Lobby, bool]:
        '''Returns an existing lobby unchanged, or creates one playing `game`.'''
        if not id or not id.isascii(): raise HTTPException(400, 'Invalid lobby id, must be ascii')
        if lobby := self.get_lobby(id):
            if host and host.uid not in lobby.members:
                lobby.create_member(host)
                self.update(lobby)
            return lobby, False
        if len(self.lobbies) >= self.lobby_limit: raise HTTPException(
            400, 'Too many lobbies, wait until some are finished')
        if host and self._host_lobby_count(host.uid) >= self.max_lobbies_per_host:
            raise HTTPException(429, 'You already have several open lobbies. Close one before creating another.')
        return self.create_lobby(host, id, game, **create_kwargs), True

    def sync_active_lobbies_user(self, u: User):
        """Synchronizes user information across all active lobbies they are in."""
        for l in self.lobbies.values(): 
            if u.uid in l.members: l.members[u.uid].update_user(u)

    def update(self, lobby: Lobby): 
        if lobby.persistent:
            self.repo.update(lobby)

    def spectate(self, player: LobbyMember, lobby: Lobby):
        player.spectate()
        state = lobby.state
        if hasattr(state, 'remove_player'): state.remove_player(player.uid)
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
