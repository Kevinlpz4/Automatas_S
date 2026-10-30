"""Service tests for the JSON automaton loader (T11)."""

from __future__ import annotations

import pytest

from automata.models.errores import (
    AutomatonFileNotFoundError,
    AutomatonFileReadError,
    InvalidAutomatonDefinition,
    MalformedJsonError,
)
from automata.models.tipos import AFD, AFN, NFALambda
from conftest import EJEMPLOS, write_json, write_text


# --- T11: valid documents --------------------------------------------------


def test_load_valid_afd(loader):
    """R4/R6: the main AFD loads verbatim into a frozen AFD model."""
    afd = loader.load(EJEMPLOS / "afd_ejemplo.json")

    assert isinstance(afd, AFD)
    assert afd.estados == ("q0", "q1", "q2", "q3", "q4", "q5")
    assert len(afd.estados) == 6
    assert afd.alfabeto == ("a", "b", "c")
    assert len(afd.alfabeto) == 3
    assert len(afd.transiciones) == 6
    assert sum(len(simbolos) for simbolos in afd.transiciones.values()) == 18
    assert afd.inicial == "q0"
    assert afd.finales == frozenset({"q1", "q4"})

    with pytest.raises(TypeError):
        afd.transiciones["q0"]["a"] = "q0"  # type: ignore[index]


def test_load_afn_format(loader):
    """R4: AFN destination lists become tuples and ``[]`` means no transition."""
    afn = loader.load(EJEMPLOS / "afn_ejemplo.json")

    assert isinstance(afn, AFN)
    assert afn.transiciones["q0"]["a"] == ("q0", "q1")
    assert isinstance(afn.transiciones["q0"]["a"], tuple)
    assert afn.transiciones["q1"]["b"] == ("q2",)
    assert afn.transiciones["q2"]["b"] == ()
    assert isinstance(afn.transiciones["q2"]["b"], tuple)


def test_load_afn_lambda_format(loader):
    """R4: AFN-λ keeps λ as a transition key and out of the alphabet."""
    nfa_lambda = loader.load(EJEMPLOS / "afn_lambda_ejemplo.json")

    assert isinstance(nfa_lambda, NFALambda)
    assert nfa_lambda.transiciones["q0"]["λ"] == ("q2",)
    assert nfa_lambda.transiciones["q1"]["λ"] == ("q1",)
    assert "λ" not in nfa_lambda.alfabeto


# --- T11: file-level errors ------------------------------------------------


def test_loader_file_not_found(loader):
    """R18: a missing path becomes AutomatonFileNotFoundError."""
    path = EJEMPLOS / "no_existe.json"

    with pytest.raises(AutomatonFileNotFoundError) as excinfo:
        loader.load(path)

    assert excinfo.value.path == path
    assert excinfo.value.code == "AUTOMATON_FILE_NOT_FOUND"
    assert isinstance(excinfo.value, AutomatonFileNotFoundError)


def test_loader_malformed_json(loader, tmp_path):
    """R18: invalid JSON becomes MalformedJsonError, never a native exception."""
    path = write_text(tmp_path, "roto.json", '{"tipo": "AFD",')

    with pytest.raises(MalformedJsonError) as excinfo:
        loader.load(path)

    assert excinfo.value.path == path
    assert excinfo.value.code == "MALFORMED_JSON"


def test_loader_read_error(loader, tmp_path):
    """A directory path cannot be read as text and becomes AutomatonFileReadError."""
    directory = tmp_path / "carpeta"
    directory.mkdir()

    with pytest.raises(AutomatonFileReadError) as excinfo:
        loader.load(directory)

    assert excinfo.value.path == directory
    assert excinfo.value.code == "AUTOMATON_FILE_READ_ERROR"


# --- T11: validation wrapping ---------------------------------------------


def test_loader_wraps_validation_error(loader, tmp_path):
    """R5/R21: validation failures are domain errors, never KeyError/ValueError."""
    payload = {
        "estados": ["q0", "q1"],
        "alfabeto": ["a"],
        "finales": ["q1"],
        "transiciones": {"q0": {"a": "q1"}, "q1": {"a": "q1"}},
    }
    path = write_json(tmp_path, "invalido.json", payload)

    with pytest.raises(InvalidAutomatonDefinition) as excinfo:
        loader.load(path)

    error = excinfo.value
    assert isinstance(error, InvalidAutomatonDefinition)
    assert not isinstance(error, (KeyError, ValueError))
    assert error.code == "INVALID_AUTOMATON_DEFINITION"
    assert isinstance(error.errors, tuple)
    assert [issue.code for issue in error.errors] == [
        "MISSING_TIPO",
        "MISSING_FIELD",
    ]
    assert [issue.field for issue in error.errors] == ["tipo", "inicial"]
    assert all(issue.stage == 1 for issue in error.errors)


def test_loader_wraps_semantic_validation_error(loader, tmp_path):
    """R5/R21: a stage-2 defect also becomes InvalidAutomatonDefinition."""
    payload = {
        "tipo": "AFD",
        "estados": ["q0", "q1"],
        "alfabeto": ["a"],
        "inicial": "q0",
        "finales": ["q1"],
        "transiciones": {"q0": {"a": "q9"}, "q1": {"a": "q1"}},
    }
    path = write_json(tmp_path, "semantico_invalido.json", payload)

    with pytest.raises(InvalidAutomatonDefinition) as excinfo:
        loader.load(path)

    errors = excinfo.value.errors
    assert [issue.code for issue in errors] == ["UNKNOWN_DESTINATION_STATE"]
    assert errors[0].field == "transiciones['q0']['a']"
    assert errors[0].stage == 2
    assert not any(issue.stage == 1 for issue in errors)


def test_validation_stops_after_stage1(loader, tmp_path):
    """R5: a stage-1 defect suppresses every stage-2 issue."""
    payload = {
        "tipo": "AFD",
        "estados": ["q0", 5],
        "alfabeto": ["a"],
        "inicial": "q9",
        "finales": ["zz"],
        "transiciones": {},
    }
    path = write_json(tmp_path, "dos_etapas.json", payload)

    with pytest.raises(InvalidAutomatonDefinition) as excinfo:
        loader.load(path)

    errors = excinfo.value.errors
    assert [issue.code for issue in errors] == ["INVALID_FIELD_TYPE"]
    assert errors[0].field == "estados[1]"
    assert all(issue.stage == 1 for issue in errors)
    assert not any(
        issue.code in {"INITIAL_NOT_IN_STATES", "FINAL_NOT_IN_STATES"}
        for issue in errors
    )


# --- T11: bundled examples -------------------------------------------------


@pytest.mark.parametrize(
    ("name", "expected"),
    [
        ("afd_ejemplo.json", AFD),
        ("afd_incompleto.json", AFD),
        ("afn_ejemplo.json", AFN),
        ("afn_lambda_ejemplo.json", NFALambda),
    ],
)
def test_examples_load_all(loader, name, expected):
    """R20: every bundled example loads through the real loader."""
    automaton = loader.load(EJEMPLOS / name)

    assert isinstance(automaton, expected)
