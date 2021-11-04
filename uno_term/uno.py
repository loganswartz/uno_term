#!/usr/bin/env python3

# Imports {{{
# builtins
from dataclasses import dataclass, field
from enum import Enum
import getpass
import random
import re
import textwrap
from typing import Iterable, List, NamedTuple, Optional, Union

# 3rd party
from colorama import Fore, Back, Style, init

# local modules

# }}}


# TODO
# reshuffle deck when the draw pile runs out
# evaluate actions when they are the first card of the game
#    i.e. game starts, and the top card flipped over is a Draw Two
#    (currently we just walk through the deck until with find a numeric card)


# enable colors in the terminal
init(autoreset=True)


class CardColor(Enum):
    """
    The color of a card.

    Wilds have no color until they are played, when the player decides what
    color they will become.
    """

    Red = 1
    Blue = 2
    Green = 3
    Yellow = 4


class CardType(Enum):
    """
    The face value of a card.

    The numbered cards have enum values matching their number.
    """

    Zero = 0
    One = 1
    Two = 2
    Three = 3
    Four = 4
    Five = 5
    Six = 6
    Seven = 7
    Eight = 8
    Nine = 9
    Skip = 10
    Reverse = 11
    DrawTwo = 12
    WildDrawFour = 13
    Wild = 14

    @property
    def isWild(self):
        return self in [CardType.Wild, CardType.WildDrawFour]

    @classmethod
    def numerics(cls):
        """
        Return all non-Wild types.
        """
        return [type for type in cls if not type.isWild]

    @classmethod
    def wilds(cls):
        """
        Return all Wild types.
        """
        return [type for type in cls if type.isWild]

    @classmethod
    def numbers(cls):
        """
        Return all numeric types.
        """
        return [type for type in cls if type.value <= 9]

    @classmethod
    def draws(cls):
        """
        Return all types that trigger a player to draw cards.
        """
        return [
            type for type in cls if type in [CardType.DrawTwo, CardType.WildDrawFour]
        ]

    @property
    def draw_amount(self):
        """
        Get the amount of cards this card makes you draw.
        """
        amounts = {
            CardType.WildDrawFour: 4,
            CardType.DrawTwo: 2,
        }
        return amounts.get(self, 0)


@dataclass
class Card:
    """
    A simple representation of an UNO card.

    Has both a type (the face value) and a color. Wilds initially have no color,
    and acquire a color after being played.
    """

    color: Optional[CardColor]
    type: CardType

    def __str__(self):
        label = [word for word in re.split("(?=[A-Z])", self.type.name) if word]
        type = str(self.type.value) if self.type.value <= 9 else " ".join(label)
        color = self.color.name if self.color else None

        if self.type.isWild:
            return colored(f"{type} ({color})", fore=self.color) if color else type
        else:
            return colored(f"{color or 'Unknown'} {type}", fore=self.color)


class ActionType(Enum):
    """
    The types of actions a player can take in their turn.
    """

    Draw = 1
    Play = 2


class PlayerAction(NamedTuple):
    """
    Represents an action taken by a player.

    Players may only take one action per turn.
    """

    type: ActionType
    card: Optional[Card]


class Deck(list):
    """
    A complete deck of UNO cards.

    A deck should be created for a single game, and then dealt out to players
    and split into piles.
    """

    def __init__(self):
        self.extend(self.standard_deck())
        self.shuffle()

    @staticmethod
    def standard_deck():
        """
        Create a standard deck.
        """
        # create 4 of each type of wild
        wilds = [Card(None, type) for type in CardType.wilds() for _ in range(4)]
        # https://stackoverflow.com/a/45079294
        # the above is equivalent to:
        #
        # wilds = []
        # for type in CardType.wilds():
        #     for _ in range(4):
        #         card = Card(None, type)
        #         wilds.append(card)

        # make 2 of each type of non-wild card, for each color
        normal = []
        for color in CardColor:
            for type in CardType.numerics():
                # 2 copies of each card per color, except zero which only gets one per color
                qty = 1 if type is CardType.Zero else 2
                for _ in range(qty):
                    normal.append(Card(color, type))

        return [*normal, *wilds]  # combine the lists

    def shuffle(self):
        random.shuffle(self)


