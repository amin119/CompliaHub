import re

from app.services.iso27001.catalog import CATALOG, CATALOG_BY_ID

_CONTROL_ID_RE = re.compile(r"^A\.\d{1,2}\.\d{1,2}$")


def test_catalog_has_48_entries():
    assert len(CATALOG) == 48


def test_no_duplicate_control_ids():
    ids = [control.control_id for control in CATALOG]
    assert len(ids) == len(set(ids))
    assert len(CATALOG_BY_ID) == len(CATALOG)


def test_every_control_id_matches_annex_a_shape():
    for control in CATALOG:
        assert _CONTROL_ID_RE.match(control.control_id), control.control_id


def test_every_entry_has_a_source_note():
    for control in CATALOG:
        assert control.source_note
        assert "not sourced from the licensed standard" in control.source_note.lower()


def test_theme_is_one_of_the_four_valid_values():
    valid_themes = {"Organizational", "People", "Physical", "Technological"}
    for control in CATALOG:
        assert control.theme in valid_themes


def test_no_people_or_physical_controls_catalogued_this_phase():
    themes = {control.theme for control in CATALOG}
    assert "People" not in themes
    assert "Physical" not in themes


def test_automatable_false_never_paired_with_technical_assessment_type():
    for control in CATALOG:
        if not control.automatable:
            assert control.assessment_type != "technical", control.control_id


def test_all_34_technological_a8_controls_present():
    a8_ids = {control.control_id for control in CATALOG if control.control_id.startswith("A.8.")}
    expected = {f"A.8.{n}" for n in range(1, 35)}
    assert a8_ids == expected


def test_14_organizational_a5_controls_present():
    a5_controls = [control for control in CATALOG if control.theme == "Organizational"]
    assert len(a5_controls) == 14
    assert all(control.control_id.startswith("A.5.") for control in a5_controls)


def test_six_technological_controls_marked_not_automatable():
    non_automatable_a8 = {
        control.control_id
        for control in CATALOG
        if control.control_id.startswith("A.8.") and not control.automatable
    }
    assert non_automatable_a8 == {
        "A.8.1",
        "A.8.6",
        "A.8.14",
        "A.8.17",
        "A.8.19",
        "A.8.30",
    }
