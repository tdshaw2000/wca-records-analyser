"""wca_client reads the wca_data database, keeping the shapes the web app was built on."""

from datetime import UTC, date, datetime

import pytest

from wca_data.build import build_database
from wca_data.read import DatabaseUnavailable, WcaData
from wca_records_analyser.wca_client import (
    Competition,
    Person,
    PersonNotFound,
    Profile,
    Result,
    get_competition_dates,
    get_competitions,
    get_export_date,
    get_profile,
    get_results,
    search_persons,
)

from tests.wca_data.export_zip import write_fixture_zip

FELIKS = Person(
    name="Feliks Zemdegs",
    wca_id="2009ZEMD01",
    profile_url="https://www.worldcubeassociation.org/persons/2009ZEMD01",
)


@pytest.fixture(scope="module")
def db_path(tmp_path_factory):
    folder = tmp_path_factory.mktemp("wca")
    path = folder / "wca.sqlite"
    build_database(
        write_fixture_zip(folder / "export.zip"), path, datetime(2026, 9, 24, tzinfo=UTC)
    )
    return path


@pytest.fixture
def data(db_path):
    with WcaData.open(db_path) as opened:
        yield opened


def test_search_persons_returns_name_wca_id_and_wca_profile_url(data):
    assert search_persons("feliks", data=data) == [FELIKS]


def test_search_persons_returns_an_empty_list_when_nobody_matches(data):
    assert search_persons("nobody", data=data) == []


def test_without_a_database_given_it_opens_the_one_wca_data_db_path_names(db_path, monkeypatch):
    monkeypatch.setenv("WCA_DATA_DB_PATH", str(db_path))
    assert search_persons("feliks") == [FELIKS]


def test_without_a_database_configured_it_says_so(monkeypatch):
    monkeypatch.delenv("WCA_DATA_DB_PATH", raising=False)
    with pytest.raises(DatabaseUnavailable):
        search_persons("feliks")


def test_get_results_returns_single_average_competition_and_solves_in_date_order(data):
    assert get_results("2009ZEMD01", "333", data=data) == [
        Result(single=1052, competition_id="MelbourneWinterOpen2009", average=1157,
               solves=(1052, 1203, 1122, 1146, 1301)),
        Result(single=993, competition_id="MelbourneWinterOpen2009", average=1120,
               solves=(1044, 993, 1120, 1136, 1101)),
        Result(single=593, competition_id="AustralianNationals2026", average=648,
               solves=(623, 593, 705, 693, 629)),
    ]


def test_get_results_keeps_dnf_and_dns_as_the_wca_defines_them(data):
    assert get_results("2009ZEMD01", "333bf", data=data) == [
        Result(single=-1, competition_id="AustralianNationals2026", average=-1,
               solves=(-1, -1, -2)),
    ]


def test_get_competitions_returns_each_competition_with_its_location(data):
    assert get_competitions("2009ZEMD01", data=data) == {
        "MelbourneWinterOpen2009": Competition(
            id="MelbourneWinterOpen2009", start_date="2009-07-18",
            latitude=-37.8136, longitude=144.9631, city="Melbourne",
        ),
        "AustralianNationals2026": Competition(
            id="AustralianNationals2026", start_date="2026-07-09",
            latitude=-37.8136, longitude=144.9631, city="Melbourne, Victoria",
        ),
    }


def test_a_competition_without_coordinates_has_none(data):
    [shanghai] = get_competitions("2010WANG01", data=data).values()
    assert (shanghai.latitude, shanghai.longitude) == (None, None)


def test_get_competition_dates_maps_each_competition_to_its_start_date(data):
    assert get_competition_dates("2009ZEMD01", data=data) == {
        "MelbourneWinterOpen2009": "2009-07-18",
        "AustralianNationals2026": "2026-07-09",
    }


def test_get_profile_returns_the_person_and_the_events_they_have_a_result_in(data):
    # Feliks' only 3x3 Blindfolded result is a DNF, so, as on WCA, it holds no record.
    assert get_profile("2009ZEMD01", data=data) == Profile(person=FELIKS, event_ids=["333"])


def test_get_profile_of_an_unknown_wca_id_raises_person_not_found(data):
    with pytest.raises(PersonNotFound, match="1999NONE01"):
        get_profile("1999NONE01", data=data)


def test_get_export_date_is_the_day_of_the_export_the_database_was_built_from(data):
    assert get_export_date(data=data) == date(2026, 9, 23)
