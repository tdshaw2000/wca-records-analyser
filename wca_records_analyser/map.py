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
TOTAL_KEY = "total"
EVENTS_KEY = "events"
NAME_KEY = "name"
SINGLES_KEY = "singles"
AVERAGES_KEY = "averages"


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


def to_overview_map_series(results_by_event, competitions, event_names):
    """Return city-grouped PR summary across all events for the overview map.

    Each group carries the city name, mean lat/lng of unique contributing
    competitions, a total PR count (singles + averages), and a per-event
    breakdown of singles and averages counts.
    """
    city_groups = {}

    for event_id, results in results_by_event.items():
        event_name = event_names.get(event_id, event_id)
        _accumulate_event_into_city_groups(results, competitions, event_id, event_name, city_groups)

    return [
        {
            CITY_KEY: city,
            LATITUDE_KEY: sum(data["latitudes"]) / len(data["latitudes"]),
            LONGITUDE_KEY: sum(data["longitudes"]) / len(data["longitudes"]),
            TOTAL_KEY: data[TOTAL_KEY],
            EVENTS_KEY: [
                {NAME_KEY: name, SINGLES_KEY: counts[SINGLES_KEY], AVERAGES_KEY: counts[AVERAGES_KEY]}
                for name, counts in data[EVENTS_KEY].items()
            ],
        }
        for city, data in city_groups.items()
    ]


def _accumulate_event_into_city_groups(results, competitions, event_id, event_name, city_groups):
    dated_results = sorted(results, key=lambda r: competitions[r.competition_id].start_date)
    singles_flags = personal_record_flags([r.single for r in dated_results])
    averages_flags = personal_record_flags([r.average for r in dated_results])

    for result, is_single_pr, is_average_pr in zip(dated_results, singles_flags, averages_flags):
        if not is_single_pr and not is_average_pr:
            continue
        competition = competitions[result.competition_id]
        city = competition.city
        if city not in city_groups:
            city_groups[city] = {"latitudes": [], "longitudes": [], TOTAL_KEY: 0, EVENTS_KEY: {}, "comp_ids": set()}
        group = city_groups[city]
        if competition.id not in group["comp_ids"]:
            group["latitudes"].append(competition.latitude)
            group["longitudes"].append(competition.longitude)
            group["comp_ids"].add(competition.id)
        if event_name not in group[EVENTS_KEY]:
            group[EVENTS_KEY][event_name] = {SINGLES_KEY: 0, AVERAGES_KEY: 0}
        if is_single_pr:
            group[EVENTS_KEY][event_name][SINGLES_KEY] += 1
            group[TOTAL_KEY] += 1
        if is_average_pr:
            group[EVENTS_KEY][event_name][AVERAGES_KEY] += 1
            group[TOTAL_KEY] += 1


def _choose_formatter(event_id, is_average):
    if event_id == MULTI_BLIND_EVENT_ID and not is_average:
        return lambda value, _event_id: format_multi_blind_full(value)
    return format_average if is_average else format_single
