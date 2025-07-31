from meme_games.core import *
import time as t

class Timer:

    def __init__(self):
        self.pause_, self.stop_ = asyncio.Event(), asyncio.Event()
        
    def set(self, time: int = 10): self.rem_t = self.total = time

    def reset(self):
        self.unpause()
        self.stop_.clear()

    async def sleep(self, time: int = None):
        '''Blocks caller's execution for `time` seconds, or until timer is stopped.'''
        self.rem_t = self.total or time
        self.reset()
        finish_t = t.monotonic() + self.total
        while self.rem_t > 0:
            timer = asyncio.create_task(asyncio.sleep(0.5))  # interval check on pause and stop
            await asyncio.wait([timer, asyncio.create_task(self.stop_.wait())], return_when=asyncio.FIRST_COMPLETED)
            if self.stop_.is_set(): return
            elif self.pause_.is_set():
                paused_t = t.monotonic()
                await self.pause_.wait()
                unpause_t = t.monotonic()
                finish_t += paused_t - unpause_t
            else: self.rem_t = finish_t - t.monotonic()

    @property
    def time(self): 
        return dt.timedelta(seconds=max(0, self.rem_t))
    def unpause(self): self.pause_.clear()
    def pause(self): self.pause_.set()
    def stop(self): 
        self.stop_.set()