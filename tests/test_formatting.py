from wca_records_analyser.formatting import format_time


def test_format_time_shows_seconds_and_hundredths_under_a_minute():
    assert format_time(585) == "5.85"


def test_format_time_keeps_two_hundredths_digits():
    assert format_time(1498) == "14.98"


def test_format_time_shows_minutes_when_at_least_a_minute():
    assert format_time(7674) == "1:16.74"


def test_format_time_pads_seconds_and_hundredths_within_a_minute_value():
    assert format_time(6000) == "1:00.00"
