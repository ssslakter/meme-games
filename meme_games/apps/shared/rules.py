__all__ = ['RULES', 'GAMES_WITH_RULES', 'game_rules']


CODENAMES_RULES = '''# Codenames

Two teams, red and blue, race to find their own agents among 25 word cards.
Each team has one spymaster who can see every card's colour, and one or more
operatives who see only the words. The spymaster gives clues; the operatives
guess. Winning means revealing all of your own team's cards before the other
team reveals theirs.

## Setup

While the lobby is waiting, pick a team and then a role. A team needs at least
two members and exactly one spymaster before the host can start. Once the game
starts the lobby is locked: teams and roles are fixed for the round.

The board is 25 words. The team that moves first has 9 cards, the other has 8,
7 are neutral, and 1 is the assassin (also called the bomb).

## Playing

On your team's turn the spymaster gives a clue plus a number. The clue must not
be one of the words visible on the board. The number says how many of your
cards the clue is meant to point at; your operatives get that many guesses plus
one extra.

Operatives then reveal cards one at a time. What happens depends on the colour
underneath:

- your own colour: it counts, and you may keep guessing while guesses remain
- neutral or the other team's colour: your turn ends immediately
- the assassin: the game ends at once and the other team wins

Operatives may stop early and end the turn rather than risk a bad guess. When
all of a colour's cards are revealed, that team wins - including when the other
team accidentally reveals your last card for you.

## Playing well

As spymaster, a clue linking two cards is worth more than a safe clue for one,
but a clue that also fits a neutral, an enemy card, or the assassin can lose the
round in a single guess. Say the number honestly - it is the only quantity your
operatives have.

As an operative, guess in the order you are most confident about; the strongest
match first, so a wrong turn costs the least. The bonus guess is real but
optional. If none of the remaining candidates feels like your colour, ending the
turn is a legitimate move, not a forfeit.

Fair play: the spymaster gives a clue and a number and nothing else. No hints
about position, no letters, no gestures, no commenting on guesses in progress,
and no reacting to a guess before the card is turned over. Operatives reason
only from what is publicly visible.'''


ALIAS_RULES = '''# Alias

Teams take turns. On a team's turn one of its members is the active player: they
see a word and describe it out loud, and the rest of their team shouts guesses,
against a timer. Each word guessed correctly scores a point. The first team to
reach the score limit wins.

## Setup

Create or join a team while the lobby is waiting. Up to 4 teams; a game needs at
least one team and every team needs its minimum members. The host picks the word
pack. Default settings: 60 seconds per round, first to 40 points, +1 per correct
guess, no penalty for a mistake.

## The round

Every member of the active team votes to start; the round begins when all of
them have voted. The timer starts and the active player is shown the first word.

The active player describes the word without saying it, and marks each word
either guessed (scores) or skipped, which immediately deals the next word. Words
keep coming until the timer runs out.

## Review

When time is up the round moves to review, where the other team goes through the
log of what happened and can adjust the points on any entry - taking a point
back if the word was effectively said out loud, or granting one that was
disputed. When review is confirmed, the points are added to the team's score,
the turn passes to the next team, and the next active player in that team's
rotation takes over.

A team wins when it is at or above the score limit and every team has played the
same number of rounds, so nobody wins on an extra turn.

## Playing well

As the describer, lead with the category or the strongest association, then
narrow: broad first, specific after. Short concrete clues beat long careful
sentences - the timer is the real opponent. Skip fast when a word is not landing
rather than burning fifteen seconds on it.

As a guesser, say every candidate out loud, including bad ones; only the correct
word costs nothing and a near miss tells the describer where you are.

Fair play: never say the word, any part of it, a translation of it, or a word
sharing its root. No spelling it, no rhymes, no "sounds like", no gestures at
objects in the room. The review step exists because these lines are judged by
the other team, so describing that skirts the rule usually just loses the point
later.'''


WHOAMI_RULES = '''# Who Am I

Everyone wears a hidden card that names someone or something - a character, a
person, a thing. You cannot see your own card, but everyone else can. Each
player writes the card for another player. You win by working out what is
written on yours.

## Setup

The lobby may set a topic (for example "cartoon characters", "scientists",
"things in a kitchen"). Each player writes the card for the next player in
order. The game starts when there are at least two players and every player has
a card written for them.

If the topic changes after you have written a card, your card is flagged as
written under an older topic - rewrite it to fit the new one. Cards can be
written or revised at any point, including in the middle of somebody else's
turn.

**A shared agreement, not a rule the code enforces: no two players ever have the
same card.** Before writing a card for someone, look at every card already on
the table and pick something nobody else has. Nothing in the game stops you from
duplicating a card, and nothing ever should - it is a convention players and
agents keep by hand, and every player is entitled to rely on it. Because it
holds, a card you can see is a card you do not have, which is real information
you can reason with.

## Turns

Players take turns in order. On your turn you ask a yes/no question about your
own card. The player before you in the order answers it, with yes, no, or not
sure.

- a yes lets you keep going: up to three questions per turn
- a no ends your questioning; end your turn
- three questions asked also ends the turn

When you are convinced you know your card, say it - if you are right you are
marked as having guessed and the turn order skips you from then on. The game
carries on for the players still looking.

Notes are a private scratchpad for tracking what you have learned. Depending on
the lobby setting they may be visible to others or private to you.

## Playing well

Ask questions that split the remaining possibilities roughly in half rather than
guessing at specific names early: alive or fictional, human or not, from a film
or from history. A yes buys you another question this turn, so chain from broad
to narrow while your streak lasts - and a question you expect a yes to is worth
more than a clever one that will probably end your turn.

Watch other players' questions and answers: they narrow their cards, and since
no card is duplicated, everything you learn about someone else's card is also
something yours is not.

Fair play: answer honestly to the best of your knowledge, use not sure when you
genuinely are, and never hint at someone's card outside of answering their
question. When writing a card, aim for something the player can actually reach
in a handful of questions - obscure enough to be interesting, known enough to be
guessable, and inside the topic.'''


RULES: dict[str, str] = {
    'codenames': CODENAMES_RULES,
    'alias': ALIAS_RULES,
    'whoami': WHOAMI_RULES,
}

GAMES_WITH_RULES: list[str] = list(RULES)


def game_rules(game: str) -> str | None: return RULES.get(game)