class Pile(list):
    """
    Simple convience class for representing piles.

    We could probably get away with using a regular list, but I wanted to add
    some of these convenience methods to cut down on boilerplate code.
    """

    def play(self, card: Card):
        self.append(card)

    def take(self, number: int = 1):
        return [self.pop() for _ in range(number)]

    @property
    def top_card(self):
        return self[-1]


@dataclass
class Player:
    """
    A player in the game.

    Players have a name and a hand of cards, which starts out empty. We'll deal
    out cards to them when the game starts.
    """

    name: str
    hand: List[Card] = field(default_factory=list)

    def find_card(self, color: Optional[CardColor], type: CardType):
        """
        Find a card of the given type and color in your hand.

        Returns the index of the card in their hand, and the card itself.
        (The card is not removed from your hand)
        """

        def matches_card(card: Card):
            return card.color is color and card.type is type

        idx, card = next(
            ((idx, card) for idx, card in enumerate(self.hand) if matches_card(card)),
            (None, None),
        )

        return idx, card

    def play_card(self, color: Optional[CardColor], type: CardType):
        """
        Play a card of the given type and color from your hand.

        Returns the played card and removes it from your hand.
        """
        idx, card = self.find_card(color, type)

        # if card not found or failed to play card
        if card is None or idx is None:
            return None

        # remove played card from hand
        self.hand.pop(idx)

        return card

    def take_cards(self, cards: Union[Card, List[Card]]):
        """
        Add the given cards to your hand.
        """
        if isinstance(cards, list):
            self.hand.extend(cards)
        else:
            self.hand.append(cards)

    def take_from_pile(self, pile: Pile, qty: int = 1):
        """
        Take <qty> cards from the top of the pile and add them to your hand.
        """
        cards = pile.take(qty)
        self.take_cards(cards)
        return cards

    @property
    def has_no_cards(self):
        return len(self.hand) == 0

    def get_action(self, current: Card):
        """
        Ask for the desired action during your turn.

        The player is allowed to either draw a new card, or play a card from
        their hand. If the player starts the turn and has no valid cards to
        play, they'll first be forced to draw a card.

        Whatever the user types is parsed to determine:
            1) if they want to draw a new card, or
            2) what color and type of card they want to play.

        The action is then returned, and the game will evaluate it.
        """
        print("Your cards:")
        sorted_hand = self.sort_cards_by_color(self.sort_cards_by_value(self.hand))
        print(textwrap.indent("\n".join(str(card) for card in sorted_hand), "  "))

        card = None
        color = None
        type = None
        valid = None
        while type is None or not valid:
            print("If you would like to draw a card, enter 'draw'.")
            print("If you would like to play a card, enter the color and value as shown above.")
            choice = input("What card would you like to play?\n=> ").strip()
            if choice.lower() in ["draw", "draw card"]:
                return PlayerAction(ActionType.Draw, None)

            # parse their answer
            color, type = parse_to_enums(choice)

            if type is None:
                print("Unable to parse choice, try again.")
                continue

            _, card = self.find_card(color, type)
            if not card:
                print("You don't have that card.")
                continue

            valid = is_valid_play(current, card)
            if not valid:
                print("You can't play that card.")
                continue

        card = self.play_card(color, type)
        return PlayerAction(ActionType.Play, card)

    @staticmethod
    def sort_cards_by_color(cards: List[Card]):
        def sort(card):
            return card.color.value if card.color else 0

        return sorted(cards, key=sort)

    @staticmethod
    def sort_cards_by_value(cards: List[Card]):
        def sort(card):
            return card.type.value

        return sorted(cards, key=sort)

    def has_valid_play(self, current: Card):
        """
        Check if the user has any valid cards to play in their hand.
        """
        return any(is_valid_play(current, card) for card in self.hand)


