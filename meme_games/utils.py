import random
import string
import fastlite as fl


class DataManager:
    def __init__(self, db: fl.Database):
        self.db = db
        self.__post_init__()

    def __post_init__(self): pass


def random_id(size=5): return ''.join(random.choices(string.ascii_lowercase+string.digits, k=size))
