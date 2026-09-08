from __future__ import annotations

import datetime as dt

from kaianolevine_api.retrieval.wcs.flatten import FLATTENER_VERSION, flatten_note


def test_flattener_version_is_set() -> None:
    assert isinstance(FLATTENER_VERSION, int)
    assert FLATTENER_VERSION >= 1


def test_minimal_note() -> None:
    out = flatten_note(
        title="Frame and axis",
        instructors=["Kaiano"],
        students=["Sarah"],
        organization="",
        session_date=dt.date(2024, 1, 15),
        notes_json={"summary": "Worked on frame and axis."},
    )
    assert out == (
        "Frame and axis\n\nKaiano | Sarah |  | 2024-01-15\n\nWorked on frame and axis."
    )


def test_omits_empty_sections_but_keeps_header() -> None:
    out = flatten_note(
        title="X",
        instructors=[],
        students=[],
        organization="",
        session_date=None,
        notes_json={
            "summary": "S",
            "key_concepts": [],
            "drills": [],
        },
    )
    assert out == "X\n\n |  |  | \n\nS"


def test_organization_in_header_for_class_taught() -> None:
    out = flatten_note(
        title="Class taught at Studio",
        instructors=["Kaiano"],
        students=[],
        organization="Atomic Ballroom",
        session_date=dt.date(2024, 5, 1),
        notes_json={"summary": "Taught beginner class."},
    )
    assert out == (
        "Class taught at Studio\n\n"
        "Kaiano |  | Atomic Ballroom | 2024-05-01\n\n"
        "Taught beginner class."
    )


def test_full_render_snapshot() -> None:
    out = flatten_note(
        title="Anchor step deep dive",
        instructors=["Kyle"],
        students=["Kaiano"],
        organization="",
        session_date=dt.date(2024, 3, 8),
        notes_json={
            "summary": "Worked on anchor step timing.",
            "key_concepts": [
                "frame",
                {"concept": "anchor step", "detail": "lands on counts 5-and-6"},
            ],
            "vocabulary_terms": [
                {"term": "anchor", "definition": "settling step on count 6"},
            ],
            "drills": [
                {
                    "name": "Anchor isolation",
                    "goal": "stable weight transfer",
                    "steps": ["walk in place", "shift weight on 6", "feel the settle"],
                },
            ],
            "common_mistakes": [
                {"mistake": "early commit", "correction": "wait until 6"},
            ],
            "patterns_and_sequences": [
                {"name": "basic pattern", "description": "rock step into anchor"},
            ],
            "student_observations": [
                "rushes the anchor",
                {"observation": "looks down at her feet"},
            ],
            "action_items": [
                {"action": "drill anchor at home", "rationale": "build muscle memory"},
            ],
            "competition_notes": [
                {"note": "prelim went well", "context": "Open J&J"},
            ],
            "quotes": [
                {
                    "quote": "wait for it",
                    "speaker": "Kyle",
                    "context": "during anchor drill",
                },
            ],
            "references": [
                {
                    "name": "Robert Royston anchor video",
                    "type": "video",
                    "context": "see 4:30 mark",
                },
            ],
            "off_topic_notes": ["this should not appear"],
            "suggested_new_sections": ["this also should not"],
        },
    )

    expected = (
        "Anchor step deep dive\n\n"
        "Kyle | Kaiano |  | 2024-03-08\n\n"
        "Worked on anchor step timing.\n\n"
        "Key concepts:\n"
        "- frame\n"
        "- anchor step — lands on counts 5-and-6\n\n"
        "Vocabulary:\n"
        "- anchor: settling step on count 6\n\n"
        "Drills:\n"
        "- Anchor isolation — stable weight transfer\n"
        "  Steps: walk in place; shift weight on 6; feel the settle\n\n"
        "Common mistakes:\n"
        "- early commit → wait until 6\n\n"
        "Patterns and sequences:\n"
        "- basic pattern: rock step into anchor\n\n"
        "Student observations:\n"
        "- rushes the anchor\n"
        "- looks down at her feet\n\n"
        "Action items:\n"
        "- drill anchor at home: build muscle memory\n\n"
        "Competition notes:\n"
        "- prelim went well (Open J&J)\n\n"
        "Quotes:\n"
        '- "wait for it" — Kyle (during anchor drill)\n\n'
        "References:\n"
        "- Robert Royston anchor video (video): see 4:30 mark"
    )
    assert out == expected


def test_skips_malformed_items() -> None:
    out = flatten_note(
        title="t",
        instructors=[],
        students=[],
        organization="",
        session_date=None,
        notes_json={
            "vocabulary_terms": [
                {"term": "good", "definition": "ok"},
                {"definition": "missing term"},
                {"term": ""},
                {},
            ],
        },
    )
    assert out == "t\n\n |  |  | \n\nVocabulary:\n- good: ok"


def test_drops_section_when_all_items_malformed() -> None:
    out = flatten_note(
        title="t",
        instructors=[],
        students=[],
        organization="",
        session_date=None,
        notes_json={
            "drills": [{"goal": "no name"}, {}],
        },
    )
    assert out == "t\n\n |  |  | "


def test_handles_none_inputs() -> None:
    out = flatten_note(
        title=None,
        instructors=None,
        students=None,
        organization=None,
        session_date=None,
        notes_json=None,
    )
    assert out == " |  |  | "


def test_excluded_sections_never_render() -> None:
    out = flatten_note(
        title="t",
        instructors=[],
        students=[],
        organization="",
        session_date=None,
        notes_json={
            "off_topic_notes": ["lunch plans"],
            "suggested_new_sections": ["new section idea"],
        },
    )
    assert out == "t\n\n |  |  | "


def test_quote_with_only_speaker() -> None:
    out = flatten_note(
        title="t",
        instructors=[],
        students=[],
        organization="",
        session_date=None,
        notes_json={
            "quotes": [{"quote": "do it again", "speaker": "Kyle"}],
        },
    )
    assert out == 't\n\n |  |  | \n\nQuotes:\n- "do it again" — Kyle'


def test_deterministic_output() -> None:
    payload = dict(
        title="x",
        instructors=["a", "b"],
        students=["c"],
        organization="",
        session_date=dt.date(2024, 1, 1),
        notes_json={"summary": "abc", "key_concepts": ["k1", "k2"]},
    )
    assert flatten_note(**payload) == flatten_note(**payload)
