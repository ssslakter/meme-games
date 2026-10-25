__all__ = ['HIVEMIND', 'HivePhase', 'HiveRound', 'HiveMindState', 'PROMPT_PACK',
           'normalize_answer', 'ANSWERS_PER_ROUND', 'ANSWER_MAX', 'ROUNDS_MAX',
           'DEFAULT_ROUNDS', 'SECONDS_MAX', 'DEFAULT_SECONDS']

from collections import defaultdict

from ...core import *
from ...domain import *
from ..word_packs.domain import WordPack, WordPackRepo


ANSWERS_PER_ROUND, ANSWER_MAX = 6, 60
ROUNDS_MAX, DEFAULT_ROUNDS = 20, 5
SECONDS_MAX, DEFAULT_SECONDS = 900, 120
PROMPT_PACK = 'Prompts'  # the shipped deck of prompts a lobby plays by default


class HivePhase(Enum):
    WAITING = 'waiting'
    WRITING = 'writing'      # the question is up, words are hidden until the round closes
    REVEAL = 'reveal'        # this round is scored and on the table


def normalize_answer(text: str) -> str:
    """Answers agree when they read the same, whatever the capitals, spacing or
    trailing punctuation - so "Pizza!", "pizza" and "  pizza " are one answer."""
    return ' '.join(str(text or '').casefold().split()).strip('.,!?;:')


@dataclass
class HiveRound:
    """One question, the list every player wrote for it, and what it scored."""
    question: str
    answers: dict[str, list[str]] = field(default_factory=dict)  # uid -> words as typed

    def words(self, uid: str) -> list[str]:
        """This player's non-empty words, in cell order."""
        return [word for word in self.answers.get(uid, []) if word]

    def owners(self) -> dict[str, set[str]]:
        """Normalized word -> the players who wrote it."""
        owners = defaultdict(set)
        for uid, words in self.answers.items():
            for word in words:
                if normalized := normalize_answer(word): owners[normalized].add(uid)
        return dict(owners)

    def matched_positions(self) -> set[tuple[str, int]]:
        """(player, cell) for every word somebody else also wrote - the case-insensitive,
        punctuation-insensitive match. This is what a manual edit re-decides."""
        owners = self.owners()
        return {(uid, index) for uid, words in self.answers.items()
                for index, word in enumerate(words)
                if (normalized := normalize_answer(word)) and len(owners[normalized]) > 1}

    def points(self) -> dict[str, int]:
        """A point for every word of yours that somebody else also wrote."""
        scored = defaultdict(int)
        for uid, _ in self.matched_positions(): scored[uid] += 1
        return dict(scored)

    def matches(self) -> dict[str, list[str]]:
        """Normalized word -> the players who wrote it, for every shared word."""
        shared = ((word, sorted(uids)) for word, uids in self.owners().items() if len(uids) > 1)
        return dict(sorted(shared, key=lambda item: (-len(item[1]), item[0])))


