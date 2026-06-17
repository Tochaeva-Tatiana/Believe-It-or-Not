"""Game objects for Believe-It-or-Not."""

import random

from believe.common import RANKS, SUITS


class Card:
    """Represent one playing card."""

    def __init__(self, suit: str, rank: str) -> None:
        """Create a card with the given suit and rank."""
        if suit not in SUITS:
            raise ValueError("Unknown suit")

        if rank not in RANKS:
            raise ValueError("Unknown rank")

        self.suit = suit
        self.rank = rank

    def __str__(self) -> str:
        """Return a short text representation of the card."""
        return f"{self.rank}{self.suit}"

    def __repr__(self) -> str:
        """Return a developer representation of the card."""
        return (
            f"{self.__class__.__name__}("
            f"suit={self.suit!r}, rank={self.rank!r})"
        )

    def __eq__(self, other: object) -> bool:
        """Compare two cards by suit and rank."""
        if not isinstance(other, Card):
            return NotImplemented

        return self.suit == other.suit and self.rank == other.rank


class Deck:
    """Represent a deck of 36 playing cards."""

    def __init__(self) -> None:
        """Create a complete deck of 36 unique cards."""
        self.cards = [
            Card(suit, rank)
            for suit in SUITS
            for rank in RANKS
        ]

    def shuffle(self) -> None:
        """Shuffle the remaining cards in random order."""
        random.shuffle(self.cards)

    def card_count(self) -> int:
        """Return the number of cards remaining in the deck."""
        return len(self.cards)

    def take_card(self) -> Card:
        """Remove and return one card from the deck."""
        if not self.cards:
            raise IndexError("The deck is empty")

        return self.cards.pop()