def colored(text: str = None, fore: CardColor = None, back: CardColor = None):
    """
    Utility method for coloring printed text.
    """
    if text is None:
        return ""

    codes = [
        getattr(Fore, fore.name.upper()) if fore else None,
        getattr(Back, back.name.upper()) if back else None,
    ]
    prefix = "".join(code for code in codes if code)
    return prefix + text + Style.RESET_ALL


def parse_to_enums(input: str):
    """
    Parse a string to a CardColor + CardType pair.
    """
    words = input.split()
    try:
        color = parse_color(words[0])
        type_names = words[1:] if color is not None else words
        type = parse_type(" ".join(type_names))
    except IndexError:
        color = None
        type = None

    return color, type


def parse_color(input: str):
    """
    Parse a string to a CardColor enum.
    """
    try:
        color = CardColor[input.capitalize()]
    except KeyError:
        color = None

    return color


def parse_type(input: str):
    """
    Parse a string to a CardType enum.
    """
    type = "".join(word.capitalize() for word in input.split())

    try:
        type = CardType(int(type))
    except ValueError:
        try:
            type = CardType[type]
        except KeyError:
            type = None

    return type


def is_valid_play(current: Card, playing: Card):
    """
    Check if a card (playing) is allowed to be played on the current card.
    """
    return (
        playing.type.isWild
        or playing.color is current.color
        or playing.type is current.type
    )


class Game(object):
    """
    A single game of UNO.

    Start a game by creating a Game instance with the list of players, and then
    calling Game.run(). The run() method will return the winning player when the
    game is completed.
    """

    def __init__(self, players: List[Player], initial_hand_size: int = 7):
        self.players = players
        deck = Deck()
        for _ in range(initial_hand_size):
            for player in self.players:
                player.take_cards(deck.pop())

        while True:
            top_card = deck.pop()
            if top_card.type in CardType.numbers():
                break
            else:
                deck.insert(0, top_card)

        self.discard_pile = Pile([top_card])
        self.draw_pile = Pile(deck)
        self.turn_cycle = Cycle(self.players)

    def run(self):
        """
        Run the game.

        Returns the winning player.
        """
        winner = None
        player: Player = self.turn_cycle.current

        # each loop represents a player turn
        while not winner:
            clear()
            print(f"It's {player.name}'s turn!")
            current = self.discard_pile.top_card
            print(f"The current card is a {current}.")

            # force the player to draw if they don't have any valid cards
            skip = False
            if not player.has_valid_play(current):
                draw = player.take_from_pile(self.draw_pile).pop()
                print(f"You had no valid cards, so you drew a {draw}.")

            card = None
            # allow player to play card if the one they drew is valid
            if player.has_valid_play(current):
                action, card = player.get_action(self.discard_pile.top_card)

                # immediately end the game (break the loop) if a player wins
                if player.has_no_cards:
                    winner = player
                    break

                if action is ActionType.Draw:
                    draw = player.take_from_pile(self.draw_pile, 1).pop()
                    print(f"You drew a {draw}.")

                skip = False
                # execute side affects for special cards
                if card is not None:
                    next_player = self.turn_cycle.peek_next()

                    # reverses
                    if card.type is CardType.Reverse:
                        self.turn_cycle.reverse()
                        print(f"{player.name} played a reverse!")
                    # draw twos and draw fours
                    elif card.type in CardType.draws():
                        draw_amount = card.type.draw_amount
                        print(f"{next_player.name} draws {draw_amount} cards!")
                        next_player.take_from_pile(self.draw_pile, draw_amount)
                    # skips
                    elif card.type is CardType.Skip:
                        print(f"{next_player.name} was skipped!")
                        skip = True

                    # if a wild is played, the player must assign a color
                    if card.type.isWild:
                        while card.color is None:
                            card.color = parse_color(
                                input(f"What color should the {card} become? ")
                            )
                            if card.color is None:
                                valid = ", ".join(color.name for color in CardColor)
                                print(f"Please pick one of the following: {valid}")

                    # put the played card on the top of the discard pile
                    self.discard_pile.play(card)

            getpass.getpass(prompt="(Press enter to end your turn)")
            print("\n")
            player = self.turn_cycle.next(skip=skip)

        return winner


