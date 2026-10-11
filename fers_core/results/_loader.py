"""Load solver results without holding the whole result as Python objects.

Results used to be parsed in one go, validated into a full pydantic tree and then
copied into the SDK's own objects, so three complete copies existed at the peak --
about 14x the size of the file. Here every member and node entry is read, validated
in small batches against the generated schema and stored straight into the
compact tables of ``fers_core.results.compact``; the rest of each load case or
combination is small and is validated whole, exactly as before.
"""

from __future__ import annotations

from typing import Any, Callable, Dict, Iterable, Iterator, List, Mapping, Optional, Tuple

from pydantic import TypeAdapter, ValidationError

from fers_core.results._json_stream import JsonStream
from fers_core.results.compact import (
    KeyIndexCache,
    MemberResultTableBuilder,
    NodeDisplacementTableBuilder,
    normalize_selection,
)
from fers_core.results.nodes import ReactionNodeResult
from fers_core.results.plate import PlateResult
from fers_core.results.resultsbundle import ResultsBundle
from fers_core.results.singleresults import SingleResults
from fers_core.types.pydantic_models import Results as ResultsSchema
from fers_core.types.pydantic_models import ResultsBundle as ResultsBundleSchema
from fers_core.types.pydantic_models import ResultSelection as ResultSelectionSchema

_BATCH = 512
_ENTRY_MAPS = ("displacement_nodes", "reaction_nodes", "member_results", "plate_results")
_RESULT_SETS = ("loadcases", "loadcombinations")
# The keys from_dict reads besides the results: once all four are in, the model can be
# built and its source dict dropped before the results are read.
_HEAD_KEYS = frozenset(("schema_version", "settings", "model", "analysis"))
_ADAPTERS: Dict[str, TypeAdapter] = {}


def _adapter(name: str) -> TypeAdapter:
    adapter = _ADAPTERS.get(name)
    if adapter is None:
        adapter = _ADAPTERS[name] = TypeAdapter(ResultsSchema.model_fields[name].annotation)
    return adapter


def _validate(validate: Callable[[Any], Any], value: Any, loc: Tuple[Any, ...]) -> Any:
    """Validate, reporting errors where they sit in the whole bundle, as before."""
    try:
        return validate(value)
    except ValidationError as exc:
        if not loc and exc.title == "ResultsBundle":
            raise
        raise _relocated(exc, loc) from None


def _relocated(exc: ValidationError, loc: Tuple[Any, ...]) -> ValidationError:
    errors = []
    for error in exc.errors(include_url=False):
        moved = {"type": error["type"], "loc": tuple(loc) + tuple(error["loc"]), "input": error["input"]}
        if "ctx" in error:
            moved["ctx"] = error["ctx"]
        errors.append(moved)
    try:
        return ValidationError.from_exception_data("ResultsBundle", errors)
    except Exception:  # an error type from_exception_data cannot rebuild: keep the original
        return exc


class _SingleResultsBuilder:
    """One load case or combination, fed entry by entry."""

    def __init__(self, keys: KeyIndexCache, loc: Tuple[Any, ...]):
        self._keys = keys
        self._loc = loc
        self._members = MemberResultTableBuilder(keys.members)
        self._nodes = NodeDisplacementTableBuilder(keys.nodes)
        self._reactions: Dict[str, ReactionNodeResult] = {}
        self._plates: Dict[str, PlateResult] = {}
        self._shell: Dict[str, Any] = {}

    def entries(self, name: str, batches: Iterable[Dict[str, Any]]) -> None:
        adapter = _adapter(name)
        loc = self._loc + (name,)
        for batch in batches:
            for key, value in _validate(adapter.validate_python, batch, loc).items():
                if name == "member_results":
                    self._members.add(key, value)
                elif name == "displacement_nodes":
                    self._nodes.add(key, value)
                elif name == "reaction_nodes":
                    self._reactions[key] = ReactionNodeResult.from_pydantic(value)
                else:
                    self._plates[key] = PlateResult.from_pydantic(value)
        self._shell[name] = {}

    def field(self, name: str, value: Any) -> None:
        self._shell[name] = value

    def finish(self) -> SingleResults:
        validated = _validate(ResultsSchema.model_validate, self._shell, self._loc)
        return SingleResults._assemble(
            validated, self._members.finish(), self._nodes.finish(), self._reactions, self._plates, self._keys
        )


def _batches(pairs: Iterable[Tuple[str, Any]]) -> Iterator[Dict[str, Any]]:
    batch: Dict[str, Any] = {}
    for key, value in pairs:
        batch[key] = value
        if len(batch) >= _BATCH:
            yield batch
            batch = {}
    if batch:
        yield batch


def _stream_pairs(js: JsonStream) -> Iterator[Tuple[str, Any]]:
    for key in js.iter_object():
        yield key, js.read_value()


# --- from a stream ----------------------------------------------------------


def _single_from_stream(js: JsonStream, keys: KeyIndexCache, loc: Tuple[Any, ...]) -> SingleResults:
    builder = _SingleResultsBuilder(keys, loc)
    for name in js.iter_object():
        if name in _ENTRY_MAPS and js.peek() == "{":
            builder.entries(name, _batches(_stream_pairs(js)))
        else:
            builder.field(name, js.read_value())
    return builder.finish()


