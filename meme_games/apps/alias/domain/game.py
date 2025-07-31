from enum import auto
from itertools import cycle
from meme_games.domain import * 
from meme_games.core import *
from meme_games.apps.word_packs.domain import WordPackRepo
from .team import *
from .config import GameConfig

class StateMachine(Enum):
    def _generate_next_value_(name: str, start, count, last_values): return name.lower()
    WAITING_FOR_PLAYERS = auto()      # Waiting for all required players to connect
    VOTING_TO_START = auto()          # Team members voting to start their round
    ROUND_PLAYING = auto()            # Active round in progress
    REVIEWING = auto()                # Another team reviewing the just-finished round

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


@dataclass
class GameState:
    config: GameConfig = field(default_factory=GameConfig)
    state: StateMachine = field(default=StateMachine.WAITING_FOR_PLAYERS)
    teams: Dict[int, Team] = field(default_factory=dict)
    active_team: Optional[Team] = None
    active_player: Optional[AliasPlayer] = None
    active_word: Optional[str] = None
    guess_log: List[GuessEntry] = field(default_factory=list)
    timer: Timer = field(default_factory=Timer)

    def change_config(self, config: GameConfig):
        self.config = config

    def can_start(self) -> bool:
        return (self.state == StateMachine.WAITING_FOR_PLAYERS and
                self.config.max_teams >= len(self.teams) >= self.config.min_teams and
                all(len(team) >= self.config.min_team_players for team in self.teams.values()) and
                self.config.wordpack is not None)

    def next_state(self):
        match self.state:
            case StateMachine.WAITING_FOR_PLAYERS:
                if self.can_start(): self.start_game()
            case StateMachine.VOTING_TO_START:
                self.state = StateMachine.ROUND_PLAYING
                self.active_word = next(self.words_iterator)
                self.timer.set(self.config.time_limit)
            case StateMachine.ROUND_PLAYING:
                self.state = StateMachine.REVIEWING
            case StateMachine.REVIEWING:
                self.active_team.points = sum(g.points for g in self.guess_log)
                self.active_team.times_played += 1
                self.active_team = next(self.teams_iterator)
                self.guess_log.clear()
                self.state = StateMachine.VOTING_TO_START                
        self.reset_votes()

    def team_points(self, team: Team):
        extra = sum(g.points for g in self.guess_log)
        return team.points + extra*(team==self.active_team)

    def check_win_condition(self):
        return (any(self.team_points(t) >= self.config.max_score for t in self.teams.values()) and 
                all(t.times_played == self.active_team.times_played for t in self.teams.values()))

    def is_winner(self, team: Team): 
        if not self.check_win_condition(): return False
        winner = max(self.teams.values(), key=lambda t: self.team_points(t))
        return team==winner

    def start_game(self):
        self.state = StateMachine.VOTING_TO_START
        self.teams_iterator = cycle(self.teams.values())
        self.active_team = next(self.teams_iterator)
        self.active_player = next(self.active_team)
        words = self.config.wordpack.words
        random.shuffle(words)
        self.words_iterator = cycle(words)

    def retract_vote(self, player: AliasPlayer):
        player.voted = False
    
    def add_vote(self, player: AliasPlayer) -> bool:
        team = self.team_by_player(player)
        if not team: return False
        player.voted = True
        if not all(m.voted for m in self.active_team.members):
            return False
        return True
    
    def guess_word(self, player: AliasPlayer, correct: bool):
        if self.state != StateMachine.ROUND_PLAYING or player != self.active_player: return
        self.guess_log.append(GuessEntry(self.active_word, self.config.correct_guess_score 
                                         if correct else self.config.mistake_penalty))
        self.active_word = next(self.words_iterator) # TODO maybe if pack is empty, end round? (need to call timer.stop)

    def change_guess_points(self, guess_id: str, points: int) -> Optional[GuessEntry]:
        guess = next((g for g in self.guess_log if g.id == guess_id), None)
        if not guess: return
        guess.points = points
        return guess

    
    def reset_votes(self):
        for team in self.teams.values():
            for player in team.members:
                player.reset_votes()


    def create_team(self) -> Team:
        team = Team()
        return self.teams.setdefault(team.id, team)
        
    def delete_team(self, id: str): self.teams.pop(id, None)
        
    def team_by_player(self, player: AliasPlayer) -> Optional[Team]:
        return next((t for t in self.teams.values() if player in t), None)
    
    def remove_player(self, p: AliasPlayer):
        team = self.team_by_player(p)
        if not team: return
        team.remove_member(p)
        p.reset_votes(); p.reset_score()
        if not len(team): self.delete_team(team.id)

        

AliasLobby = Lobby[AliasPlayer, GameState]
register_lobby_type(AliasLobby)