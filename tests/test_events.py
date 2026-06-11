from wca_records_analyser.events import Event, named_events

COMPETED_EVENT_IDS = ["pyram", "333", "222"]
EXPECTED_NAMED_EVENTS = [
    Event(event_id="222", name="2x2x2 Cube"),
    Event(event_id="333", name="3x3x3 Cube"),
    Event(event_id="pyram", name="Pyraminx"),
]


def test_named_events_returns_named_events_sorted_alphabetically():
    assert named_events(COMPETED_EVENT_IDS) == EXPECTED_NAMED_EVENTS