def bundle_from_stream(js: JsonStream) -> Optional[ResultsBundle]:
    """The results object at the cursor, or None if it is ``{}``."""
    keys = KeyIndexCache()
    shell: Dict[str, Any] = {}
    groups: Dict[str, Dict[str, SingleResults]] = {}
    selections: Optional[List[Dict[str, Any]]] = None
    empty = True
    for name in js.iter_object():
        empty = False
        if name in _RESULT_SETS and js.peek() == "{":
            group = groups.setdefault(name, {})
            for set_name in js.iter_object():
                if js.peek() == "{":
                    group[set_name] = _single_from_stream(js, keys, (name, set_name))
                else:
                    _validate(ResultsSchema.model_validate, js.read_value(), (name, set_name))
            shell[name] = {}
        elif name == "selections" and js.peek() == "[":
            # One request's selection at a time: the values are most of the file.
            selections = [_selection(js.read_value(), index) for index in js.iter_array()]
        else:
            shell[name] = js.read_value()
    if empty:
        return None
    return _assemble_bundle(shell, groups, selections)


def _selection(raw: Any, index: int) -> Dict[str, Any]:
    return normalize_selection(_validate(ResultSelectionSchema.model_validate, raw, ("selections", index)))


def _assemble_bundle(
    shell: Dict[str, Any],
    groups: Dict[str, Dict[str, SingleResults]],
    selections: Optional[List[Dict[str, Any]]] = None,
) -> ResultsBundle:
    bundle = ResultsBundle._from_shell(_validate(ResultsBundleSchema.model_validate, shell, ()))
    bundle.loadcases = groups.get("loadcases", {})
    bundle.loadcombinations = groups.get("loadcombinations", {})
    if selections is not None:
        bundle.apply_selections(selections)
    return bundle


def results_from_engine_output(text: str) -> ResultsBundle:
    """The results of a solve, from the document ``calculate_from_json`` returns.

    The model echoed in front of them is decoded and dropped; ``run_analysis``
    keeps the model it already has.
    """
    js = JsonStream(text)
    bundle: Optional[ResultsBundle] = None
    for key in js.iter_object():
        if key == "results" and js.peek() not in ("n", ""):
            if js.peek() == "{":
                bundle = bundle_from_stream(js) or _assemble_bundle({}, {})
            else:
                bundle = _assemble_bundle(js.read_value(), {})
        else:
            js.skip_value()
    js.expect_end()
    if bundle is None:
        raise ValueError("No 'results' field found in the calculation output")
    return bundle


def read_document(
    js: JsonStream, build_model: Callable[[Dict[str, Any]], Any]
) -> Tuple[Any, Optional[ResultsBundle]]:
    """A whole FERS document: the model built by ``build_model`` and its results, if any.

    As ``from_dict``: ``results`` wins over the legacy ``resultsbundle`` key unless it
    is empty, and an empty results object means no results.
    """
    head: Dict[str, Any] = {}
    model: Any = None
    bundles: Dict[str, Optional[ResultsBundle]] = {}
    for key in js.iter_object():
        if key in ("results", "resultsbundle"):
            if model is None and _HEAD_KEYS <= head.keys():
                model, head = build_model(head), {}
            bundles[key] = bundle_from_stream(js) if js.peek() == "{" else _null_or_invalid(js)
        elif model is not None:
            if key in _HEAD_KEYS:
                raise ValueError(f"'{key}' appears twice in the document")
            js.skip_value()
        else:
            head[key] = js.read_value()
    js.expect_end()
    if model is None:
        model = build_model(head)
    return model, bundles.get("results") or bundles.get("resultsbundle")


def _null_or_invalid(js: JsonStream) -> None:
    value = js.read_value()
    if value:
        # Neither an object nor empty: let the schema say what is wrong, as before.
        _validate(ResultsBundleSchema.model_validate, value, ())
    return None


# --- from a mapping ---------------------------------------------------------


def bundle_from_mapping(raw: Mapping[str, Any]) -> ResultsBundle:
    """Results already parsed into dicts, validated and stored as from a stream."""
    keys = KeyIndexCache()
    shell: Dict[str, Any] = {}
    groups: Dict[str, Dict[str, SingleResults]] = {}
    selections: Optional[List[Dict[str, Any]]] = None
    for name, value in raw.items():
        if name in _RESULT_SETS and isinstance(value, Mapping):
            group = groups[name] = {}
            for set_name, single in value.items():
                if isinstance(single, Mapping):
                    group[str(set_name)] = _single_from_mapping(single, keys, (name, set_name))
                else:
                    _validate(ResultsSchema.model_validate, single, (name, set_name))
            shell[name] = {}
        elif name == "selections" and isinstance(value, list):
            selections = [_selection(item, index) for index, item in enumerate(value)]
        else:
            shell[name] = value
    return _assemble_bundle(shell, groups, selections)


def _single_from_mapping(raw: Mapping[str, Any], keys: KeyIndexCache, loc: Tuple[Any, ...]) -> SingleResults:
    builder = _SingleResultsBuilder(keys, loc)
    for name, value in raw.items():
        if name in _ENTRY_MAPS and isinstance(value, Mapping):
            builder.entries(name, _batches(value.items()))
        else:
            builder.field(name, value)
    return builder.finish()
