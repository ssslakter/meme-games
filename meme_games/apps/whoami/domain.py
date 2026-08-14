__all__ = ['WHOAMI', 'WhoAmIPhase', 'WhoAmIQuestion', 'PlayerLabel',
           'PlayerNotes', 'WhoAmIConfig', 'WhoAmIState', 'CARD_MAX', 'QUESTION_MAX',
           'NOTES_MAX', 'TOPIC_MAX', 'MAX_QUESTIONS']

from ...core import *
from ...domain import *

CARD_MAX, QUESTION_MAX, NOTES_MAX, TOPIC_MAX, MAX_QUESTIONS = 100, 300, 4000, 200, 3


class WhoAmIPhase(Enum):
    WAITING = 'waiting'
    PLAYING = 'playing'


@dataclass
class WhoAmIQuestion:
    text: str
    asker_uid: str
    answerer_uid: str
    answer: Optional[str] = None


@dataclass
class PlayerLabel:
    '''A label's placement, as an offset from the card it belongs to, so it follows the card.'''
    x: int = 0
    y: int = 0
    width: int = 0
    height: int = 0


@dataclass
class PlayerNotes:
    '''What a player owns in a Who Am I round: the label others gave them, and their own notes.'''
    label_text: str = ''
    label_tfm: Optional[PlayerLabel] = None
    notes: str = ''

    def set_notes(self, notes: str) -> None: self.notes = notes
    def set_label(self, label: str) -> None: self.label_text = label
    def set_label_transform(self, tfm: Optional[dict] = None) -> None:
        self.label_tfm = PlayerLabel(**(tfm or {}))


@dataclass
class WhoAmIConfig:
    private_notes: bool = False
    topic: str = ''


@dataclass
class WhoAmIState:
    players: dict[str, PlayerNotes] = field(default_factory=dict)
    config: WhoAmIConfig = field(default_factory=WhoAmIConfig)
    phase: WhoAmIPhase = WhoAmIPhase.WAITING
    turn_order: list[str] = field(default_factory=list)
    current_turn_uid: Optional[str] = None
    question: Optional[WhoAmIQuestion] = None
    questions_asked: int = 0

    def player(self, uid: str) -> PlayerNotes: return self.players.setdefault(uid, PlayerNotes())

    def next_player(self, uid: str, order: list[str] = None) -> Optional[str]:
        order = order or self.turn_order
        if uid not in order or len(order) < 2: return None
        return order[(order.index(uid) + 1) % len(order)]

    def previous_player(self, uid: str, order: list[str] = None) -> Optional[str]:
        order = order or self.turn_order
        if uid not in order or len(order) < 2: return None
        return order[(order.index(uid) - 1) % len(order)]

    def can_start(self, order: list[str]) -> bool:
        return len(order) >= 2 and all(self.player(uid).label_text.strip() for uid in order)

    def start(self, order: list[str]) -> bool:
        if self.phase != WhoAmIPhase.WAITING or not self.can_start(order): return False
        self.turn_order = list(order)
        self.current_turn_uid = self.turn_order[0]
        self.question = None
        self.questions_asked = 0
        self.phase = WhoAmIPhase.PLAYING
        return True

    def ask_rejection(self, member: LobbyMember, text: str) -> Optional[str]:
        text = ' '.join(text.split())
        if self.phase != WhoAmIPhase.PLAYING or member.uid != self.current_turn_uid:
            return 'Only the active player can ask a question'
        if not 1 <= len(text) <= QUESTION_MAX: return 'Question must be between 1 and 300 characters'
        if self.question and self.question.answer is None: return 'The current question must be answered first'
        if self.question and self.question.answer == 'no': return 'Your turn must end after a no answer'
        if self.questions_asked >= MAX_QUESTIONS: return 'You already asked 3 questions this turn'
        return None

    def ask(self, member: LobbyMember, text: str) -> bool:
        text = ' '.join(text.split())
        if self.ask_rejection(member, text): return False
        self.question = WhoAmIQuestion(text, member.uid, self.previous_player(member.uid))
        self.questions_asked += 1
        return True

    def answer(self, member: LobbyMember, answer: str) -> bool:
        if (answer not in ('yes', 'no', 'not_sure') or not self.question or
                self.question.answer is not None or member.uid != self.question.answerer_uid): return False
        self.question.answer = answer
        return True

    def end_turn(self, member: LobbyMember) -> bool:
        if self.phase != WhoAmIPhase.PLAYING or member.uid != self.current_turn_uid: return False
        self.current_turn_uid = self.next_player(member.uid)
        self.question = None
        self.questions_asked = 0
        return True

    def restart(self):
        self.phase = WhoAmIPhase.WAITING
        self.current_turn_uid = None
        self.question = None
        self.questions_asked = 0
        for player in self.players.values():
            player.label_text = player.notes = ''

    def remove_player(self, uid: str) -> None:
        self.players.pop(uid, None)
        if uid in self.turn_order: self.turn_order.remove(uid)
        if self.current_turn_uid == uid:
            self.current_turn_uid = self.turn_order[0] if self.turn_order else None
            self.questions_asked = 0
        if self.question and uid in (self.question.asker_uid, self.question.answerer_uid): self.question = None

    def to_dict(self):
        return {**asdict(self), 'phase': self.phase.value}

    @classmethod
    def from_dict(cls, data: dict) -> 'WhoAmIState':
        def sub(sub_cls: type, raw: Optional[dict]): return sub_cls(**raw) if raw else None
        players = {}
        for uid, raw in data.get('players', {}).items():
            raw = {key: value for key, value in raw.items() if key != 'card_pos'}
            players[uid] = PlayerNotes(**{**raw, 'label_tfm': sub(PlayerLabel, raw.get('label_tfm'))})
        question = data.get('question')
        return cls(players=players,
                   config=WhoAmIConfig(**data.get('config', {})),
                   phase=WhoAmIPhase(data.get('phase', WhoAmIPhase.WAITING.value)),
                   turn_order=data.get('turn_order', []),
                   current_turn_uid=data.get('current_turn_uid'),
                   question=WhoAmIQuestion(**question) if question else None,
                   questions_asked=data.get('questions_asked', 1 if question else 0))


WHOAMI = 'whoami'
register_game(WHOAMI, WhoAmIState, persist=True)