@dataclass
class HiveMindState:
    """The host's wordpack, the round in progress, and every round already revealed.

    Words live in `answers` only while the round is open; revealing moves them into
    `revealed`, which is the only record the board reads.
    """
    wordpack: Optional[WordPack] = field(
        default_factory=lambda: DI.get(WordPackRepo).find(PROMPT_PACK))
    total_rounds: int = DEFAULT_ROUNDS
    seconds: int = DEFAULT_SECONDS                        # 0 means no round timer
    phase: HivePhase = HivePhase.WAITING
    round_number: int = 0
    question: str = ''
    answers: dict[str, list[str]] = field(default_factory=dict)
    ready: set[str] = field(default_factory=set)
    revealed: list[HiveRound] = field(default_factory=list)
    timer: Timer = field(default_factory=Timer)
    timer_token: int = 0

    @property
    def finished(self) -> bool:
        """The last round is on the table, so there is nothing left to deal."""
        return self.phase == HivePhase.REVEAL and self.round_number >= self.total_rounds

    def last(self) -> Optional[HiveRound]: return self.revealed[-1] if self.revealed else None

    def totals(self) -> dict[str, int]:
        """Running score: the words of yours that agreed, summed over every reveal."""
        sums = defaultdict(int)
        for played in self.revealed:
            for uid, points in played.points().items(): sums[uid] += points
        return dict(sums)

    def score(self, uid: str) -> int: return self.totals().get(uid, 0)

    def words(self, uid: str) -> list[str]:
        """The words this player has saved for the open round."""
        return HiveRound(self.question, self.answers).words(uid)

    def is_ready(self, uid: str) -> bool: return uid in self.ready

    def all_ready(self, uids: list[str]) -> bool:
        return bool(uids) and all(uid in self.ready for uid in uids)

    def deck(self) -> list[str]:
        """The questions this lobby plays, straight from the host's wordpack."""
        return self.wordpack.words if self.wordpack else []

    def can_start(self, uids: list[str]) -> bool:
        return self.phase == HivePhase.WAITING and len(uids) >= 2 and bool(self.deck())

    def start(self, uids: list[str]) -> bool:
        if not self.can_start(uids): return False
        self.round_number = 0
        self.revealed.clear()
        self._deal()
        self.phase = HivePhase.WRITING
        self.arm_timer()
        return True

    def _deal(self):
        """The next question, cycling the deck when the host asked for more rounds than
        it holds."""
        deck = self.deck()
        self.round_number += 1
        self.question = deck[(self.round_number - 1) % len(deck)]
        self.answers.clear()
        self.ready.clear()

    def set_word(self, uid: str, index: int, text: str) -> bool:
        """Save one cell of this player's list. Emptying a cell drops it."""
        text = ' '.join(str(text or '').split())
        if self.phase != HivePhase.WRITING or uid in self.ready: return False
        if not 0 <= index < ANSWERS_PER_ROUND or len(text) > ANSWER_MAX: return False
        words = list(self.answers.get(uid, []))
        words += [''] * (index + 1 - len(words))
        words[index] = text
        self.answers[uid] = words
        return True

    def set_ready(self, uid: str, is_ready: bool = True) -> bool:
        """Whether this player is done writing. Everyone being ready closes the round."""
        if self.phase != HivePhase.WRITING: return False
        self.ready.add(uid) if is_ready else self.ready.discard(uid)
        return True

    def reveal(self) -> bool:
        """Close the open round and score it; `last()` is what the board then shows."""
        if self.phase != HivePhase.WRITING: return False
        self.revealed.append(HiveRound(self.question, {uid: list(words)
                                                      for uid, words in self.answers.items()}))
        self.answers.clear()
        self.ready.clear()
        self.phase = HivePhase.REVEAL
        self.timer.stop()
        return True

    def timeout(self) -> bool:
        """The clock ran out: close the round with whatever has been written."""
        if self.phase != HivePhase.WRITING: return False
        return self.reveal()

    def edit_word(self, uid: str, index: int, text: str) -> bool:
        """Rewrite a word on the revealed round, so a paraphrase can be made to agree
        (or a typo fixed) before the scores are taken as final."""
        text = ' '.join(str(text or '').split())
        played = self.last()
        if self.phase != HivePhase.REVEAL or not played or len(text) > ANSWER_MAX: return False
        words = played.answers.get(uid)
        if not words or not 0 <= index < len(words): return False
        words[index] = text
        return True

    def next_round(self) -> bool:
        if self.phase != HivePhase.REVEAL or self.finished: return False
        self._deal()
        self.phase = HivePhase.WRITING
        self.arm_timer()
        return True

    def restart(self):
        self.phase = HivePhase.WAITING
        self.round_number = 0
        self.question = ''
        self.answers.clear()
        self.ready.clear()
        self.revealed.clear()
        self.timer.stop()

    def set_total_rounds(self, rounds: int) -> bool:
        if not 1 <= rounds <= ROUNDS_MAX: return False
        self.total_rounds = rounds
        return True

    def set_seconds(self, seconds: int) -> bool:
        if not 0 <= seconds <= SECONDS_MAX: return False
        self.seconds = seconds
        self.arm_timer()
        return True

    def arm_timer(self):
        """One token per armed clock; the watcher that outlives this round sees a
        different token and does nothing."""
        self.timer_token += 1
        self.timer.set(self.seconds) if self.seconds and self.phase == HivePhase.WRITING \
            else self.timer.stop()

    def remove_player(self, uid: str) -> None:
        """Drop everything this player wrote, so no view renders a name that left."""
        self.answers.pop(uid, None)
        self.ready.discard(uid)
        for played in self.revealed: played.answers.pop(uid, None)


HIVEMIND = 'hivemind'
register_game(HIVEMIND, HiveMindState)
