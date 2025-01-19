from dataclasses import is_dataclass
from shlex import join
from typing import get_args, Generic, TypeVar
from .imports import *


@fc.delegates(fl.Database)
def init_db(filename_or_conn=':memory:', **kwargs):
    db = fl.Database(filename_or_conn, **kwargs)
    return db


class DataManager[T]:

    def __init__(self, db: fl.Database):
        self.db = db
        self.table: fl.Table = self._set_tables()
        self.pk = self.table.pks[0] if len(self.table.pks) == 1 else self.table.pks

    def _set_tables(self):
        '''Used to create the default table for the data-manager'''
        raise NotImplementedError()

    def insert(self, obj: T): self.table.insert(obj); return obj
    def upsert(self, obj: T): self.table.upsert(obj, pk=self.pk); return obj
    def update(self, obj: T): self.table.update(obj); return obj
    def delete(self, id: Union[list, tuple, str, int, float]): self.table.delete(id)
    def upsert_all(self, objs: list[T]): self.table.upsert_all(objs, pk=self.pk); return objs


def to_basic_t(t: type):
    if get_args(t): return to_basic_t(get_args(t)[0])
    if is_dataclass(t): return dict
    return t


MODELS_REGISTRY = {}


class Model:
    '''Base class to put classes in sqlite database'''
    _ignore = ()

    def __init_subclass__(cls, **kwargs):
        super().__init_subclass__(**kwargs)
        MODELS_REGISTRY[cls.__name__] = cls

    def _asdict(self, columns: list[str] = None):
        '''Convert to a dict, possibly with only the given columns'''
        res = {}
        for f in self.fields():
            if columns and f.name not in columns: continue
            v = getattr(self, f.name)
            res[f.name] = asdict(v) if is_dataclass(v) else v
        return res

    @classmethod
    def fields(cls): 
        '''Return (name, type) pairs of the model fields that are not ignored'''
        return tuple(f for f in dataclasses.fields(cls) if f.name not in cls._ignore)

    @classmethod
    def columns(cls):
        '''Get (name, type) pairs of the table columns for this model'''
        return {f.name: to_basic_t(f.type) for f in cls.fields()}

    @classmethod
    def from_cols(cls, data: dict): 
        '''Reconstruct a model from a flat dict of column values'''
        return cls(**data)


def mk_aliases(dt_cls: Model, table: fl.Table):
    '''create aliases for columns for SQL queries'''
    return ', '.join(f'{getattr(table.c, coln)} as "{dt_cls.__name__}.{coln}"'
                     for coln, _ in dt_cls.columns().items())


def cols2dict(cols: dict, as_model=True) -> dict[Union[str, type], dict]:
    '''Converts key,value pairs of aliased columns to nested dict'''
    res = {}
    for k, v in cols.items():
        pre, field = k.split('.', 1)
        if as_model: pre = MODELS_REGISTRY[pre]
        res.setdefault(pre, {})[field] = v
    return res
