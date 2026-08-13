from enum import Enum

from meme_games.core import *
from meme_games.domain import *
from meme_games.apps.word_packs.domain import WordPack, WordPackRepo

__all__ = ['CODENAMES', 'CardColor', 'TeamColor', 'GamePhase', 'WordCard', 'CodenamesState']


class CardColor(Enum):
    RED = 'red'
    BLUE = 'blue'
    NEUTRAL = 'neutral'
    BOMB = 'bomb'


class TeamColor(Enum):
    RED = 'red'
    BLUE = 'blue'

    @property
    def card_color(self): return CardColor(self.value)

    @property
    def other(self): return TeamColor.BLUE if self == TeamColor.RED else TeamColor.RED


class GamePhase(Enum):
    WAITING = 'waiting'
    CLUE = 'clue'
    GUESSING = 'guessing'
    FINISHED = 'finished'


@dataclass
class WordCard:
    word: str
    color: CardColor
    revealed: bool = False
    id: str = field(default_factory=lambda: random_id(8))


FALLBACK_WORDS = '''apple bridge moon doctor train glass forest crown robot river
dragon piano cloud bottle star table key shadow snow eagle castle lemon camera
spider clock beach paper fire circle king whale tower plane field code diamond
school needle orange mouse hospital ring night book engine garden pirate hotel'''.split()


@dataclass
class CodenamesState:
    wordpack: Optional[WordPack] = field(default_factory=lambda: DI.get(WordPackRepo).find('default'))
    phase: GamePhase = GamePhase.WAITING
    players: dict[str, TeamColor] = field(default_factory=dict)
    spymasters: set[str] = field(default_factory=set)
    board: list[WordCard] = field(default_factory=list)
    turn: Optional[TeamColor] = None
    clue: str = ''
    clue_number: int = 0
    guesses_left: int = 0
    winner: Optional[TeamColor] = None

    def team_of(self, member: LobbyMember | User | str) -> Optional[TeamColor]:
        uid = member if isinstance(member, str) else member.uid
        return self.players.get(uid)

    def join(self, member: LobbyMember, team: TeamColor):
        if self.phase != GamePhase.WAITING: return False
        self.players[member.uid] = team
        self.spymasters.discard(member.uid)
        return True

    def toggle_spymaster(self, member: LobbyMember):
        if self.phase != GamePhase.WAITING or member.uid not in self.players: return False
        if member.uid in self.spymasters: self.spymasters.remove(member.uid)
        elif not any(uid in self.spymasters and self.players.get(uid) == self.players[member.uid]
                     for uid in self.players): self.spymasters.add(member.uid)
        else: return False
        return True

    def remove_player(self, uid: str):
        self.players.pop(uid, None)
        self.spymasters.discard(uid)

    def team_uids(self, team: TeamColor):
        return [uid for uid, assigned in self.players.items() if assigned == team]

    def can_start(self):
        return (self.phase == GamePhase.WAITING and
                all(len(self.team_uids(team)) >= 2 for team in TeamColor) and
                all(any(uid in self.spymasters for uid in self.team_uids(team)) for team in TeamColor))

    def _words(self):
        pack_words = self.wordpack.words if self.wordpack else []
        def unique(words):
            result, seen = [], set()
            for word in words:
                word = word.strip()
                if word and word.casefold() not in seen:
                    result.append(word)
                    seen.add(word.casefold())
            return result
        words = unique(pack_words)
        return words if len(words) >= 25 else unique([*words, *FALLBACK_WORDS])

    def start(self):
        if not self.can_start(): return False
        words = random.sample(self._words(), 25)
        self.turn = random.choice(list(TeamColor))
        other = self.turn.other
        colors = [self.turn.card_color] * 9 + [other.card_color] * 8 + [CardColor.NEUTRAL] * 7 + [CardColor.BOMB]
        random.shuffle(colors)
        self.board = [WordCard(word, color) for word, color in zip(words, colors)]
        self.phase = GamePhase.CLUE
        self.clue = ''
        self.clue_number = self.guesses_left = 0
        self.winner = None
        return True

    def give_clue(self, member: LobbyMember, clue: str, number: int):
        clue = ' '.join(clue.split())
        if (self.phase != GamePhase.CLUE or self.team_of(member) != self.turn or
                member.uid not in self.spymasters or not clue or ' ' in clue or not 1 <= number <= 9): return False
        if clue.casefold() in {card.word.casefold() for card in self.board}: return False
        self.clue, self.clue_number = clue, number
        self.guesses_left = number + 1
        self.phase = GamePhase.GUESSING
        return True

    def _all_revealed(self, team: TeamColor):
        return all(card.revealed for card in self.board if card.color == team.card_color)

    def reveal(self, member: LobbyMember, card_id: str):
        if (self.phase != GamePhase.GUESSING or self.team_of(member) != self.turn or
                member.uid in self.spymasters): return False
        card = next((card for card in self.board if card.id == card_id and not card.revealed), None)
        if not card: return False
        card.revealed = True
        if card.color == CardColor.BOMB:
            self.winner, self.phase = self.turn.other, GamePhase.FINISHED
        elif card.color in (CardColor.RED, CardColor.BLUE) and self._all_revealed(TeamColor(card.color.value)):
            self.winner, self.phase = TeamColor(card.color.value), GamePhase.FINISHED
        elif card.color != self.turn.card_color:
            self.end_turn()
        else:
            self.guesses_left -= 1
            if self.guesses_left <= 0: self.end_turn()
        return True

    def end_turn(self):
        if self.phase not in (GamePhase.GUESSING, GamePhase.CLUE): return False
        self.turn = self.turn.other
        self.phase = GamePhase.CLUE
        self.clue = ''
        self.clue_number = self.guesses_left = 0
        return True

    def restart(self):
        self.phase = GamePhase.WAITING
        self.board.clear()
        self.turn = self.winner = None
        self.clue = ''
        self.clue_number = self.guesses_left = 0


CODENAMES = 'codenames'
register_game(CODENAMES, CodenamesState)
