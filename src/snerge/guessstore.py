#!/usr/bin/env python3
# SPDX-FileCopyrightText: 2023 Kitsune
#
# SPDX-License-Identifier: BSD-2-Clause


from __future__ import annotations

import statistics


class GuessStore:
    use_latest_reply: bool
    guesses: dict[str, int]

    def __init__(self, use_latest_reply: bool = True):
        self.use_latest_reply = use_latest_reply
        self.guesses = {}

    def accept_guess(self, name: str, value: int) -> None:
        if self.use_latest_reply:
            self.guesses[name] = value
        else:
            if name not in self.guesses:
                self.guesses[name] = value

    def get_score(
        self, value: float, closest_without_going_over: bool
    ) -> tuple[list[str], set[int]]:
        # Find the score value to use as a result

        if closest_without_going_over:
            winning_values = {max(val for val in self.guesses.values() if val <= value)}
        else:
            diffs = [(i, abs(i - value)) for i in self.guesses.values()]
            min_diff = min(diff[1] for diff in diffs)
            winning_values = {diff[0] for diff in diffs if diff[1] == min_diff}

        winners = [name for name, guess in self.guesses.items() if guess in winning_values]

        return winners, winning_values

    def num_replies(self) -> int:
        return len(self.guesses)

    def stats(self) -> dict[str, int | float | list[float]]:
        raw_values = list(self.guesses.values())

        return {
            "count": self.num_replies(),
            "min": min(raw_values) if raw_values else 0,
            "max": max(raw_values) if raw_values else 0,
            "mean": statistics.mean(raw_values) if raw_values else 0,
            "stdev": statistics.stdev(raw_values) if len(raw_values) > 1 else 0,
            "median": statistics.median(raw_values) if raw_values else 0,
        }
