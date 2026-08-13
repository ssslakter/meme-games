from meme_games.core import *
import time as t

class Timer:

    def __init__(self):
        self.stop_ = asyncio.Event()
        self.finished = False
        self.paused = False
        self.generation = 0

    def set(self, time: float = 10.0):
        self.reset()
        self.rem_t = self.total = time

    def reset(self):
        self.generation += 1
        self.finished = False
        self.paused = False
        self.stop_.clear()

    async def sleep(self, time: float = None):
        '''Blocks caller's execution for `time` seconds, or until timer is stopped.'''
        if time is not None: self.set(time)
        generation = self.generation
        checked_at = t.monotonic()
        while self.rem_t > 0:
            try: await asyncio.wait_for(self.stop_.wait(), 0.25)
            except TimeoutError: pass
            if self.stop_.is_set() or generation != self.generation: return
            now = t.monotonic()
            if not self.paused: self.rem_t -= now - checked_at
            checked_at = now
        self.finished = True

    @property
    def time(self):
        return dt.timedelta(seconds=max(0, self.rem_t))
    def stop(self):
        self.generation += 1
        self.stop_.set()

    def pause(self):
        if not self.finished: self.paused = True

    def resume(self): self.paused = False
