from meme_games.core import *
import time as t

class Timer:

    def __init__(self):
        self.stop_ = asyncio.Event()
        self.finished = False

    def set(self, time: float = 10.0):
        self.reset()
        self.rem_t = self.total = time

    def reset(self):
        self.finished = False
        self.stop_.clear()

    async def sleep(self, time: float = None):
        '''Blocks caller's execution for `time` seconds, or until timer is stopped.'''
        self.rem_t = self.total or time
        self.reset()
        finish_t = t.monotonic() + self.total
        while self.rem_t > 0:
            try: await asyncio.wait_for(self.stop_.wait(), 0.5)  # interval check on stop
            except TimeoutError: pass
            if self.stop_.is_set(): return
            self.rem_t = finish_t - t.monotonic()
        self.finished = True

    @property
    def time(self):
        return dt.timedelta(seconds=max(0, self.rem_t))
    def stop(self):
        self.stop_.set()