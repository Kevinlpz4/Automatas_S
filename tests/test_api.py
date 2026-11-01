"""API adapter tests.

T03 covers the immutable V-code map and the phase-1 Spanish message passthrough.
Later tasks extend this file with endpoint behavior.
"""

from __future__ import annotations

import re
from pathlib import Path
from types import MappingProxyType

import pytest

from automata.api.catalog import ExampleCatalog, ExampleEntry, ExampleNotFoundError
from automata.api.vcodes import V_CODE_MAP, api_codigo, api_error
from automata.models import validacion
from automata.models.validacion import ValidationIssue, validate_structure

PHASE1_CODES = (
    validacion.MISSING_TIPO,
    validacion.INVALID_TIPO,
    validacion.MISSING_FIELD,
    validacion.INVALID_FIELD_TYPE,
    validacion.INVALID_ALPHABET_SYMBOL,
    validacion.DUPLICATE_ELEMENT,
    validacion.EMPTY_STATES,
    validacion.INITIAL_NOT_IN_STATES,
    validacion.FINAL_NOT_IN_STATES,
    validacion.EMPTY_ALPHABET,
    validacion.UNKNOWN_TRANSITION_STATE,
    validacion.UNKNOWN_DESTINATION_STATE,
    validacion.SYMBOL_NOT_IN_ALPHABET,
    validacion.LAMBDA_FORBIDDEN,
    validacion.INVALID_AFD_TARGET,
    validacion.DUPLICATE_TRANSITION,
    validacion.LAMBDA_IN_ALPHABET,
    validacion.INVALID_AFN_TARGET,
)

EXPECTED_VCODES = tuple(f"V{index:02d}" for index in range(1, 19))


def test_vcode_mapping_all() -> None:
    """The map has exactly V01-V18, keyed by real phase-1 issue codes."""
    assert len(V_CODE_MAP) == 18
    assert tuple(V_CODE_MAP) == PHASE1_CODES
    assert tuple(V_CODE_MAP.values()) == EXPECTED_VCODES
    assert set(V_CODE_MAP) == set(PHASE1_CODES)


def test_vcode_unknown_passthrough() -> None:
    """Unknown codes are forwarded unchanged for forward compatibility."""
    assert api_codigo("UNMAPPED_CODE") == "UNMAPPED_CODE"


def test_vcode_invalid_root_symbolic() -> None:
    """INVALID_ROOT stays symbolic and is not one of the 18 V entries."""
    assert validacion.INVALID_ROOT not in V_CODE_MAP
    assert api_codigo(validacion.INVALID_ROOT) == "INVALID_ROOT"


def test_vcode_map_is_immutable() -> None:
    """The map cannot be mutated at runtime."""
    assert isinstance(V_CODE_MAP, MappingProxyType)
    with pytest.raises(TypeError):
        V_CODE_MAP[validacion.MISSING_TIPO] = "V99"  # type: ignore[index]
    with pytest.raises(TypeError):
        del V_CODE_MAP[validacion.MISSING_TIPO]  # type: ignore[attr-defined]


def test_vcode_values_are_codes_not_messages() -> None:
    """The map stores codes only; Spanish text is not duplicated here."""
    assert all(re.fullmatch(r"V\d{2}", value) for value in V_CODE_MAP.values())
    assert all(" " not in value for value in V_CODE_MAP.values())


def test_vcode_uses_phase1_spanish_message() -> None:
    """API errors reuse the exact phase-1 Spanish message, never a copy."""
    issues = validate_structure({})
    missing_tipo = next(
        issue for issue in issues if issue.code == validacion.MISSING_TIPO
    )
    assert missing_tipo.message == "Falta el campo obligatorio 'tipo'."
    assert api_error(missing_tipo) == {
        "codigo": "V01",
        "mensaje": missing_tipo.message,
    }

    sentinel = ValidationIssue(
        code=validacion.SYMBOL_NOT_IN_ALPHABET,
        message="MENSAJE_FASE_1",
        field=None,
        stage=2,
    )
    assert api_error(sentinel) == {
        "codigo": "V13",
        "mensaje": "MENSAJE_FASE_1",
    }


def test_catalog_whitelist_exact() -> None:
    """The default catalog exposes exactly the four bundled examples."""
    entries = ExampleCatalog().list_examples()

    assert len(entries) == 4
    assert tuple(entry.nombre for entry in entries) == (
        "afd_ejemplo.json",
        "afd_incompleto.json",
        "afn_ejemplo.json",
        "afn_lambda_ejemplo.json",
    )
    assert tuple(entry.tipo for entry in entries) == ("AFD", "AFD", "AFN", "AFN-λ")


def test_catalog_order_is_stable() -> None:
    """The listing is alphabetical and stable across calls."""
    catalog = ExampleCatalog()
    first = tuple(entry.nombre for entry in catalog.list_examples())
    second = tuple(entry.nombre for entry in catalog.list_examples())

    assert first == second
    assert first == tuple(sorted(first))


@pytest.mark.parametrize("nombre", ["../secreto.json", "otro.json", "README.md"])
def test_catalog_rejects_non_whitelisted_without_filesystem(
    nombre: str,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A non-whitelisted name fails before any filesystem access."""
    catalog = ExampleCatalog()

    def fail(*args: object, **kwargs: object) -> None:
        raise AssertionError("filesystem touched")

    monkeypatch.setattr(Path, "read_text", fail)
    monkeypatch.setattr(Path, "read_bytes", fail)
    monkeypatch.setattr(Path, "resolve", fail)

    with pytest.raises(ExampleNotFoundError) as excinfo:
        catalog.read(nombre)

    assert excinfo.value.codigo == "EJEMPLO_NO_ENCONTRADO"


def test_catalog_reads_type_from_json_not_filename(tmp_path: Path) -> None:
    """The type comes from the JSON content, not from the file name."""
    path = tmp_path / "afn_ejemplo.json"
    path.write_text(
        '{"tipo":"AFD","estados":["q0"],"alfabeto":["a"],'
        '"inicial":"q0","finales":[],"transiciones":{}}',
        encoding="utf-8",
    )
    catalog = ExampleCatalog(
        directory=tmp_path,
        whitelist=("afn_ejemplo.json",),
    )

    assert catalog.list_examples() == (
        ExampleEntry(nombre="afn_ejemplo.json", tipo="AFD"),
    )


def test_catalog_read_exact_text(tmp_path: Path) -> None:
    """Text is returned byte-for-byte, without newline normalization."""
    raw = '{\r\n  "tipo": "AFD",  \r\n  "estados": []\r\n}\r\n'
    path = tmp_path / "afd_ejemplo.json"
    path.write_bytes(raw.encode("utf-8"))
    catalog = ExampleCatalog(
        directory=tmp_path,
        whitelist=("afd_ejemplo.json",),
    )

    assert catalog.read("afd_ejemplo.json") == raw


def test_catalog_read_real_file_exact() -> None:
    """A bundled example is returned byte-for-byte in UTF-8."""
    repo_root = Path(__file__).resolve().parents[1]
    expected = (repo_root / "ejemplos" / "afd_ejemplo.json").read_bytes().decode(
        "utf-8"
    )

    assert ExampleCatalog().read("afd_ejemplo.json") == expected
