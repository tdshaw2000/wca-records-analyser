from wca_records_analyser.formatting import (
    decode_multi_blind,
    event_has_average,
    format_average,
    format_consistency,
    format_midpoint,
    format_multi_blind,
    format_multi_blind_full,
    format_single,
    format_time,
    result_unit,
)

THREE_BY_THREE_EVENT_ID = "333"
FEWEST_MOVES_EVENT_ID = "333fm"
MULTI_BLIND_EVENT_ID = "333mbf"


def test_format_time_shows_seconds_and_hundredths_under_a_minute():
    assert format_time(585) == "5.85"


def test_format_time_keeps_two_hundredths_digits():
    assert format_time(1498) == "14.98"


def test_format_time_shows_minutes_when_at_least_a_minute():
    assert format_time(7674) == "1:16.74"


def test_format_time_pads_seconds_and_hundredths_within_a_minute_value():
    assert format_time(6000) == "1:00.00"


def test_format_single_renders_timed_events_as_a_time():
    assert format_single(1498, THREE_BY_THREE_EVENT_ID) == "14.98"


def test_format_single_renders_fewest_moves_as_a_whole_move_count():
    assert format_single(24, FEWEST_MOVES_EVENT_ID) == "24"


def test_format_average_renders_timed_events_as_a_time():
    assert format_average(1888, THREE_BY_THREE_EVENT_ID) == "18.88"


def test_format_average_renders_fewest_moves_as_moves_to_two_decimals():
    assert format_average(2733, FEWEST_MOVES_EVENT_ID) == "27.33"


def test_result_unit_is_time_for_timed_events():
    assert result_unit(THREE_BY_THREE_EVENT_ID) == "time"


def test_result_unit_is_moves_for_fewest_moves():
    assert result_unit(FEWEST_MOVES_EVENT_ID) == "moves"


PERFECT_CONSISTENCY_RATIO = 1.0
SPIKY_CONSISTENCY_RATIO = 1.359158


def test_format_consistency_shows_the_ratio_to_two_decimals_with_a_times_sign():
    assert format_consistency(SPIKY_CONSISTENCY_RATIO) == "1.36×"


def test_format_consistency_of_a_perfectly_consistent_ratio():
    assert format_consistency(PERFECT_CONSISTENCY_RATIO) == "1.00×"


# Multi-Blind results are stored by the WCA API as a single encoded integer:
#   value = (99 - points) * 10_000_000 + time_in_seconds * 100 + missed
# where points = solved - missed. The example below is "8/10 in 34:21 (6 pts)".
MULTI_BLIND_EIGHT_OF_TEN = 930206102
MULTI_BLIND_EIGHT_OF_TEN_SOLVED = 8
MULTI_BLIND_EIGHT_OF_TEN_ATTEMPTED = 10
MULTI_BLIND_EIGHT_OF_TEN_MISSED = 2
MULTI_BLIND_EIGHT_OF_TEN_POINTS = 6
MULTI_BLIND_EIGHT_OF_TEN_TIME_SECONDS = 34 * 60 + 21


def test_decode_multi_blind_recovers_solved_attempted_and_points():
    decoded = decode_multi_blind(MULTI_BLIND_EIGHT_OF_TEN)

    assert decoded.solved == MULTI_BLIND_EIGHT_OF_TEN_SOLVED
    assert decoded.attempted == MULTI_BLIND_EIGHT_OF_TEN_ATTEMPTED
    assert decoded.missed == MULTI_BLIND_EIGHT_OF_TEN_MISSED
    assert decoded.points == MULTI_BLIND_EIGHT_OF_TEN_POINTS
    assert decoded.time_seconds == MULTI_BLIND_EIGHT_OF_TEN_TIME_SECONDS


MULTI_BLIND_PERFECT_THREE = 960030000


def test_decode_multi_blind_handles_a_flawless_attempt_with_no_misses():
    decoded = decode_multi_blind(MULTI_BLIND_PERFECT_THREE)

    assert decoded.solved == 3
    assert decoded.attempted == 3
    assert decoded.missed == 0
    assert decoded.points == 3
    assert decoded.time_seconds == 300


# One cube solved of three attempted: 1 - 2 = -1 points, which scores as a DNF.
MULTI_BLIND_ONE_OF_THREE = 1000060002


def test_decode_multi_blind_reports_non_positive_points_for_a_failed_attempt():
    decoded = decode_multi_blind(MULTI_BLIND_ONE_OF_THREE)

    assert decoded.solved == 1
    assert decoded.attempted == 3
    assert decoded.points == -1


def test_format_multi_blind_shows_solved_over_attempted_and_minutes_seconds():
    assert format_multi_blind(MULTI_BLIND_EIGHT_OF_TEN) == "8/10 34:21"


def test_format_multi_blind_pads_the_seconds_to_two_digits():
    assert format_multi_blind(MULTI_BLIND_PERFECT_THREE) == "3/3 5:00"


def test_format_multi_blind_full_adds_the_word_in_and_the_points():
    assert (
        format_multi_blind_full(MULTI_BLIND_EIGHT_OF_TEN) == "8/10 in 34:21 (6 pts)"
    )


def test_format_single_renders_multi_blind_as_solved_over_attempted():
    assert format_single(MULTI_BLIND_EIGHT_OF_TEN, MULTI_BLIND_EVENT_ID) == "8/10 34:21"


def test_result_unit_is_points_for_multi_blind():
    assert result_unit(MULTI_BLIND_EVENT_ID) == "points"


def test_event_has_average_is_true_for_timed_events():
    assert event_has_average(THREE_BY_THREE_EVENT_ID) is True


def test_event_has_average_is_true_for_fewest_moves():
    assert event_has_average(FEWEST_MOVES_EVENT_ID) is True


def test_event_has_average_is_false_for_multi_blind():
    assert event_has_average(MULTI_BLIND_EVENT_ID) is False


def test_format_midpoint_renders_a_timed_value_as_a_time():
    assert format_midpoint(1755, THREE_BY_THREE_EVENT_ID) == "17.55"


def test_format_midpoint_rounds_a_half_centisecond_to_a_whole_time():
    assert format_midpoint(1693.5, THREE_BY_THREE_EVENT_ID) == "16.94"


def test_format_midpoint_renders_a_fewest_moves_value_to_two_decimals():
    assert format_midpoint(3.5, FEWEST_MOVES_EVENT_ID) == "3.50"
