__all__ = ['HIVEMIND', 'HivePhase', 'HiveRound', 'HiveMindState', 'PROMPT_PACK',
           'normalize_answer', 'ANSWER_MAX', 'ROUNDS_MAX', 'DEFAULT_ROUNDS']

from collections import defaultdict

from ...core import *
from ...domain import *
from ..word_packs.domain import WordPack, WordPackRepo


ANSWER_MAX, ROUNDS_MAX, DEFAULT_ROUNDS = 60, 20, 5
PROMPT_PACK = 'Prompts'  # the shipped deck of prompts a lobby plays by default


class HivePhase(Enum):
    WAITING = 'waiting'
    WRITING = 'writing'      # the question is up, answers are hidden
    REVEAL = 'reveal'        # this round is scored and on the table


def normalize_answer(text: str) -> str:
    """Answers agree when they read the same, whatever the capitals, spacing or
    trailing punctuation - so "Pizza!", "pizza" and "  pizza " are one answer."""
    return ' '.join(str(text or '').casefold().split()).strip('.,!?;:')


@dataclass
class HiveRound:
    """One question, what everyone wrote for it, and what it scored."""
    question: str
    answers: dict[str, str] = field(default_factory=dict)  # uid -> answer as typed

    def groups(self) -> dict[str, list[str]]:
        """Normalized answer -> the players who wrote it, for every answer two or more
        players share, biggest group first."""
        by_answer = defaultdict(list)
        for uid, text in self.answers.items():
            if normalized := normalize_answer(text): by_answer[normalized].append(uid)
        shared = ((answer, uids) for answer, uids in by_answer.items() if len(uids) > 1)
        return dict(sorted(shared, key=lambda item: (-len(item[1]), item[0])))

    def uniques(self) -> dict[str, str]:
        """The players whose answer nobody else wrote - this round scored nothing for
        them."""
        matched = {uid for uids in self.groups().values() for uid in uids}
        return {uid: text for uid, text in self.answers.items() if uid not in matched}

    def points(self) -> dict[str, int]:
        """A point for everyone who agreed with someone else. A group of two and a
        group of five pay the same."""
        return {uid: 1 for uids in self.groups().values() for uid in uids}


@dataclass
class HiveMindState:
    """The host's wordpack, the round in progress, and every round already revealed.

    Answers live in `answers` only while the round is open; revealing moves them into
    `revealed`, which is the only record the board reads.
    """
    wordpack: Optional[WordPack] = field(
        default_factory=lambda: DI.get(WordPackRepo).find(PROMPT_PACK))
    total_rounds: int = DEFAULT_ROUNDS
    phase: HivePhase = HivePhase.WAITING
    round_number: int = 0
    question: str = ''
    answers: dict[str, str] = field(default_factory=dict)
    revealed: list[HiveRound] = field(default_factory=list)

    @property
    def finished(self) -> bool:
        """The last round is on the table, so there is nothing left to deal."""
        return self.phase == HivePhase.REVEAL and self.round_number >= self.total_rounds

    def last(self) -> Optional[HiveRound]: return self.revealed[-1] if self.revealed else None

    def totals(self) -> dict[str, int]:
        """Running score: a point for every revealed round the player agreed in."""
        sums = defaultdict(int)
        for played in self.revealed:
            for uid, points in played.points().items(): sums[uid] += points
        return dict(sums)

    def score(self, uid: str) -> int: return self.totals().get(uid, 0)

    def answered(self, uids: list[str]) -> int:
        """How many players have an answer in - a count, never a name."""
        return sum(1 for uid in uids if normalize_answer(self.answers.get(uid)))

    def all_answered(self, uids: list[str]) -> bool:
        return bool(uids) and self.answered(uids) == len(uids)

    def has_answer(self, uid: str) -> bool: return bool(normalize_answer(self.answers.get(uid)))

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
        return True

    def _deal(self):
        """The next question, cycling the deck when the host asked for more rounds than
        it holds."""
        deck = self.deck()
        self.round_number += 1
        self.question = deck[(self.round_number - 1) % len(deck)]
        self.answers.clear()

    def submit(self, uid: str, text: str) -> bool:
        """Take or replace this player's answer for the open round."""
        text = ' '.join(str(text or '').split())
        if self.phase != HivePhase.WRITING or not 1 <= len(text) <= ANSWER_MAX: return False
        self.answers[uid] = text
        return True

    def reveal(self) -> bool:
        """Close the open round and score it; `last()` is what the board then shows."""
        if self.phase != HivePhase.WRITING: return False
        self.revealed.append(HiveRound(self.question, dict(self.answers)))
        self.answers.clear()
        self.phase = HivePhase.REVEAL
        return True

    def next_round(self) -> bool:
        if self.phase != HivePhase.REVEAL or self.finished: return False
        self._deal()
        self.phase = HivePhase.WRITING
        return True

    def restart(self):
        self.phase = HivePhase.WAITING
        self.round_number = 0
        self.question = ''
        self.answers.clear()
        self.revealed.clear()

    def set_total_rounds(self, rounds: int) -> bool:
        if not 1 <= rounds <= ROUNDS_MAX: return False
        self.total_rounds = rounds
        return True

    def remove_player(self, uid: str) -> None:
        """Drop everything this player wrote, so no view renders a name that left."""
        self.answers.pop(uid, None)
        for played in self.revealed: played.answers.pop(uid, None)


HIVEMIND = 'hivemind'
register_game(HIVEMIND, HiveMindState)
