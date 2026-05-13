from app.spaced_repetition import MIN_EASE, ReviewState, sm2


def test_sm2_perfect_first_time():
    result = sm2(ReviewState(ease_factor=2.5, interval=0, repetitions=0), grade=5)
    assert result.interval == 1
    assert result.repetitions == 1
    assert result.ease_factor == 2.5 + 0.1


def test_sm2_perfect_second_time():
    result = sm2(ReviewState(ease_factor=2.5, interval=1, repetitions=1), grade=5)
    assert result.interval == 6
    assert result.repetitions == 2


def test_sm2_perfect_third_time():
    result = sm2(ReviewState(ease_factor=2.5, interval=6, repetitions=2), grade=5)
    assert result.interval == round(6 * 2.5)
    assert result.repetitions == 3


def test_sm2_complete_blackout():
    result = sm2(ReviewState(ease_factor=2.5, interval=10, repetitions=5), grade=0)
    assert result.interval == 1
    assert result.repetitions == 0
    assert result.ease_factor < 2.5


def test_sm2_ease_never_below_minimum():
    result = sm2(ReviewState(ease_factor=MIN_EASE, interval=1, repetitions=0), grade=0)
    assert result.ease_factor >= MIN_EASE
