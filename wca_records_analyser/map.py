"""Shaping of personal-record data into city-grouped series for the map view."""

from wca_records_analyser.formatting import (
    MULTI_BLIND_EVENT_ID,
    format_average,
    format_multi_blind_full,
    format_single,
)
from wca_records_analyser.records import personal_record_flags

CITY_KEY = "city"
LATITUDE_KEY = "lat"
LONGITUDE_KEY = "lng"
PRS_KEY = "prs"
DATE_KEY = "date"
DISPLAY_KEY = "display"


def to_map_series(results, competitions, event_id, is_average):
    """Return city-grouped PR locations for singles or averages.

    Each group carries the city name, the mean lat/lng of all competitions in
    that city where a PR was set, and a list of (date, formatted display) pairs
    for every PR set there.
    """
    metric = (lambda r: r.average) if is_average else (lambda r: r.single)
    formatter = _choose_formatter(event_id, is_average)

    dated_results = sorted(
        results,
        key=lambda result: competitions[result.competition_id].start_date,
    )
    values = [metric(result) for result in dated_results]
    flags = personal_record_flags(values)

    city_groups = {}
    for result, is_pr in zip(dated_results, flags):
        if not is_pr:
            continue
        competition = competitions[result.competition_id]
        city = competition.city
        if city not in city_groups:
            city_groups[city] = {"latitudes": [], "longitudes": [], PRS_KEY: []}
        city_groups[city]["latitudes"].append(competition.latitude)
        city_groups[city]["longitudes"].append(competition.longitude)
        city_groups[city][PRS_KEY].append(
            {
                DATE_KEY: competition.start_date,
                DISPLAY_KEY: formatter(metric(result), event_id),
            }
        )

    return [
        {
            CITY_KEY: city,
            LATITUDE_KEY: sum(data["latitudes"]) / len(data["latitudes"]),
            LONGITUDE_KEY: sum(data["longitudes"]) / len(data["longitudes"]),
            PRS_KEY: data[PRS_KEY],
        }
        for city, data in city_groups.items()
    ]


def _choose_formatter(event_id, is_average):
    if event_id == MULTI_BLIND_EVENT_ID and not is_average:
        return lambda value, _event_id: format_multi_blind_full(value)
    return format_average if is_average else format_single
