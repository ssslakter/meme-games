import datetime as dt
import hashlib
import secrets
from dataclasses import dataclass

import fastlite as fl

from meme_games.core import DI, DataRepository, Model
from .user import UserManager

__all__ = ['AgentPlayerSession', 'AgentPlayerSessionRepo', 'AgentPlayerSessionService']


@dataclass
class AgentPlayerSession(Model):
    """A durable agent identity. Only the digest of its bearer handle is stored."""
    handle_hash: str
    lobby_id: str
    user_uid: str
    created_at: dt.datetime
    closed_at: dt.datetime | None = None

    def __post_init__(self):
        for field in ('created_at', 'closed_at'):
            value = getattr(self, field)
            if isinstance(value, str): setattr(self, field, dt.datetime.fromisoformat(value))


class AgentPlayerSessionRepo(DataRepository[AgentPlayerSession]):
    def _set_tables(self):
        self.sessions: fl.Table = self.db.t.agent_player_sessions.create(
            **AgentPlayerSession.columns(), pk='handle_hash', transform=True, if_not_exists=True)
        return self.sessions

    def get(self, handle_hash: str) -> AgentPlayerSession | None:
        return AgentPlayerSession.from_dict(self.table.get(handle_hash)) if handle_hash in self.table else None

    def close_for_lobby(self, lobby_id: str):
        self.db.q('DELETE FROM agent_player_sessions WHERE lobby_id = ?', [lobby_id])


class AgentPlayerSessionService:
    def __init__(self, repo: AgentPlayerSessionRepo, users: UserManager):
        self.repo, self.users = repo, users

    @staticmethod
    def _digest(handle: str) -> str: return hashlib.sha256(handle.encode()).hexdigest()

    def create(self, lobby_id: str, name: str) -> tuple[AgentPlayerSession, str]:
        handle = f'mgps_{secrets.token_urlsafe(32)}'
        user = self.users.create(name=name, named=True, kind='agent')
        session = AgentPlayerSession(self._digest(handle), lobby_id, user.uid, dt.datetime.now())
        self.repo.insert(session)
        return session, handle

    def get(self, handle: str) -> AgentPlayerSession | None:
        if not handle.startswith('mgps_'): return None
        session = self.repo.get(self._digest(handle))
        if not session or session.closed_at: return None
        return session

    def close(self, handle: str) -> AgentPlayerSession | None:
        session = self.get(handle)
        if not session: return None
        session.closed_at = dt.datetime.now()
        self.repo.update(session)
        return session


DI.register_services([AgentPlayerSessionRepo, AgentPlayerSessionService])
