from itertools import cycle
from meme_games.domain import * 
from meme_games.core import *
from meme_games.apps.word_packs.domain import WordPackRepo
from .team import *
from .config import GameConfig

class StateMachine(Enum):
    def _generate_next_value_(name: str, start, count, last_values): return name.lower()
    WAITING_FOR_PLAYERS = auto()      # Waiting for all required players to connect
    COLLECTING_WORDS = auto()         # Players are building the shared word pool
    BETWEEN_WORD_ROUNDS = auto()
    VOTING_TO_START = auto()          # Team members voting to start their round
    ROUND_PLAYING = auto()            # Active round in progress
    REVIEWING = auto()                # Another team reviewing the just-finished round
    FINISHED = auto()

    def pretty(self) -> str:
        # Convert "waiting_for_players" → "Waiting for players"
        return self.value.replace("_", " ").capitalize()

    def __str__(self) -> str:
        return self.pretty()

@dataclass
class GuessEntry:
    word: str
    points: int
    id: str = field(default_factory=random_id)
    skipped: Optional[bool] = None

    def was_skipped(self) -> bool:
        return self.skipped if self.skipped is not None else self.points <= 0


@dataclass
class GameState:
    config: GameConfig = field(default_factory=GameConfig)
    state: StateMachine = field(default=StateMachine.WAITING_FOR_PLAYERS)
    teams: Dict[int, Team] = field(default_factory=dict)
    active_team: Optional[Team] = None
    active_player: Optional[LobbyMember] = None
    active_guesser: Optional[LobbyMember] = None
    review_team: Optional[Team] = None
    review_player: Optional[LobbyMember] = None
    review_guesser: Optional[LobbyMember] = None
    active_word: Optional[str] = None
    submitted_words: Dict[str, List[str]] = field(default_factory=dict)
    submitted_players: set[str] = field(default_factory=set)
    word_pool: List[str] = field(default_factory=list)
    skipped_words: List[str] = field(default_factory=list)
    all_words: List[str] = field(default_factory=list)
    word_round: int = 1
    leader_index: int = 0
    guesser_offset: int = 1
    guess_log: List[GuessEntry] = field(default_factory=list)
    votes: set[str] = field(default_factory=set)
    timer: Timer = field(default_factory=Timer)

    def has_voted(self, player: LobbyMember) -> bool: return player.uid in self.votes

    def all_voted(self, team: Team) -> bool: return all(self.has_voted(m) for m in team.members)

    def all_players_voted(self) -> bool:
        players = [member for team in self.teams.values() for member in team.members]
        return bool(players) and all(self.has_voted(member) for member in players)

    def hides_skipped_words(self) -> bool:
        return self.config.player_words or self.config.hide_skipped_words

    def change_config(self, config: GameConfig):
        self.config = config

    def can_start(self) -> bool:
        return (self.state == StateMachine.WAITING_FOR_PLAYERS and
                self.config.max_teams >= len(self.teams) >= self.config.min_teams and
                all(len(team) >= self.config.min_team_players for team in self.teams.values()) and
                (self.config.player_words or self.config.wordpack is not None))

    def next_state(self, reset_votes: bool = True) -> None:
        match self.state:
            case StateMachine.WAITING_FOR_PLAYERS:
                if self.can_start(): self.start_game()
            case StateMachine.VOTING_TO_START:
                self.state = StateMachine.ROUND_PLAYING
                self.active_word = self.next_word()
                self.timer.set(self.config.time_limit)
            case StateMachine.BETWEEN_WORD_ROUNDS:
                self.start_word_round(self.all_words, round_number=2)
                self.state = StateMachine.ROUND_PLAYING
                self.active_word = self.next_word()
                self.timer.set(self.config.time_limit)
            case StateMachine.ROUND_PLAYING:
                self.review_team = self.active_team
                self.review_player = self.active_player
                self.review_guesser = self.active_guesser
                self.active_team.times_played += 1
                self.advance_turn()
                self.state = StateMachine.REVIEWING
            case StateMachine.REVIEWING:
                points = sum(g.points for g in self.guess_log)
                if len(self.teams) == 1:
                    self.review_player.add_score(points)
                    if self.review_guesser and self.review_guesser != self.review_player:
                        self.review_guesser.add_score(points)
                else:
                    self.review_team.points += points
                self.review_team = self.review_player = self.review_guesser = None
                self.guess_log.clear()
                if self.config.player_words and not self.word_pool and not self.skipped_words and self.active_word is None:
                    self.state = (StateMachine.FINISHED if self.word_round == 2 else
                                  StateMachine.BETWEEN_WORD_ROUNDS)
                    if self.state == StateMachine.BETWEEN_WORD_ROUNDS: self.reset_votes()
                else:
                    self.state = StateMachine.VOTING_TO_START
        if reset_votes: self.reset_votes()

    def team_points(self, team: Team):
        extra = sum(g.points for g in self.guess_log)
        return team.points + extra*(team==self.review_team)

    def player_points(self, player: LobbyMember):
        extra = sum(g.points for g in self.guess_log)
        return player.score + extra * (player in (self.review_player, self.review_guesser))

    def check_win_condition(self) -> bool:
        if self.config.player_words: return self.state == StateMachine.FINISHED
        if self.state == StateMachine.FINISHED: return True
        if len(self.teams) == 1:
            team = next(iter(self.teams.values()))
            return (len(team) and team.times_played >= len(team) and
                    team.times_played % len(team) == 0 and
                    max(self.player_points(member) for member in team.members) >= self.config.max_score)
        return (any(self.team_points(t) >= self.config.max_score for t in self.teams.values()) and 
                all(t.times_played == self.active_team.times_played for t in self.teams.values()))

    def is_winner(self, team: Team): 
        if len(self.teams) == 1: return False
        if not self.check_win_condition(): return False
        winner = max(self.teams.values(), key=lambda t: self.team_points(t))
        return team==winner

    def is_player_winner(self, player: LobbyMember):
        return (len(self.teams) == 1 and self.check_win_condition() and
                self.player_points(player) == max(self.player_points(member) for member in self.active_team.members))

    def start_game(self):
        self.teams_iterator = cycle(self.teams.values())
        self.active_team = next(self.teams_iterator)
        if len(self.teams) == 1:
            self.leader_index, self.guesser_offset = 0, 1
            self.set_pair()
        else: self.active_player = next(self.active_team)
        if self.config.player_words:
            self.state = StateMachine.COLLECTING_WORDS
            self.timer.set(self.config.word_collection_time)
            return
        self.start_word_round(self.config.wordpack.words)
        self.state = StateMachine.VOTING_TO_START

    def start_word_round(self, words: List[str], round_number: int = 1) -> None:
        self.word_round = round_number
        self.all_words = list(words)
        self.word_pool = list(words)
        self.skipped_words.clear()
        random.shuffle(self.word_pool)
        if not self.config.player_words: self.words_iterator = cycle(tuple(self.word_pool))

    def next_word(self) -> Optional[str]:
        if self.word_pool: return self.word_pool.pop()
        if self.config.player_words and self.skipped_words:
            self.word_pool, self.skipped_words = self.skipped_words, []
            random.shuffle(self.word_pool)
            return self.word_pool.pop()
        if not self.config.player_words: return next(self.words_iterator)

    def submit_words(self, player: LobbyMember, words: str, finalized: bool = False) -> bool:
        if (self.state != StateMachine.COLLECTING_WORDS or not self.team_by_player(player) or
                player.uid in self.submitted_players): return False
        self.submitted_words[player.uid] = [word.strip() for word in words.splitlines() if word.strip()]
        if finalized: self.submitted_players.add(player.uid)
        return True

    def finish_word_collection(self) -> bool:
        words = list(dict.fromkeys(word for submitted in self.submitted_words.values() for word in submitted))
        if not words: return False
        self.start_word_round(words)
        self.state = StateMachine.VOTING_TO_START
        return True

    def restart(self):
        self.timer.stop()
        self.state = StateMachine.WAITING_FOR_PLAYERS
        self.active_team = self.active_player = self.active_guesser = self.active_word = None
        self.review_team = self.review_player = self.review_guesser = None
        self.submitted_words.clear()
        self.submitted_players.clear()
        self.word_pool.clear()
        self.skipped_words.clear()
        self.all_words.clear()
        self.word_round = 1
        self.leader_index, self.guesser_offset = 0, 1
        self.guess_log.clear()
        self.reset_votes()
        for team in self.teams.values():
            team.points = team.times_played = 0
            for member in team.members: member.reset_score()
        for attr in ('teams_iterator',):
            if hasattr(self, attr): delattr(self, attr)

    def advance_turn(self):
        team = self.active_team
        if len(self.teams) > 1:
            self.active_team = next(self.teams_iterator)
            self.active_player = next(self.active_team)
        else:
            if len(team) > 1:
                self.leader_index = (self.leader_index + 1) % len(team)
                if self.leader_index == 0:
                    self.guesser_offset = self.guesser_offset % (len(team) - 1) + 1
            self.set_pair()

    def set_pair(self):
        team = self.active_team
        self.active_player = team.members[self.leader_index]
        self.active_guesser = team.members[(self.leader_index + self.guesser_offset) % len(team)]

    def shuffle_teams(self):
        sizes = [len(team.members) for team in self.teams.values()]
        members = [member for team in self.teams.values() for member in team.members]
        random.shuffle(members)
        offset = 0
        for team, size in zip(self.teams.values(), sizes):
            team.members[:] = members[offset:offset + size]
            offset += size

    def retract_vote(self, player: LobbyMember):
        self.votes.discard(player.uid)

    def add_vote(self, player: LobbyMember):
        if self.team_by_player(player): self.votes.add(player.uid)

    def check_all_voted(self):
        return self.all_voted(self.active_team)

    def guess_word(self, player: LobbyMember, correct: bool) -> bool:
        if self.state != StateMachine.ROUND_PLAYING or player != self.active_player: return False
        self.guess_log.append(GuessEntry(self.active_word, self.config.correct_guess_score
                                         if correct else self.config.mistake_penalty, skipped=not correct))
        if self.config.player_words and not correct: self.skipped_words.append(self.active_word)
        self.active_word = self.next_word()
        return self.active_word is None

    def change_guess_points(self, guess_id: str, delta: int) -> Optional[GuessEntry]:
        guess = next((g for g in self.guess_log if g.id == guess_id), None)
        if not guess: return
        guess.points += delta
        return guess

    
    def reset_votes(self): self.votes.clear()

    def create_team(self) -> Team:
        team = Team()
        return self.teams.setdefault(team.id, team)

    def delete_team(self, id: str): self.teams.pop(id, None)

    def team_by_player(self, player: LobbyMember) -> Optional[Team]:
        return next((t for t in self.teams.values() if player in t), None)

    def remove_player(self, uid: str):
        self.votes.discard(uid)
        removed = [m for team in self.teams.values() for m in team.members if m.uid == uid]
        for team in list(self.teams.values()):
            had_member = any(m.uid == uid for m in team.members)
            team.members[:] = [m for m in team.members if m.uid != uid]
            if had_member and not len(team): self.delete_team(team.id)
        if removed: removed[0].reset_score()


ALIAS = 'alias'
register_game(ALIAS, GameState)
