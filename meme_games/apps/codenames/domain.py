from enum import Enum

from meme_games.core import *
from meme_games.domain import *
from meme_games.apps.word_packs.domain import WordPack, WordPackRepo

__all__ = ['CODENAMES', 'CardColor', 'TeamColor', 'GamePhase', 'WordCard', 'CodenamesState',
           'LogEntry', 'COMMIT_SECONDS', 'LOG_MAX']

COMMIT_SECONDS = 2.0
LOG_MAX = 50


@dataclass
class LogEntry:
    '''One beat of play, kept as facts so the panel can colour it. The wording lives
    in the view: this is the only log a human reads, agents get their own narration.'''
    kind: str
    team: Optional[str] = None
    card: Optional[str] = None
    word: str = ''
    number: int = 0


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
    last_revealed: Optional[str] = None    # so an event can name the card that was turned
    last_revealed_by: Optional[str] = None  # and the team that turned it, before the turn flips
    clue_seconds: int = 0
    guess_seconds: int = 0
    log: list[LogEntry] = field(default_factory=list)
    votes: dict[str, str] = field(default_factory=dict)
    votes_version: int = 0
    timer: Timer = field(default_factory=Timer)
    timer_token: int = 0

    def _log(self, kind: str, **facts):
        self.log.append(LogEntry(kind, **facts))
        del self.log[:-LOG_MAX]

    def team_of(self, member: LobbyMember | User | str) -> Optional[TeamColor]:
        uid = member if isinstance(member, str) else member.uid
        return self.players.get(uid)

    def join(self, member: LobbyMember, team: TeamColor):
        if self.phase != GamePhase.WAITING: return False
        self.players[member.uid] = team
        self.spymasters.discard(member.uid)
        return True

    def toggle_spymaster(self, member: LobbyMember):
        return self.set_spymaster(member, member.uid not in self.spymasters)

    def set_spymaster(self, member: LobbyMember, enabled: bool):
        if self.phase != GamePhase.WAITING or member.uid not in self.players: return False
        if not enabled:
            self.spymasters.discard(member.uid)
        elif any(uid in self.spymasters and self.players.get(uid) == self.players[member.uid]
                 for uid in self.players if uid != member.uid): return False
        else: self.spymasters.add(member.uid)
        return True

    def remove_player(self, uid: str):
        self.players.pop(uid, None)
        self.spymasters.discard(uid)
        if self.votes.pop(uid, None): self.votes_version += 1

    def team_uids(self, team: TeamColor):
        return [uid for uid, assigned in self.players.items() if assigned == team]

    def operatives(self, team: TeamColor) -> list[str]:
        return [uid for uid in self.team_uids(team) if uid not in self.spymasters]

    def shuffle_teams(self) -> bool:
        '''Keep team sizes, reshuffle who sits where. Spymaster seats are cleared.'''
        if self.phase != GamePhase.WAITING or not self.players: return False
        sizes = {team: len(self.team_uids(team)) for team in TeamColor}
        uids = list(self.players)
        random.shuffle(uids)
        offset = 0
        for team, size in sizes.items():
            for uid in uids[offset:offset + size]: self.players[uid] = team
            offset += size
        self.spymasters.clear()
        return True

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
        self.winner = self.last_revealed = self.last_revealed_by = None
        self.votes.clear()
        self.log.clear()
        self._log('start', team=self.turn.value)
        self._arm_timer()
        return True

    def turn_seconds(self) -> int:
        if self.phase == GamePhase.CLUE: return max(0, self.clue_seconds)
        if self.phase == GamePhase.GUESSING: return max(0, self.guess_seconds)
        return 0

    def _arm_timer(self):
        self.timer_token += 1
        seconds = self.turn_seconds()
        self.timer.set(seconds) if seconds else self.timer.stop()

    def timeout(self) -> bool:
        if self.phase not in (GamePhase.CLUE, GamePhase.GUESSING) or not self.turn: return False
        self._log('timeout', team=self.turn.value)
        return self.end_turn()

    def give_clue(self, member: LobbyMember, clue: str, number: int):
        clue = ' '.join(clue.split())
        if (self.phase != GamePhase.CLUE or self.team_of(member) != self.turn or
                member.uid not in self.spymasters or not clue or not 1 <= number <= 9): return False
        if clue.casefold() in {card.word.casefold() for card in self.board}: return False
        self.clue, self.clue_number = clue, number
        self.guesses_left = number + 1
        self.phase = GamePhase.GUESSING
        self.votes.clear()
        self._log('clue', team=self.turn.value, word=clue, number=number)
        self._arm_timer()
        return True

    def vote(self, member: LobbyMember, card_id: str) -> bool:
        '''One active pick per operative; picking the same card again retracts it.'''
        if (self.phase != GamePhase.GUESSING or self.team_of(member) != self.turn or
                member.uid in self.spymasters): return False
        if not any(card.id == card_id and not card.revealed for card in self.board): return False
        if self.votes.get(member.uid) == card_id: self.votes.pop(member.uid)
        else: self.votes[member.uid] = card_id
        self.votes_version += 1
        return True

    def voters(self, card_id: str) -> list[str]:
        return [uid for uid, choice in self.votes.items() if choice == card_id]

    def consensus(self) -> Optional[str]:
        '''The card every operative of the active team has picked, if they agree.'''
        if self.phase != GamePhase.GUESSING or not self.turn: return None
        picks = {self.votes.get(uid) for uid in self.operatives(self.turn)}
        return picks.pop() if len(picks) == 1 and None not in picks else None

    def _all_revealed(self, team: TeamColor):
        return all(card.revealed for card in self.board if card.color == team.card_color)

    def reveal(self, member: LobbyMember, card_id: str):
        if (self.phase != GamePhase.GUESSING or self.team_of(member) != self.turn or
                member.uid in self.spymasters): return False
        card = next((card for card in self.board if card.id == card_id and not card.revealed), None)
        if not card: return False
        card.revealed, self.last_revealed, self.last_revealed_by = True, card.id, self.turn.value
        self.votes.clear()
        self.votes_version += 1
        self._log('reveal', team=self.turn.value, word=card.word, card=card.color.value)
        if card.color == CardColor.BOMB:
            self._finish(self.turn.other)
        elif card.color in (CardColor.RED, CardColor.BLUE) and self._all_revealed(TeamColor(card.color.value)):
            self._finish(TeamColor(card.color.value))
        elif card.color != self.turn.card_color:
            self.end_turn()
        else:
            self.guesses_left -= 1
            if self.guesses_left <= 0: self.end_turn()
        return True

    def _finish(self, winner: TeamColor):
        self.winner, self.phase = winner, GamePhase.FINISHED
        self.timer.stop()
        self._log('win', team=winner.value)

    def end_turn(self):
        if self.phase not in (GamePhase.GUESSING, GamePhase.CLUE): return False
        self.turn = self.turn.other
        self.phase = GamePhase.CLUE
        self.clue = ''
        self.clue_number = self.guesses_left = 0
        self.votes.clear()
        self.votes_version += 1
        self._log('turn', team=self.turn.value)
        self._arm_timer()
        return True

    def restart(self):
        self.phase = GamePhase.WAITING
        self.board.clear()
        self.turn = self.winner = self.last_revealed = self.last_revealed_by = None
        self.clue = ''
        self.clue_number = self.guesses_left = 0
        self.votes.clear()
        self.votes_version += 1
        self.log.clear()
        self.timer.stop()


CODENAMES = 'codenames'
register_game(CODENAMES, CodenamesState)
