"""SM-2 spaced repetition algorithm.

Grade meanings:
   0 = complete blackout
   1 = incorrect, but upon seeing the answer it made sense
   2 = incorrect, but the answer was easy to recall
   3 = correct with serious difficulty
   4 = correct after hesitation
   5 = perfect response
"""

from dataclasses import dataclass


@dataclass(frozen=True)
class ReviewState:
    ease_factor: float
    interval: int
    repetitions: int


MIN_EASE = 1.3
INITIAL_EASE = 2.5


def sm2(state: ReviewState, grade: int) -> ReviewState:
    if grade < 0 or grade > 5:
        raise ValueError("Grade must be 0-5")

    if grade >= 3:
        if state.repetitions == 0:
            interval = 1
        elif state.repetitions == 1:
            interval = 6
        else:
            interval = round(state.interval * state.ease_factor)
        repetitions = state.repetitions + 1
    else:
        interval = 1
        repetitions = 0

    ease = state.ease_factor + (0.1 - (5 - grade) * (0.08 + (5 - grade) * 0.02))
    ease = max(ease, MIN_EASE)

    return ReviewState(ease_factor=ease, interval=interval, repetitions=repetitions)
