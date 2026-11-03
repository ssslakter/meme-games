__all__ = ['HIVEMIND', 'HivePhase', 'HiveRound', 'HiveMindState', 'PROMPT_PACK',
           'TOPIC_PACK', 'normalize_answer', 'ANSWERS_PER_ROUND', 'ANSWER_MAX',
           'ROUNDS_MAX', 'DEFAULT_ROUNDS', 'SECONDS_MAX', 'DEFAULT_SECONDS']

from collections import defaultdict

from ...core import *
from ...domain import *
from ..word_packs.domain import WordPack, WordPackRepo


ANSWERS_PER_ROUND, ANSWER_MAX = 6, 60
ROUNDS_MAX, DEFAULT_ROUNDS = 20, 5
SECONDS_MAX, DEFAULT_SECONDS = 900, 120
PROMPT_PACK = 'Prompts'  # the shipped deck of prompts a lobby plays by default
TOPIC_PACK = 'Topics'    # one topic per line; a topics round deals six of them


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
    """One question, the list every player wrote for it, and what it scored.

    `kind` is `same` (a word scores when somebody else wrote it), `different`
    (when nobody else did), or `topics` (same scoring, but only within one row:
    the six cells are six topics, and row 1 does not agree with row 2).
    """
    question: str
    answers: dict[str, list[str]] = field(default_factory=dict)  # uid -> words as typed
    kind: str = 'same'
    topics: list[str] = field(default_factory=list)

    def words(self, uid: str) -> list[str]:
        """This player's non-empty words, in cell order."""
        return [word for word in self.answers.get(uid, []) if word]

    def _key(self, index: int, normalized: str):
        return (index, normalized) if self.kind == 'topics' else normalized

    def owners(self) -> dict:
        """Normalized word -> the players who wrote it. On a topics round the key is
        (row, word), so the same word on two different topics is not one answer."""
        owners = defaultdict(set)
        for uid, words in self.answers.items():
            for index, word in enumerate(words):
                if normalized := normalize_answer(word):
                    owners[self._key(index, normalized)].add(uid)
        return dict(owners)

    def matched_positions(self) -> set[tuple[str, int]]:
        """(player, cell) for every word somebody else also wrote - the case-insensitive,
        punctuation-insensitive match. This is what a manual edit re-decides."""
        owners = self.owners()
        return {(uid, index) for uid, words in self.answers.items()
                for index, word in enumerate(words)
                if (normalized := normalize_answer(word)) and len(owners[self._key(index, normalized)]) > 1}

    def scored_positions(self) -> set[tuple[str, int]]:
        """Cells that earn a point. Same and topics pay for a shared word, different
        pays for a word nobody else wrote. Topics only compare a cell with that same row."""
        owners = self.owners()
        scored = set()
        for uid, words in self.answers.items():
            for index, word in enumerate(words):
                normalized = normalize_answer(word)
                if not normalized: continue
                shared = len(owners[self._key(index, normalized)]) > 1
                if shared != (self.kind == 'different'): scored.add((uid, index))
        return scored

    def points(self) -> dict[str, int]:
        """A point for every cell of yours that scored this round."""
        scored = defaultdict(int)
        for uid, _ in self.scored_positions(): scored[uid] += 1
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
    topicpack: Optional[WordPack] = field(
        default_factory=lambda: DI.get(WordPackRepo).find(TOPIC_PACK))
    total_rounds: int = DEFAULT_ROUNDS
    seconds: int = DEFAULT_SECONDS                        # 0 means no round timer
    phase: HivePhase = HivePhase.WAITING
    round_number: int = 0
    question: str = ''
    round_topics: list[str] = field(default_factory=list)  # the six topics, this round only
    answers: dict[str, list[str]] = field(default_factory=dict)
    ready: set[str] = field(default_factory=set)
    players: set[str] = field(default_factory=set)  # seated when the match started
    same: bool = True
    different: bool = False
    topics: bool = False
    order: list[str] = field(default_factory=list)  # the prompt deck, shuffled for this match
    dealt: int = 0
    topic_order: list[str] = field(default_factory=list)  # shuffled once per match
    topic_dealt: int = 0
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

    def enabled_kinds(self) -> list[str]:
        """Round types the host turned on, in the order a match cycles through them."""
        kinds = [kind for kind, on in (('same', self.same), ('different', self.different),
                                       ('topics', self.topics)) if on]
        return kinds or ['same']

    def round_kind(self) -> str:
        kinds = self.enabled_kinds()
        return kinds[(max(self.round_number, 1) - 1) % len(kinds)]

    def deck(self) -> list[str]:
        """The questions this lobby plays, straight from the host's wordpack."""
        return self.wordpack.words if self.wordpack else []

    def topic_deck(self) -> list[str]:
        return self.topicpack.words if self.topicpack else []

    def _plays_prompts(self) -> bool:
        return self.same or self.different or not self.topics

    def can_start(self, uids: list[str]) -> bool:
        if self.phase != HivePhase.WAITING or len(uids) < 2: return False
        if self._plays_prompts() and not self.deck(): return False
        if self.topics and len(self.topic_deck()) < ANSWERS_PER_ROUND: return False
        return True

    def start(self, uids: list[str]) -> bool:
        if not self.can_start(uids): return False
        self.players = set(uids)
        self.round_number = 0
        self.revealed.clear()
        if self._plays_prompts(): self._reshuffle()
        else: self.order, self.dealt = [], 0
        if self.topics: self._shuffle_topics()
        self._deal()
        self.phase = HivePhase.WRITING
        self.arm_timer()
        return True

    def _reshuffle(self):
        self.order = list(self.deck())
        random.shuffle(self.order)
        self.dealt = 0

    def _shuffle_topics(self):
        """Once per match. Rounds then take the next six lines, so a topic is not
        repeated until that list runs out."""
        self.topic_order = list(self.topic_deck())
        random.shuffle(self.topic_order)
        self.topic_dealt = 0

    def _take_topics(self) -> list[str]:
        # shortcut: fewer than six lines left reshuffles the whole topic deck, so a line can repeat
        if self.topic_dealt + ANSWERS_PER_ROUND > len(self.topic_order): self._shuffle_topics()
        chunk = self.topic_order[self.topic_dealt:self.topic_dealt + ANSWERS_PER_ROUND]
        self.topic_dealt += ANSWERS_PER_ROUND
        return chunk

    def _deal(self):
        """The next round. A prompt past the end of its deck is shuffled and dealt again.
        A topics round takes the next six lines of the topic deck shuffled at the start."""
        self.round_number += 1
        self.answers.clear()
        self.ready.clear()
        if self.round_kind() == 'topics':
            self.question = ''
            self.round_topics = self._take_topics()
            return
        self.round_topics = []
        if self.dealt >= len(self.order): self._reshuffle()
        if not self.order:
            # shortcut: an empty deck deals a blank prompt, refuse it when a pack is chosen
            self.question = ''
            return
        self.question = self.order[self.dealt]
        self.dealt += 1

    def set_word(self, uid: str, index: int, text: str) -> bool:
        """Save one cell of this player's list. Emptying a cell drops it."""
        text = ' '.join(str(text or '').split())
        if self.phase != HivePhase.WRITING or uid not in self.players or uid in self.ready: return False
        if not 0 <= index < ANSWERS_PER_ROUND or len(text) > ANSWER_MAX: return False
        words = list(self.answers.get(uid, []))
        words += [''] * (index + 1 - len(words))
        words[index] = text
        self.answers[uid] = words
        return True

    def set_ready(self, uid: str, is_ready: bool = True) -> bool:
        """Done writing. The last player to say so closes the round."""
        if self.phase != HivePhase.WRITING or uid not in self.players: return False
        self.ready.add(uid) if is_ready else self.ready.discard(uid)
        if self.players <= self.ready: self.reveal()
        return True

    def reveal(self) -> bool:
        """Close the open round and score it; `last()` is what the board then shows."""
        if self.phase != HivePhase.WRITING: return False
        seated = set(self.players) | set(self.answers)
        self.revealed.append(HiveRound(
            self.question, {uid: self._six(self.answers.get(uid, [])) for uid in seated},
            kind=self.round_kind(), topics=list(self.round_topics)))
        self.answers.clear()
        self.ready.clear()
        self.phase = HivePhase.REVEAL
        self.timer.stop()
        return True

    def timeout(self) -> bool:
        """The clock ran out: close the round with whatever has been written."""
        if self.phase != HivePhase.WRITING: return False
        return self.reveal()

    @staticmethod
    def _six(words) -> list[str]:
        """Calibration always has six cells, so clearing one does not remove it."""
        words = list(words)[:ANSWERS_PER_ROUND]
        return words + [''] * (ANSWERS_PER_ROUND - len(words))

    def edit_word(self, uid: str, index: int, text: str) -> bool:
        """Rewrite one of the six cells. Empty is a cell, not a deleted one."""
        text = ' '.join(str(text or '').split())
        played = self.last()
        if self.phase != HivePhase.REVEAL or not played or len(text) > ANSWER_MAX: return False
        if uid not in played.answers or not 0 <= index < ANSWERS_PER_ROUND: return False
        words = self._six(played.answers[uid])
        words[index] = text
        played.answers[uid] = words
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
        self.round_topics = []
        self.answers.clear()
        self.ready.clear()
        self.players.clear()
        self.order.clear()
        self.dealt = 0
        self.topic_order.clear()
        self.topic_dealt = 0
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

    def set_kinds(self, same: bool, different: bool, topics: bool) -> bool:
        """Which round types play, in order same, different, topics. At least one.
        Locked only while a round is being written; the next deal uses the new set."""
        if self.phase == HivePhase.WRITING: return False
        if not (same or different or topics): return False
        self.same, self.different, self.topics = bool(same), bool(different), bool(topics)
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
        self.players.discard(uid)
        for played in self.revealed: played.answers.pop(uid, None)


HIVEMIND = 'hivemind'
register_game(HIVEMIND, HiveMindState)
