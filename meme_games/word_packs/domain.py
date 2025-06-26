import ast
from meme_games.common import *

@dataclass
class WordPack:
    id: str
    words: list[str]
    is_revealed: bool = False
    
@dataclass
class Word(Model):
    id: str
    pack_id: str
    word: str

class WordPackManager(DataManager[WordPack]):
    def _set_tables(self):
        self.words = self.db.t.word_cards.create(**Word.columns(), pk='id', if_not_exists=True)
        return self.words

    def get_all(self):
        return self.db.q(f'select {mk_aliases(WordPack, self.table)} from {self.table}')

    def get_by_id(self, id: str):
        return self.db.q(f'select {mk_aliases(WordPack, self.table)} from {self.table} where id = ?', [id])