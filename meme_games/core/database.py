from dataclasses import is_dataclass
from typing import get_args
from .imports import *


__all__ = ['init_db', 'DataManager', 'Model', 'mk_aliases', 'cols2dict']


@fc.delegates(fl.Database)
def init_db(filename_or_conn=':memory:', **kwargs):
    db = fl.Database(filename_or_conn, **kwargs)
    return db


class DataManager[T: Model]:
    '''Base class to manage database tables for a specific model and its CRUD.
    To use this class, you must subclass it and implement the `_set_tables` method
    to define the table it will manage.

    Args:
        db (fl.Database): The database connection object.

    Attributes:
        db (fl.Database): The database connection object.
        table (fl.Table): The `fastlite` table managed by this instance.
        pk (str or tuple): The primary key(s) of the table.

    Example:
        ```python
        from dataclasses import dataclass

        @dataclass
        class User(Model):
            id: int
            name: str

        class UserRepo(DataManager[User]):
            def _set_tables(self):
                self.db.create_table(User.__name__, User.columns(), 'id')
                return self.db[User.__name__]

        db = init_db()
        user_repo = UserRepo(db)
        user_repo.insert(User(id=1, name='Alice'))
        ```
    '''

    def __init__(self, db: fl.Database):
        self.db = db
        self.table: fl.Table = self._set_tables()
        self.pk = self.table.pks[0] if len(self.table.pks) == 1 else self.table.pks

    def _set_tables(self):
        '''Used to create the default table for the data-manager'''
        raise NotImplementedError()

    def insert(self, obj: T): self.table.insert(asdict(obj)); return obj
    def upsert(self, obj: T): self.table.upsert(asdict(obj), pk=self.pk); return obj
    def update(self, obj: T): self.table.update(asdict(obj)); return obj
    def delete(self, id: Union[list, tuple, str, int, float]): self.table.delete(id)
    def upsert_all(self, objs: list[T]): self.table.upsert_all([asdict(o) for o in objs], pk=self.pk); return objs


def to_basic_t(t: type):
    if get_args(t): return to_basic_t(get_args(t)[0])
    if is_dataclass(t): return dict
    return t


MODELS_REGISTRY = {}


# TODO implement simpler way to convert models to database
class Model:
    """
    Base class for creating models that can be stored in an SQLite database.

    This class provides the foundation for creating database models that can be 
    stored in SQLite. To create your own model:
    
    1. Inherit from this class.
    2. Use dataclass fields to define your model attributes.
    3. Optionally add `_ignore` to exclude fields from database storage.
    4. The model will automatically be registered in `MODELS_REGISTRY`.
    
    Example:
        ```python
        from datetime import datetime
        from dataclasses import dataclass
        
        @dataclass
        class User(Model):
            id: int
            name: str
            email: str
            created_at: datetime
            _ignore = ('created_at',)  # This field won't be stored in the DB
            
        # The User model is now ready to be used with DataManager
        user_manager = DataManager[User](db)
        user = User(id=1, name="John", email="john@example.com", created_at=datetime.now())
        user_manager.insert(user)
        ```
    """
    _ignore = ()

    def __init_subclass__(cls, **kwargs):
        super().__init_subclass__(**kwargs)
        MODELS_REGISTRY[cls.__name__] = cls

    def _asdict(self, columns: list[str] = None):
        '''Convert to a dict, possibly with only the given columns for database storage'''
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
    def from_dict(cls, data: dict): 
        '''Reconstruct a model from a flat dict of column values'''
        return cls(**data)
    
    @classmethod
    def from_cols(cls, cols_data: dict): 
        '''Reconstruct a model from a flat dict of column values'''
        d = list(cols2dict(cols_data).values())[0]
        return cls(**d)


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
