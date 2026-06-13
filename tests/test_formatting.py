from wca_records_analyser.formatting import (
    format_average,
    format_consistency,
    format_single,
    format_time,
    result_unit,
)

THREE_BY_THREE_EVENT_ID = "333"
FEWEST_MOVES_EVENT_ID = "333fm"


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
