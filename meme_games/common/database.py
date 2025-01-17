from shlex import join
from typing import get_args
from .imports import *


@fc.delegates(fl.Database)
def init_db(filename_or_conn=':memory:', **kwargs):
    db = fl.Database(filename_or_conn, **kwargs)
    return db


class DataManager:
    def __init__(self, db: fl.Database):
        self.db = db
        self._set_tables()

    def _set_tables(self): pass


def to_basic_t(t: type):
    if get_args(t): return get_args(t)[0]
    return t


class Model:
    '''Base class to put classes in sqlite database'''
    _ignore = ()
    def _asdict(self): return {k: v for k, v in dataclasses.asdict(self).items() if k not in self._ignore}
    @classmethod
    def fields(cls): return tuple(f for f in dataclasses.fields(cls) if f.name not in cls._ignore)

    @classmethod
    def columns(cls):
        return {f.name: to_basic_t(f.type) for f in cls.fields()}


def mk_aliases(dt_cls: Model, table: fl.Table):
    '''create aliases for columns for SQL queries'''
    return ', '.join(f'{getattr(table.c, coln)} as "{dt_cls.__name__}.{coln}"'
                     for coln, _ in dt_cls.columns().items())


def cols2dict(cols: dict, as_cls: bool = False):
    '''Converts key,value pairs of aliased columns to nested dict'''
    res = {}
    for k, v in cols.items():
        pre, field = k.split('.', 1)
        res.setdefault(pre, {})[field] = v
    if as_cls: return tuple(globals()[cls](**v) for cls, v in res.items())
    return res
