from wca_records_analyser.records import personal_record_flags

FIRST_SOLVE = 1807
IMPROVED_SOLVE = 1777
SLOWER_SOLVE = 2134
NEW_BEST_SOLVE = 1355

CHRONOLOGICAL_SINGLES = [
    FIRST_SOLVE,
    IMPROVED_SOLVE,
    SLOWER_SOLVE,
    NEW_BEST_SOLVE,
]
EXPECTED_FLAGS = [True, True, False, True]


def test_personal_record_flags_marks_each_solve_that_beats_all_previous():
    assert personal_record_flags(CHRONOLOGICAL_SINGLES) == EXPECTED_FLAGS
