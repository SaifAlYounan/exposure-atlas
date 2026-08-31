"""Canonical JSON Schema 2020-12 validation with a cross-file registry."""
import json
import pathlib

from jsonschema import Draft202012Validator
from referencing import Registry, Resource

ROOT = pathlib.Path(__file__).resolve().parents[3]
DOMAIN = ROOT / "schemas" / "domain"
BASE = "https://exposure-atlas.invalid/schemas/domain/"


class AtlasSchemaError(ValueError):
    pass


def _registry() -> Registry:
    resources = []
    for f in DOMAIN.glob("*.json"):
        doc = json.loads(f.read_text())
        resources.append((doc["$id"], Resource.from_contents(doc)))
    return Registry().with_resources(resources)


_REG = _registry()
_VALIDATORS: dict[str, Draft202012Validator] = {}


def validator(name: str) -> Draft202012Validator:
    if name not in _VALIDATORS:
        doc = json.loads((DOMAIN / name).read_text())
        _VALIDATORS[name] = Draft202012Validator(doc, registry=_REG)
    return _VALIDATORS[name]


def validate(name: str, instance) -> None:
    errs = sorted(validator(name).iter_errors(instance), key=str)
    if errs:
        raise AtlasSchemaError(
            f"{name}: {errs[0].message} at /" + "/".join(str(p) for p in errs[0].absolute_path))
