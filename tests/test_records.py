from wca_records_analyser.records import personal_record_flags

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
