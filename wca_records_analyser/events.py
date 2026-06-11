"""Display names for the World Cube Association events."""

from dataclasses import dataclass

EVENT_NAMES = {
    "222": "2x2x2 Cube",
    "333": "3x3x3 Cube",
    "444": "4x4x4 Cube",
    "555": "5x5x5 Cube",
    "666": "6x6x6 Cube",
    "777": "7x7x7 Cube",
    "333bf": "3x3x3 Blindfolded",
    "333fm": "3x3x3 Fewest Moves",
    "333oh": "3x3x3 One-Handed",
    "clock": "Clock",
    "minx": "Megaminx",
    "pyram": "Pyraminx",
    "skewb": "Skewb",
    "sq1": "Square-1",
    "444bf": "4x4x4 Blindfolded",
    "555bf": "5x5x5 Blindfolded",
    "333mbf": "3x3x3 Multi-Blind",
    "333ft": "3x3x3 With Feet",
    "magic": "Magic",
    "mmagic": "Master Magic",
    "333mbo": "3x3x3 Multi-Blind Old Style",
}


@dataclass(frozen=True)
class Event:
    """A WCA event identified by its id and shown by its display name."""

    event_id: str
    name: str


def named_events(event_ids):
    """Return the named events for the given ids, sorted alphabetically by name."""
    events = [
        Event(event_id=event_id, name=EVENT_NAMES[event_id])
        for event_id in event_ids
    ]
    return sorted(events, key=lambda event: event.name)
