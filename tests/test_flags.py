"""flags maps WCA's own country names (persons.country_id) to flag-icons CSS classes."""

from wca_records_analyser.flags import flag_class


def test_flag_class_for_a_plain_country_name():
    assert flag_class("Australia") == "fi fi-au"


def test_flag_class_for_a_country_whose_wca_id_is_not_its_full_name():
    # The export stores "USA", not "United States" (CLAUDE.md's own example of the wrinkle).
    assert flag_class("USA") == "fi fi-us"


def test_flag_class_for_a_country_whose_wca_id_names_a_different_flag():
    # Taiwanese competitors compete as Chinese Taipei and fly that flag, not Taiwan's.
    assert flag_class("Taiwan") == "fi fi-tw"


def test_flag_class_for_an_unknown_country_id_is_none():
    assert flag_class("Nowhereland") is None
