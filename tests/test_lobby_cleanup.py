"""Tests for the leaks the lobby cleanup is supposed to plug."""
import asyncio, datetime as dt, time

from meme_games.core import DI
from meme_games.services import db
from meme_games.domain import LobbyService
from meme_games.domain.timer import Timer
from meme_games.domain.user import UserManager

service = DI.get(LobbyService)
host = DI.get(UserManager).create(name='host')


def member_count(lobby_id: str) -> int:
    return db.q('select count(*) n from members where lobby_id = ?', [lobby_id])[0]['n']


def test_timer_leaves_no_pending_tasks():
    async def run():
        before = len(asyncio.all_tasks())
        t = Timer()
        t.set(1.2)
        await t.sleep()
        await asyncio.sleep(0.1)
        assert len(asyncio.all_tasks()) == before
    asyncio.run(run())


def test_stop_wakes_the_timer_without_leaking_tasks():
    async def run():
        before = len(asyncio.all_tasks())
        t = Timer()
        t.set(30.0)
        task = asyncio.create_task(t.sleep())
        await asyncio.sleep(0.6)
        stopped_at = time.monotonic()
        t.stop()
        await task
        assert time.monotonic() - stopped_at < 0.1  # stop wins the race, no waiting out the tick
        assert not t.finished
        await asyncio.sleep(0.1)
        assert len(asyncio.all_tasks()) == before
    asyncio.run(run())


def test_pause_freezes_and_resume_finishes_timer():
    async def run():
        timer = Timer()
        timer.set(0.3)
        task = asyncio.create_task(timer.sleep())
        await asyncio.sleep(0.08)
        timer.pause()
        paused_at = timer.rem_t
        await asyncio.sleep(0.2)
        assert not task.done()
        assert abs(timer.rem_t - paused_at) < 0.03
        timer.resume()
        await task
        assert timer.finished
    asyncio.run(run())


def test_restarted_timer_invalidates_the_old_countdown():
    async def run():
        timer = Timer()
        timer.set(10)
        old = asyncio.create_task(timer.sleep())
        await asyncio.sleep(0.05)
        timer.stop()
        timer.set(0.1)
        new = asyncio.create_task(timer.sleep())
        await asyncio.gather(old, new)
        assert timer.finished
    asyncio.run(run())


def test_cleanup_purges_dead_lobbies_from_db():
    dead = service.create_lobby(host, 'deadlobby', persistent=True)
    dead.last_active = dt.datetime.now() - service.lobby_ttl - dt.timedelta(minutes=1)
    service.update(dead)
    service.evict_lobby('deadlobby')
    assert member_count('deadlobby') == 1

    service.cleanup_lobbies()

    assert 'deadlobby' not in service.repo.ids()
    assert member_count('deadlobby') == 0


def test_live_lobbies_are_never_purged_from_db():
    lobby = service.create_lobby(host, 'livelobby', persistent=True)
    lobby.last_active = dt.datetime.now() - service.lobby_ttl - dt.timedelta(days=7)
    service.update(lobby)  # db row looks ancient, but the lobby is still live in memory
    lobby.last_active = dt.datetime.now()

    service.cleanup_lobbies()

    assert 'livelobby' in service.repo.ids()
    assert member_count('livelobby') == 1
