from wca_records_analyser.records import (
    RecordPoint,
    personal_record_flags,
    single_record_progression,
)
from wca_records_analyser.wca_client import Result

FIRST_SOLVE = 1807
IMPROVED_SOLVE = 1777
SLOWER_SOLVE = 2134
NEW_BEST_SOLVE = 1355
DID_NOT_FINISH = -1
DID_NOT_START = -2

CHRONOLOGICAL_SINGLES = [
    FIRST_SOLVE,
    IMPROVED_SOLVE,
    SLOWER_SOLVE,
    NEW_BEST_SOLVE,
]
EXPECTED_FLAGS = [True, True, False, True]

CHRONOLOGICAL_SINGLES_WITH_NON_RESULTS = [
    DID_NOT_FINISH,
    FIRST_SOLVE,
    DID_NOT_START,
    NEW_BEST_SOLVE,
]
EXPECTED_FLAGS_WITH_NON_RESULTS = [False, True, False, True]


def test_personal_record_flags_marks_each_solve_that_beats_all_previous():
    assert personal_record_flags(CHRONOLOGICAL_SINGLES) == EXPECTED_FLAGS


def test_personal_record_flags_ignores_did_not_finish_and_did_not_start():
    assert (
        personal_record_flags(CHRONOLOGICAL_SINGLES_WITH_NON_RESULTS)
        == EXPECTED_FLAGS_WITH_NON_RESULTS
    )


EARLIEST_COMPETITION_ID = "WestonsuperMareAutumn2023"
MIDDLE_COMPETITION_ID = "BirminghamSummer2024"
LATEST_COMPETITION_ID = "RubiksUKChampionship2024"

EARLIEST_DATE = "2023-11-18"
MIDDLE_DATE = "2024-08-17"
LATEST_DATE = "2024-11-01"

EARLIEST_SINGLE = 1807
MIDDLE_SINGLE = 2134
LATEST_SINGLE = 1498

RESULTS_OUT_OF_DATE_ORDER = [
    Result(single=MIDDLE_SINGLE, competition_id=MIDDLE_COMPETITION_ID),
    Result(single=EARLIEST_SINGLE, competition_id=EARLIEST_COMPETITION_ID),
    Result(single=LATEST_SINGLE, competition_id=LATEST_COMPETITION_ID),
]
COMPETITION_DATES = {
    EARLIEST_COMPETITION_ID: EARLIEST_DATE,
    MIDDLE_COMPETITION_ID: MIDDLE_DATE,
    LATEST_COMPETITION_ID: LATEST_DATE,
}
EXPECTED_PROGRESSION = [
    RecordPoint(date=EARLIEST_DATE, single=EARLIEST_SINGLE),
    RecordPoint(date=LATEST_DATE, single=LATEST_SINGLE),
]


def test_single_record_progression_returns_chronological_records_only():
    progression = single_record_progression(
        RESULTS_OUT_OF_DATE_ORDER, COMPETITION_DATES
    )

    assert progression == EXPECTED_PROGRESSION


SAME_DATE_FASTER_SINGLE = 1777

RESULTS_WITH_TWO_RECORDS_ON_ONE_DATE = [
    Result(single=EARLIEST_SINGLE, competition_id=EARLIEST_COMPETITION_ID),
    Result(single=SAME_DATE_FASTER_SINGLE, competition_id=EARLIEST_COMPETITION_ID),
    Result(single=LATEST_SINGLE, competition_id=LATEST_COMPETITION_ID),
]
COMPETITION_DATES_FOR_ONE_DATE = {
    EARLIEST_COMPETITION_ID: EARLIEST_DATE,
    LATEST_COMPETITION_ID: LATEST_DATE,
}
EXPECTED_PROGRESSION_ONE_PER_DATE = [
    RecordPoint(date=EARLIEST_DATE, single=SAME_DATE_FASTER_SINGLE),
    RecordPoint(date=LATEST_DATE, single=LATEST_SINGLE),
]


def test_single_record_progression_keeps_only_the_best_record_per_date():
    progression = single_record_progression(
        RESULTS_WITH_TWO_RECORDS_ON_ONE_DATE, COMPETITION_DATES_FOR_ONE_DATE
    )

    assert progression == EXPECTED_PROGRESSION_ONE_PER_DATE