class Cycle(list):
    """
    A simple convience class to track the turns of the game.

    Initiate with a list of objects to track, and call Cycle.next() to get the
    next item in the cycle. Cycle.reverse() will change the direction that
    Cycle.next() takes you, and it will automatically loop around when the end
    of the cycle is reached.

    Use Cycle.current to get the currently selected item without changing
    anything.
    """

    def __init__(self, lst: Iterable, *args, **kwargs):
        self.pointer = 0
        self.reversed = False
        super().__init__(lst, *args, **kwargs)

    def __getitem__(self, idx: int):
        return super().__getitem__(self.wrapped(idx))

    def wrapped(self, index: int):
        return index % len(self)

    def advance(self, step: int):
        calculated = self.pointer + (-step if self.reversed else step)
        self.pointer = self.wrapped(calculated)
        return self.pointer

    def next(self, step: int = 1, skip: bool = False):
        return self[self.advance(step + (1 if skip else 0))]

    def peek_next(self, step: int = 1):
        return self[self.pointer + step]

    def previous(self, step: int = 1):
        return self[self.advance(-step)]

    def reverse(self):
        self.reversed = not self.reversed

    @property
    def current(self):
        return self[self.pointer]


def get_players():
    """
    Prompt the user for all the participating players.

    Officially, UNO is for 2 to 10 players, so anything outside that range is
    not allowed.
    """

    def get_ordinal_suffix(number: int):
        """
        Get the ordinal suffix for a given number.
        """
        numeral = number % 10
        suffixes = {
            1: "st",
            2: "nd",
            3: "rd",
        }
        # suffix is "th" for all numbers that don't end in 1, 2, or 3
        return suffixes.get(numeral, "th")

    def get_ordinal(number: int):
        """
        Converts a number to its ordinal form.

        Ex: 1 becomes 1st, 3 becomes 3rd, 14 becomes 14th, etc.
        """
        return f"{number}{get_ordinal_suffix(number)}"

    def prompt_name(index: int):
        return input(f"What is the {get_ordinal(index + 1)} player's name? ")

    # make sure we get a valid number of players
    number = None
    while not number:
        try:
            value = int(input("How many are playing? [2-10] "))
            if value not in range(2, 10):
                raise ValueError
            number = value
        except ValueError:
            print("You must pick a number between 2 and 10.")

    # collect the player names and convert to Player objects
    names = [prompt_name(idx) for idx in range(number)]
    return [Player(name) for name in names]


def main():
    """
    Main flow of the program.

    Prompts for players, then creates a new Game and starts it. When the game
    completes, the winner is announced and we ask the players if they want to
    play again.
    """
    winner = None
    players = None
    play = True

    while play:
        if not players or not bool_prompt("Use the same players?"):
            players = get_players()
        game = Game(players)
        winner = game.run()
        msg = f"  {winner.name} is the winner!  "
        print(f"\n\n{'*'*len(msg)}\n{msg}\n{'*'*len(msg)}\n\n")
        play = bool_prompt("Play again?")


def bool_prompt(prompt: str = "Continue?"):
    """
    Convenience method for getting answers to yes/no questions.
    """
    return input(prompt.strip() + " [y/n] ").strip().casefold() in ["y", "yes"]


def clear():
    """
    Clear all existing text from the console window.

    Not sure if this will work on Windows.
    """
    print(chr(27) + "[2j")
    print("\033c")
    print("\x1bc")


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\nBye!")
