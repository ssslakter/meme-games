import datetime as dt
import hashlib
import hmac
import secrets
from dataclasses import dataclass

import fastlite as fl

from meme_games.core import DI, DataRepository, Model
from .user import UserManager

__all__ = ['AgentAccess', 'AgentAccessRepo', 'AgentAccessService']


@dataclass
class AgentAccess(Model):
    id: str
    lobby_id: str
    user_uid: str
    token_salt: str
    token_hash: str
    created_at: dt.datetime
    last_used_at: dt.datetime | None = None
    revoked: bool = False

    def __post_init__(self):
        for field in ('created_at', 'last_used_at'):
            value = getattr(self, field)
            if isinstance(value, str): setattr(self, field, dt.datetime.fromisoformat(value))


class AgentAccessRepo(DataRepository[AgentAccess]):
    def _set_tables(self):
        self.access: fl.Table = self.db.t.agent_access.create(
            **AgentAccess.columns(), pk='id', transform=True, if_not_exists=True)
        return self.access

    def get(self, access_id: str) -> AgentAccess | None:
        return AgentAccess.from_dict(self.table.get(access_id)) if access_id in self.table else None

    def for_lobby(self, lobby_id: str) -> list[AgentAccess]:
        return [AgentAccess.from_dict(row) for row in self.table.rows_where('lobby_id = ?', [lobby_id])]


class AgentAccessService:
    def __init__(self, repo: AgentAccessRepo, users: UserManager):
        self.repo, self.users = repo, users
        self.connected_users: set[str] = set()

    @staticmethod
    def _digest(secret: str, salt: bytes) -> str:
        return hashlib.scrypt(secret.encode(), salt=salt, n=2**14, r=8, p=1).hex()

    def create(self, lobby_id: str, name: str) -> tuple[AgentAccess, str]:
        name = ' '.join(name.split())
        if not 1 <= len(name) <= 40: raise ValueError('Agent name must be 1–40 characters')
        access_id, secret = secrets.token_urlsafe(9), secrets.token_urlsafe(32)
        salt = secrets.token_bytes(16)
        user = self.users.create(name=name, named=True, kind='agent')
        access = AgentAccess(access_id, lobby_id, user.uid, salt.hex(), self._digest(secret, salt), dt.datetime.now())
        self.repo.insert(access)
        return access, f'mgai_{access_id}_{secret}'

    def verify(self, token: str, touch=True) -> AgentAccess | None:
        try: prefix, access_id, secret = token.split('_', 2)
        except ValueError: return None
        access = self.repo.get(access_id) if prefix == 'mgai' else None
        if not access or access.revoked: return None
        digest = self._digest(secret, bytes.fromhex(access.token_salt))
        if not hmac.compare_digest(digest, access.token_hash): return None
        if touch:
            access.last_used_at = dt.datetime.now()
            self.repo.update(access)
        return access

    def revoke(self, access_id: str, lobby_id: str) -> AgentAccess | None:
        access = self.repo.get(access_id)
        if not access or access.lobby_id != lobby_id: return None
        access.revoked = True
        self.repo.update(access)
        self.connected_users.discard(access.user_uid)
        return access


DI.register_services([AgentAccessRepo, AgentAccessService])
