# AUTOGENERATED! DO NOT EDIT! File to edit: ../../../notebooks/wordpack.ipynb.

# %% auto 0
__all__ = ['WordPack', 'WordPackManager']

# %% ../../../notebooks/wordpack.ipynb 1
from ...core import *
from ...domain import *

@dataclass
class WordPack(Model):
    _ignore = ('author')

    name: str = 'Empty Pack'
    words_: str = '' # \n separated words
    author: Optional[User] = None
    author_id: str = ''
    id: str = field(default_factory=random_id)
    created_at: dt.datetime = field(default_factory=dt.datetime.now)
    
    def __post_init__(self):
        if isinstance(self.words_, list): self.words_ = '\n'.join(self.words_)
    
    @property
    def words(self):
        return self.words_.split('\n')
    
    def get_author_name(self) -> Optional[str]:
        return self.author.name if self.author else None

    
    @classmethod
    def from_cols(cls, cols: dict):
        d = cols2dict(cols)
        if d[cls]['author_id']:
            d[cls]['author'] = User.from_dict(d.pop(User))
        return cls.from_dict(d[cls])


class WordPackManager(DataManager[WordPack]):
    def _set_tables(self):
        self.wordpacks = self.db.t.wordpacks.create(WordPack.columns(), pk='id', transform=True)
        self.users = self.db.t.user
        return self.wordpacks

    def get_all(self, offset: int = 0, limit: int = 100):
        qry = f"""select {mk_aliases(WordPack, self.table)},
                  {mk_aliases(User, self.users)}
                  from {self.table} left join {self.users}
                  on {self.table.c.author_id} = {self.users.c.uid}
                  limit {limit} offset {offset}"""
        return list(map(WordPack.from_cols, self.db.q(qry)))
    
    
    def get_by_id(self, id: str):
        return WordPack.from_dict(self.table.get(id))
    
