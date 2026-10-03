# SpecGraph classification review packet

Review source before opening proposed labels. This packet omits proposed labels, selection roles, refactoring phases, and prior diagnoses. All source is Apache-2.0; see LICENSE.SpecGraph.

## sg-001

[Pinned source](https://github.com/0al-spec/SpecGraph/blob/b7643721b11b5d4768bc966abab7dddd1092a5bd/tools/idea_maturity_metrics_report.py#L1444-L1460)

```python
def _candidate_approval_state(artifacts: dict[str, dict[str, Any]]) -> str:
    readiness_impact = _dict(
        _dict(artifacts.get("repaired_repair_session")).get("readiness_impact")
    )
    repaired_session_summary = _summary(artifacts, "repaired_repair_session")
    handoff_summary = _summary(artifacts, "repaired_handoff")
    if (
        readiness_impact.get("ready_for_candidate_approval") is True
        or repaired_session_summary.get("ready_for_candidate_approval") is True
        or handoff_summary.get("ready_for_candidate_approval") is True
    ):
        return "ready"
    if artifacts.get("repaired_repair_session") or artifacts.get("repaired_handoff"):
        return "blocked"
    if artifacts.get("candidate_graph"):
        return "not_reached"
    return "not_available"
```

Supporting declaration: `tools/idea_maturity_metrics_report.py::import@3`

```python
from __future__ import annotations
```

Supporting declaration: `tools/idea_maturity_metrics_report.py::import@5`

```python
import argparse
```

Supporting declaration: `tools/idea_maturity_metrics_report.py::import@6`

```python
import json
```

Supporting declaration: `tools/idea_maturity_metrics_report.py::import@7`

```python
import re
```

Supporting declaration: `tools/idea_maturity_metrics_report.py::import@8`

```python
import sys
```

Supporting declaration: `tools/idea_maturity_metrics_report.py::import@9`

```python
from collections import Counter
```

Supporting declaration: `tools/idea_maturity_metrics_report.py::import@10`

```python
from datetime import datetime, timezone
```

Supporting declaration: `tools/idea_maturity_metrics_report.py::import@11`

```python
from pathlib import Path
```

Supporting declaration: `tools/idea_maturity_metrics_report.py::import@12`

```python
from typing import Any
```

Supporting declaration: `tools/idea_maturity_metrics_report.py::_dict`

```python
def _dict(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}
```

Supporting declaration: `tools/idea_maturity_metrics_report.py::_text`

```python
def _text(value: Any, default: str = "") -> str:
    return value.strip() if isinstance(value, str) and value.strip() else default
```

Supporting declaration: `tools/idea_maturity_metrics_report.py::_int`

```python
def _int(value: Any, default: int = 0) -> int:
    if isinstance(value, bool):
        return default
    try:
        return int(value)
    except (TypeError, ValueError):
        return default
```

Supporting declaration: `tools/idea_maturity_metrics_report.py::_summary`

```python
def _summary(artifacts: dict[str, dict[str, Any]], key: str) -> dict[str, Any]:
    return _dict(_dict(artifacts.get(key)).get("summary"))
```

Supporting declaration: `tools/idea_maturity_metrics_report.py::_candidate_approval_intent_state`

```python
def _candidate_approval_intent_state(artifacts: dict[str, dict[str, Any]]) -> str:
    if "approval_intent" not in artifacts:
        return "not_reached" if _candidate_approval_state(artifacts) != "ready" else "not_available"
    summary = _summary(artifacts, "approval_intent")
    status = _text(summary.get("status"))
    if _int(summary.get("active_intent_count")) > 0 or "requested" in status:
        return "requested"
    if "blocked" in status:
        return "blocked"
    return "unknown"
```

Supporting declaration: `tools/idea_maturity_metrics_report.py::_candidate_approval_decision_state`

```python
def _candidate_approval_decision_state(artifacts: dict[str, dict[str, Any]]) -> str:
    decision = _dict(artifacts.get("candidate_approval_decision"))
    if decision:
        summary = _summary(artifacts, "candidate_approval_decision")
        readiness = _dict(decision.get("readiness"))
        decision_payload = _dict(decision.get("decision"))
        state = _text(summary.get("effective_state")) or _text(decision_payload.get("state"))
        status = (
            _text(summary.get("status"))
            or _text(readiness.get("review_state"))
            or _text(decision.get("status"))
        )
        if state == "approved" and readiness.get("ready") is True:
            return "materialized"
        if decision.get("dry_run") is True or status == "dry_run":
            return "dry_run"
        if _status_is_failed(status):
            return "failed"
        if _status_is_blocked(status) or state in {"rejected", "needs_context", "superseded"}:
            return "blocked"
        return "unknown"
    execution = _dict(artifacts.get("approval_execution"))
    if execution:
        summary = _summary(artifacts, "approval_execution")
        status = _text(summary.get("status")) or _text(execution.get("status"))
        if (
            _dict(execution.get("candidate_approval_decision_ref"))
            or summary.get("decision_written") is True
        ):
            return "materialized"
        if execution.get("dry_run") is True:
            return "dry_run"
        if "failed" in status or "blocked" in status:
            return "failed" if "failed" in status else "blocked"
        return "unknown"
    if _candidate_approval_intent_state(artifacts) in {"requested", "ready"}:
        return "not_available"
    return "not_reached"
```

Supporting declaration: `tools/idea_maturity_metrics_report.py::_promotion_request_state`

```python
def _promotion_request_state(artifacts: dict[str, dict[str, Any]]) -> str:
    request = _dict(artifacts.get("promotion_request"))
    if not request:
        return (
            "not_available"
            if _candidate_approval_decision_state(artifacts) == "materialized"
            else "not_reached"
        )
    summary = _summary(artifacts, "promotion_request")
    if request.get("ok") is True or summary.get("promotion_ready") is True:
        return "requested"
    if _int(summary.get("error_count")) > 0:
        return "blocked"
    return "unknown"
```

Supporting declaration: `tools/idea_maturity_metrics_report.py::_promotion_execution_state`

```python
def _promotion_execution_state(artifacts: dict[str, dict[str, Any]]) -> str:
    execution = _dict(artifacts.get("promotion_execution"))
    if not execution:
        return (
            "not_available" if _promotion_request_state(artifacts) == "requested" else "not_reached"
        )
    summary = _summary(artifacts, "promotion_execution")
    status = _text(summary.get("status")) or _text(execution.get("status"))
    if execution.get("dry_run") is True or status == "dry_run":
        return "dry_run"
    if _int(summary.get("error_count")) > 0 or _status_is_failed(status):
        return "failed"
    if _status_is_blocked(status):
        return "blocked"
    if summary.get("commit_created") is True or summary.get("review_opened") is True:
        return "executed"
    return "unknown"
```

Supporting declaration: `tools/idea_maturity_metrics_report.py::_review_status`

```python
def _review_status(artifacts: dict[str, dict[str, Any]]) -> str:
    review = _dict(artifacts.get("review_status"))
    if not review:
        return (
            "not_reached"
            if _promotion_execution_state(artifacts) == "not_reached"
            else "not_available"
        )
    review_state = _text(review.get("review_state"))
    if review.get("review_probe_only") is True and review_state == "merged":
        return "unknown"
    if review_state in {"open", "merged"}:
        return review_state
    if review_state == "closed":
        return "blocked"
    summary = _summary(artifacts, "review_status")
    status = _text(summary.get("review_status")) or _text(summary.get("status"))
    if status in {"open", "merged", "blocked", "unknown"}:
        return status
    if "merged" in status:
        return "merged"
    if "open" in status:
        return "open"
    if "blocked" in status or "failed" in status:
        return "blocked"
    return "unknown"
```

Opportunity: ______  Concern kind: ______

Evidence / missing context: ______

## sg-002

[Pinned source](https://github.com/0al-spec/SpecGraph/blob/425078cc74e1c2cccbff259b5505b1b958b8e904/tools/idea_maturity_candidate_approval_spec.py#L7-L43)

```python
_SPEC = FirstMatch.with_fallback(
    (
        (
            PredicateSpec(
                lambda c: (
                    c.mapping(c.artifact("repaired_repair_session").get("readiness_impact")).get(
                        "ready_for_candidate_approval"
                    )
                    is True
                    or c.summary("repaired_repair_session").get("ready_for_candidate_approval")
                    is True
                    or c.summary("repaired_handoff").get("ready_for_candidate_approval") is True
                ),
                name="candidate_approval.ready",
            ),
            "ready",
        ),
        (
            PredicateSpec(
                lambda c: (
                    c.has_content("repaired_repair_session") or c.has_content("repaired_handoff")
                ),
                name="candidate_approval.repair_blocked",
            ),
            "blocked",
        ),
        (
            PredicateSpec(
                lambda c: c.has_content("candidate_graph"),
                name="candidate_approval.candidate_exists",
            ),
            "not_reached",
        ),
    ),
    "not_available",
    name="candidate_approval_state",
)
```

Supporting declaration: `tools/idea_maturity_candidate_approval_spec.py::import@3`

```python
from specification_core import FirstMatch, PredicateSpec, TraceRecorder
```

Supporting declaration: `tools/idea_maturity_candidate_approval_spec.py::import@5`

```python
from idea_maturity_lifecycle_context import LifecycleStateContext, decide
```

Supporting declaration: `tools/idea_maturity_lifecycle_context.py::LifecycleStateContext`

```python
@dataclass(frozen=True)
class LifecycleStateContext:
    artifacts: dict[str, dict[str, Any]]

    def artifact(self, key: str) -> dict[str, Any]:
        return _dict(self.artifacts.get(key))

    def has_content(self, key: str) -> bool:
        return bool(self.artifacts.get(key))

    def summary(self, key: str) -> dict[str, Any]:
        return _dict(self.artifact(key).get("summary"))

    @staticmethod
    def mapping(value: Any) -> dict[str, Any]:
        return _dict(value)

    @staticmethod
    def text(value: Any, default: str = "") -> str:
        return _text(value, default)

    @staticmethod
    def integer(value: Any, default: int = 0) -> int:
        return _int(value, default)

    @staticmethod
    def is_failed(status: str) -> bool:
        return _status_is_failed(status)

    @staticmethod
    def is_blocked(status: str) -> bool:
        return _status_is_blocked(status)
```

Supporting declaration: `tools/idea_maturity_lifecycle_context.py::_dict`

```python
def _dict(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}
```

Supporting declaration: `tools/idea_maturity_lifecycle_context.py::_text`

```python
def _text(value: Any, default: str = "") -> str:
    return value.strip() if isinstance(value, str) and value.strip() else default
```

Supporting declaration: `tools/idea_maturity_lifecycle_context.py::_int`

```python
def _int(value: Any, default: int = 0) -> int:
    if isinstance(value, bool):
        return default
    try:
        return int(value)
    except (TypeError, ValueError):
        return default
```

Supporting declaration: `tools/idea_maturity_lifecycle_context.py::_summary`

```python
def _summary(artifacts: dict[str, dict[str, Any]], key: str) -> dict[str, Any]:
    return _dict(_dict(artifacts.get(key)).get("summary"))
```

Opportunity: ______  Concern kind: ______

Evidence / missing context: ______

## sg-003

[Pinned source](https://github.com/0al-spec/SpecGraph/blob/b7643721b11b5d4768bc966abab7dddd1092a5bd/tools/idea_maturity_metrics_report.py#L1463-L1472)

```python
def _candidate_approval_intent_state(artifacts: dict[str, dict[str, Any]]) -> str:
    if "approval_intent" not in artifacts:
        return "not_reached" if _candidate_approval_state(artifacts) != "ready" else "not_available"
    summary = _summary(artifacts, "approval_intent")
    status = _text(summary.get("status"))
    if _int(summary.get("active_intent_count")) > 0 or "requested" in status:
        return "requested"
    if "blocked" in status:
        return "blocked"
    return "unknown"
```

Supporting declaration: `tools/idea_maturity_metrics_report.py::import@3`

```python
from __future__ import annotations
```

Supporting declaration: `tools/idea_maturity_metrics_report.py::import@5`

```python
import argparse
```

Supporting declaration: `tools/idea_maturity_metrics_report.py::import@6`

```python
import json
```

Supporting declaration: `tools/idea_maturity_metrics_report.py::import@7`

```python
import re
```

Supporting declaration: `tools/idea_maturity_metrics_report.py::import@8`

```python
import sys
```

Supporting declaration: `tools/idea_maturity_metrics_report.py::import@9`

```python
from collections import Counter
```

Supporting declaration: `tools/idea_maturity_metrics_report.py::import@10`

```python
from datetime import datetime, timezone
```

Supporting declaration: `tools/idea_maturity_metrics_report.py::import@11`

```python
from pathlib import Path
```

Supporting declaration: `tools/idea_maturity_metrics_report.py::import@12`

```python
from typing import Any
```

Supporting declaration: `tools/idea_maturity_metrics_report.py::_dict`

```python
def _dict(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}
```

Supporting declaration: `tools/idea_maturity_metrics_report.py::_text`

```python
def _text(value: Any, default: str = "") -> str:
    return value.strip() if isinstance(value, str) and value.strip() else default
```

Supporting declaration: `tools/idea_maturity_metrics_report.py::_int`

```python
def _int(value: Any, default: int = 0) -> int:
    if isinstance(value, bool):
        return default
    try:
        return int(value)
    except (TypeError, ValueError):
        return default
```

Supporting declaration: `tools/idea_maturity_metrics_report.py::_summary`

```python
def _summary(artifacts: dict[str, dict[str, Any]], key: str) -> dict[str, Any]:
    return _dict(_dict(artifacts.get(key)).get("summary"))
```

Opportunity: ______  Concern kind: ______

Evidence / missing context: ______

## sg-004

[Pinned source](https://github.com/0al-spec/SpecGraph/blob/425078cc74e1c2cccbff259b5505b1b958b8e904/tools/idea_maturity_candidate_approval_intent_spec.py#L8-L54)

```python
_SPEC = FirstMatch.with_fallback(
    (
        (
            PredicateSpec(
                lambda c: (
                    "approval_intent" not in c.artifacts and candidate_approval_state(c) != "ready"
                ),
                name="approval_intent.not_reached",
            ),
            "not_reached",
        ),
        (
            PredicateSpec(
                lambda c: (
                    "approval_intent" not in c.artifacts and candidate_approval_state(c) == "ready"
                ),
                name="approval_intent.unavailable_after_ready",
            ),
            "not_available",
        ),
        (
            PredicateSpec(
                lambda c: (
                    "approval_intent" in c.artifacts
                    and (
                        c.integer(c.summary("approval_intent").get("active_intent_count")) > 0
                        or "requested" in c.text(c.summary("approval_intent").get("status"))
                    )
                ),
                name="approval_intent.requested",
            ),
            "requested",
        ),
        (
            PredicateSpec(
                lambda c: (
                    "approval_intent" in c.artifacts
                    and "blocked" in c.text(c.summary("approval_intent").get("status"))
                ),
                name="approval_intent.blocked",
            ),
            "blocked",
        ),
    ),
    "unknown",
    name="candidate_approval_intent_state",
)
```

Supporting declaration: `tools/idea_maturity_candidate_approval_intent_spec.py::import@3`

```python
from specification_core import FirstMatch, PredicateSpec, TraceRecorder
```

Supporting declaration: `tools/idea_maturity_candidate_approval_intent_spec.py::import@5`

```python
from idea_maturity_candidate_approval_spec import candidate_approval_state
```

Supporting declaration: `tools/idea_maturity_candidate_approval_intent_spec.py::import@6`

```python
from idea_maturity_lifecycle_context import LifecycleStateContext, decide
```

Supporting declaration: `tools/idea_maturity_lifecycle_context.py::LifecycleStateContext`

```python
@dataclass(frozen=True)
class LifecycleStateContext:
    artifacts: dict[str, dict[str, Any]]

    def artifact(self, key: str) -> dict[str, Any]:
        return _dict(self.artifacts.get(key))

    def has_content(self, key: str) -> bool:
        return bool(self.artifacts.get(key))

    def summary(self, key: str) -> dict[str, Any]:
        return _dict(self.artifact(key).get("summary"))

    @staticmethod
    def mapping(value: Any) -> dict[str, Any]:
        return _dict(value)

    @staticmethod
    def text(value: Any, default: str = "") -> str:
        return _text(value, default)

    @staticmethod
    def integer(value: Any, default: int = 0) -> int:
        return _int(value, default)

    @staticmethod
    def is_failed(status: str) -> bool:
        return _status_is_failed(status)

    @staticmethod
    def is_blocked(status: str) -> bool:
        return _status_is_blocked(status)
```

Supporting declaration: `tools/idea_maturity_lifecycle_context.py::_dict`

```python
def _dict(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}
```

Supporting declaration: `tools/idea_maturity_lifecycle_context.py::_text`

```python
def _text(value: Any, default: str = "") -> str:
    return value.strip() if isinstance(value, str) and value.strip() else default
```

Supporting declaration: `tools/idea_maturity_lifecycle_context.py::_int`

```python
def _int(value: Any, default: int = 0) -> int:
    if isinstance(value, bool):
        return default
    try:
        return int(value)
    except (TypeError, ValueError):
        return default
```

Supporting declaration: `tools/idea_maturity_lifecycle_context.py::_summary`

```python
def _summary(artifacts: dict[str, dict[str, Any]], key: str) -> dict[str, Any]:
    return _dict(_dict(artifacts.get(key)).get("summary"))
```

Opportunity: ______  Concern kind: ______

Evidence / missing context: ______

## sg-005

[Pinned source](https://github.com/0al-spec/SpecGraph/blob/b7643721b11b5d4768bc966abab7dddd1092a5bd/tools/idea_maturity_metrics_report.py#L1475-L1512)

```python
def _candidate_approval_decision_state(artifacts: dict[str, dict[str, Any]]) -> str:
    decision = _dict(artifacts.get("candidate_approval_decision"))
    if decision:
        summary = _summary(artifacts, "candidate_approval_decision")
        readiness = _dict(decision.get("readiness"))
        decision_payload = _dict(decision.get("decision"))
        state = _text(summary.get("effective_state")) or _text(decision_payload.get("state"))
        status = (
            _text(summary.get("status"))
            or _text(readiness.get("review_state"))
            or _text(decision.get("status"))
        )
        if state == "approved" and readiness.get("ready") is True:
            return "materialized"
        if decision.get("dry_run") is True or status == "dry_run":
            return "dry_run"
        if _status_is_failed(status):
            return "failed"
        if _status_is_blocked(status) or state in {"rejected", "needs_context", "superseded"}:
            return "blocked"
        return "unknown"
    execution = _dict(artifacts.get("approval_execution"))
    if execution:
        summary = _summary(artifacts, "approval_execution")
        status = _text(summary.get("status")) or _text(execution.get("status"))
        if (
            _dict(execution.get("candidate_approval_decision_ref"))
            or summary.get("decision_written") is True
        ):
            return "materialized"
        if execution.get("dry_run") is True:
            return "dry_run"
        if "failed" in status or "blocked" in status:
            return "failed" if "failed" in status else "blocked"
        return "unknown"
    if _candidate_approval_intent_state(artifacts) in {"requested", "ready"}:
        return "not_available"
    return "not_reached"
```

Supporting declaration: `tools/idea_maturity_metrics_report.py::import@3`

```python
from __future__ import annotations
```

Supporting declaration: `tools/idea_maturity_metrics_report.py::import@5`

```python
import argparse
```

Supporting declaration: `tools/idea_maturity_metrics_report.py::import@6`

```python
import json
```

Supporting declaration: `tools/idea_maturity_metrics_report.py::import@7`

```python
import re
```

Supporting declaration: `tools/idea_maturity_metrics_report.py::import@8`

```python
import sys
```

Supporting declaration: `tools/idea_maturity_metrics_report.py::import@9`

```python
from collections import Counter
```

Supporting declaration: `tools/idea_maturity_metrics_report.py::import@10`

```python
from datetime import datetime, timezone
```

Supporting declaration: `tools/idea_maturity_metrics_report.py::import@11`

```python
from pathlib import Path
```

Supporting declaration: `tools/idea_maturity_metrics_report.py::import@12`

```python
from typing import Any
```

Supporting declaration: `tools/idea_maturity_metrics_report.py::_dict`

```python
def _dict(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}
```

Supporting declaration: `tools/idea_maturity_metrics_report.py::_text`

```python
def _text(value: Any, default: str = "") -> str:
    return value.strip() if isinstance(value, str) and value.strip() else default
```

Supporting declaration: `tools/idea_maturity_metrics_report.py::_int`

```python
def _int(value: Any, default: int = 0) -> int:
    if isinstance(value, bool):
        return default
    try:
        return int(value)
    except (TypeError, ValueError):
        return default
```

Supporting declaration: `tools/idea_maturity_metrics_report.py::_summary`

```python
def _summary(artifacts: dict[str, dict[str, Any]], key: str) -> dict[str, Any]:
    return _dict(_dict(artifacts.get(key)).get("summary"))
```

Opportunity: ______  Concern kind: ______

Evidence / missing context: ______

## sg-006

[Pinned source](https://github.com/0al-spec/SpecGraph/blob/425078cc74e1c2cccbff259b5505b1b958b8e904/tools/idea_maturity_candidate_approval_decision_spec.py#L40-L137)

```python
_SPEC = FirstMatch.with_fallback(
    (
        (
            PredicateSpec(
                lambda c: (
                    _has_decision(c)
                    and _state(c) == "approved"
                    and c.artifact("candidate_approval_decision").get("readiness", {}).get("ready")
                    is True
                ),
                name="approval_decision.approved_ready",
            ),
            "materialized",
        ),
        (
            PredicateSpec(
                lambda c: (
                    _has_decision(c)
                    and (
                        c.artifact("candidate_approval_decision").get("dry_run") is True
                        or _status(c) == "dry_run"
                    )
                ),
                name="approval_decision.dry_run",
            ),
            "dry_run",
        ),
        (
            PredicateSpec(
                lambda c: _has_decision(c) and c.is_failed(_status(c)),
                name="approval_decision.failed",
            ),
            "failed",
        ),
        (
            PredicateSpec(
                lambda c: (
                    _has_decision(c)
                    and (
                        c.is_blocked(_status(c))
                        or _state(c) in {"rejected", "needs_context", "superseded"}
                    )
                ),
                name="approval_decision.blocked",
            ),
            "blocked",
        ),
        (PredicateSpec(lambda c: _has_decision(c), name="approval_decision.unknown"), "unknown"),
        (
            PredicateSpec(
                lambda c: (
                    _has_execution(c)
                    and (
                        bool(
                            c.artifact("approval_execution").get("candidate_approval_decision_ref")
                        )
                        or c.summary("approval_execution").get("decision_written") is True
                    )
                ),
                name="approval_execution.materialized",
            ),
            "materialized",
        ),
        (
            PredicateSpec(
                lambda c: (
                    _has_execution(c) and c.artifact("approval_execution").get("dry_run") is True
                ),
                name="approval_execution.dry_run",
            ),
            "dry_run",
        ),
        (
            PredicateSpec(
                lambda c: _has_execution(c) and "failed" in _exec_status(c),
                name="approval_execution.failed",
            ),
            "failed",
        ),
        (
            PredicateSpec(
                lambda c: _has_execution(c) and "blocked" in _exec_status(c),
                name="approval_execution.blocked",
            ),
            "blocked",
        ),
        (PredicateSpec(lambda c: _has_execution(c), name="approval_execution.unknown"), "unknown"),
        (
            PredicateSpec(
                lambda c: candidate_approval_intent_state(c) in {"requested", "ready"},
                name="approval_decision.not_available",
            ),
            "not_available",
        ),
    ),
    "not_reached",
    name="candidate_approval_decision_state",
)
```

Supporting declaration: `tools/idea_maturity_candidate_approval_decision_spec.py::import@3`

```python
from specification_core import FirstMatch, PredicateSpec, TraceRecorder
```

Supporting declaration: `tools/idea_maturity_candidate_approval_decision_spec.py::import@5`

```python
from idea_maturity_candidate_approval_intent_spec import candidate_approval_intent_state
```

Supporting declaration: `tools/idea_maturity_candidate_approval_decision_spec.py::import@6`

```python
from idea_maturity_lifecycle_context import LifecycleStateContext, decide
```

Supporting declaration: `tools/idea_maturity_lifecycle_context.py::LifecycleStateContext`

```python
@dataclass(frozen=True)
class LifecycleStateContext:
    artifacts: dict[str, dict[str, Any]]

    def artifact(self, key: str) -> dict[str, Any]:
        return _dict(self.artifacts.get(key))

    def has_content(self, key: str) -> bool:
        return bool(self.artifacts.get(key))

    def summary(self, key: str) -> dict[str, Any]:
        return _dict(self.artifact(key).get("summary"))

    @staticmethod
    def mapping(value: Any) -> dict[str, Any]:
        return _dict(value)

    @staticmethod
    def text(value: Any, default: str = "") -> str:
        return _text(value, default)

    @staticmethod
    def integer(value: Any, default: int = 0) -> int:
        return _int(value, default)

    @staticmethod
    def is_failed(status: str) -> bool:
        return _status_is_failed(status)

    @staticmethod
    def is_blocked(status: str) -> bool:
        return _status_is_blocked(status)
```

Supporting declaration: `tools/idea_maturity_candidate_approval_decision_spec.py::_status`

```python
def _status(c):
    artifact = c.artifact("candidate_approval_decision")
    summary = c.summary("candidate_approval_decision")
    readiness = c.mapping(artifact.get("readiness"))
    return (
        c.text(summary.get("status"))
        or c.text(readiness.get("review_state"))
        or c.text(artifact.get("status"))
    )
```

Supporting declaration: `tools/idea_maturity_lifecycle_context.py::_dict`

```python
def _dict(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}
```

Supporting declaration: `tools/idea_maturity_lifecycle_context.py::_text`

```python
def _text(value: Any, default: str = "") -> str:
    return value.strip() if isinstance(value, str) and value.strip() else default
```

Supporting declaration: `tools/idea_maturity_lifecycle_context.py::_int`

```python
def _int(value: Any, default: int = 0) -> int:
    if isinstance(value, bool):
        return default
    try:
        return int(value)
    except (TypeError, ValueError):
        return default
```

Supporting declaration: `tools/idea_maturity_lifecycle_context.py::_summary`

```python
def _summary(artifacts: dict[str, dict[str, Any]], key: str) -> dict[str, Any]:
    return _dict(_dict(artifacts.get(key)).get("summary"))
```

Opportunity: ______  Concern kind: ______

Evidence / missing context: ______

## sg-007

[Pinned source](https://github.com/0al-spec/SpecGraph/blob/b7643721b11b5d4768bc966abab7dddd1092a5bd/tools/idea_maturity_metrics_report.py#L1515-L1524)

```python
def _platform_promotion_state(artifacts: dict[str, dict[str, Any]]) -> str:
    execution_state = _promotion_execution_state(artifacts)
    if execution_state not in {"not_reached", "not_available"}:
        return execution_state
    request_state = _promotion_request_state(artifacts)
    if request_state == "requested":
        return "requested"
    if _candidate_approval_decision_state(artifacts) == "materialized":
        return "ready"
    return "not_reached"
```

Supporting declaration: `tools/idea_maturity_metrics_report.py::import@3`

```python
from __future__ import annotations
```

Supporting declaration: `tools/idea_maturity_metrics_report.py::import@5`

```python
import argparse
```

Supporting declaration: `tools/idea_maturity_metrics_report.py::import@6`

```python
import json
```

Supporting declaration: `tools/idea_maturity_metrics_report.py::import@7`

```python
import re
```

Supporting declaration: `tools/idea_maturity_metrics_report.py::import@8`

```python
import sys
```

Supporting declaration: `tools/idea_maturity_metrics_report.py::import@9`

```python
from collections import Counter
```

Supporting declaration: `tools/idea_maturity_metrics_report.py::import@10`

```python
from datetime import datetime, timezone
```

Supporting declaration: `tools/idea_maturity_metrics_report.py::import@11`

```python
from pathlib import Path
```

Supporting declaration: `tools/idea_maturity_metrics_report.py::import@12`

```python
from typing import Any
```

Supporting declaration: `tools/idea_maturity_metrics_report.py::_dict`

```python
def _dict(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}
```

Supporting declaration: `tools/idea_maturity_metrics_report.py::_text`

```python
def _text(value: Any, default: str = "") -> str:
    return value.strip() if isinstance(value, str) and value.strip() else default
```

Supporting declaration: `tools/idea_maturity_metrics_report.py::_int`

```python
def _int(value: Any, default: int = 0) -> int:
    if isinstance(value, bool):
        return default
    try:
        return int(value)
    except (TypeError, ValueError):
        return default
```

Supporting declaration: `tools/idea_maturity_metrics_report.py::_summary`

```python
def _summary(artifacts: dict[str, dict[str, Any]], key: str) -> dict[str, Any]:
    return _dict(_dict(artifacts.get(key)).get("summary"))
```

Supporting declaration: `tools/idea_maturity_metrics_report.py::_candidate_approval_intent_state`

```python
def _candidate_approval_intent_state(artifacts: dict[str, dict[str, Any]]) -> str:
    if "approval_intent" not in artifacts:
        return "not_reached" if _candidate_approval_state(artifacts) != "ready" else "not_available"
    summary = _summary(artifacts, "approval_intent")
    status = _text(summary.get("status"))
    if _int(summary.get("active_intent_count")) > 0 or "requested" in status:
        return "requested"
    if "blocked" in status:
        return "blocked"
    return "unknown"
```

Supporting declaration: `tools/idea_maturity_metrics_report.py::_candidate_approval_decision_state`

```python
def _candidate_approval_decision_state(artifacts: dict[str, dict[str, Any]]) -> str:
    decision = _dict(artifacts.get("candidate_approval_decision"))
    if decision:
        summary = _summary(artifacts, "candidate_approval_decision")
        readiness = _dict(decision.get("readiness"))
        decision_payload = _dict(decision.get("decision"))
        state = _text(summary.get("effective_state")) or _text(decision_payload.get("state"))
        status = (
            _text(summary.get("status"))
            or _text(readiness.get("review_state"))
            or _text(decision.get("status"))
        )
        if state == "approved" and readiness.get("ready") is True:
            return "materialized"
        if decision.get("dry_run") is True or status == "dry_run":
            return "dry_run"
        if _status_is_failed(status):
            return "failed"
        if _status_is_blocked(status) or state in {"rejected", "needs_context", "superseded"}:
            return "blocked"
        return "unknown"
    execution = _dict(artifacts.get("approval_execution"))
    if execution:
        summary = _summary(artifacts, "approval_execution")
        status = _text(summary.get("status")) or _text(execution.get("status"))
        if (
            _dict(execution.get("candidate_approval_decision_ref"))
            or summary.get("decision_written") is True
        ):
            return "materialized"
        if execution.get("dry_run") is True:
            return "dry_run"
        if "failed" in status or "blocked" in status:
            return "failed" if "failed" in status else "blocked"
        return "unknown"
    if _candidate_approval_intent_state(artifacts) in {"requested", "ready"}:
        return "not_available"
    return "not_reached"
```

Supporting declaration: `tools/idea_maturity_metrics_report.py::_promotion_request_state`

```python
def _promotion_request_state(artifacts: dict[str, dict[str, Any]]) -> str:
    request = _dict(artifacts.get("promotion_request"))
    if not request:
        return (
            "not_available"
            if _candidate_approval_decision_state(artifacts) == "materialized"
            else "not_reached"
        )
    summary = _summary(artifacts, "promotion_request")
    if request.get("ok") is True or summary.get("promotion_ready") is True:
        return "requested"
    if _int(summary.get("error_count")) > 0:
        return "blocked"
    return "unknown"
```

Supporting declaration: `tools/idea_maturity_metrics_report.py::_promotion_execution_state`

```python
def _promotion_execution_state(artifacts: dict[str, dict[str, Any]]) -> str:
    execution = _dict(artifacts.get("promotion_execution"))
    if not execution:
        return (
            "not_available" if _promotion_request_state(artifacts) == "requested" else "not_reached"
        )
    summary = _summary(artifacts, "promotion_execution")
    status = _text(summary.get("status")) or _text(execution.get("status"))
    if execution.get("dry_run") is True or status == "dry_run":
        return "dry_run"
    if _int(summary.get("error_count")) > 0 or _status_is_failed(status):
        return "failed"
    if _status_is_blocked(status):
        return "blocked"
    if summary.get("commit_created") is True or summary.get("review_opened") is True:
        return "executed"
    return "unknown"
```

Supporting declaration: `tools/idea_maturity_metrics_report.py::_review_status`

```python
def _review_status(artifacts: dict[str, dict[str, Any]]) -> str:
    review = _dict(artifacts.get("review_status"))
    if not review:
        return (
            "not_reached"
            if _promotion_execution_state(artifacts) == "not_reached"
            else "not_available"
        )
    review_state = _text(review.get("review_state"))
    if review.get("review_probe_only") is True and review_state == "merged":
        return "unknown"
    if review_state in {"open", "merged"}:
        return review_state
    if review_state == "closed":
        return "blocked"
    summary = _summary(artifacts, "review_status")
    status = _text(summary.get("review_status")) or _text(summary.get("status"))
    if status in {"open", "merged", "blocked", "unknown"}:
        return status
    if "merged" in status:
        return "merged"
    if "open" in status:
        return "open"
    if "blocked" in status or "failed" in status:
        return "blocked"
    return "unknown"
```

Opportunity: ______  Concern kind: ______

Evidence / missing context: ______

## sg-008

[Pinned source](https://github.com/0al-spec/SpecGraph/blob/425078cc74e1c2cccbff259b5505b1b958b8e904/tools/idea_maturity_platform_promotion_spec.py#L10-L36)

```python
_SPEC = FirstMatch.with_fallback(
    (
        (
            PredicateSpec(
                lambda c: promotion_execution_state(c) not in {"not_reached", "not_available"},
                name="platform_promotion.execution_state",
            ),
            "__execution__",
        ),
        (
            PredicateSpec(
                lambda c: promotion_request_state(c) == "requested",
                name="platform_promotion.requested",
            ),
            "requested",
        ),
        (
            PredicateSpec(
                lambda c: candidate_approval_decision_state(c) == "materialized",
                name="platform_promotion.ready",
            ),
            "ready",
        ),
    ),
    "not_reached",
    name="platform_promotion_state",
)
```

Supporting declaration: `tools/idea_maturity_platform_promotion_spec.py::import@3`

```python
from specification_core import FirstMatch, PredicateSpec, TraceRecorder
```

Supporting declaration: `tools/idea_maturity_platform_promotion_spec.py::import@5`

```python
from idea_maturity_candidate_approval_decision_spec import candidate_approval_decision_state
```

Supporting declaration: `tools/idea_maturity_platform_promotion_spec.py::import@6`

```python
from idea_maturity_lifecycle_context import LifecycleStateContext, decide
```

Supporting declaration: `tools/idea_maturity_platform_promotion_spec.py::import@7`

```python
from idea_maturity_promotion_execution_spec import promotion_execution_state
```

Supporting declaration: `tools/idea_maturity_platform_promotion_spec.py::import@8`

```python
from idea_maturity_promotion_request_spec import promotion_request_state
```

Supporting declaration: `tools/idea_maturity_lifecycle_context.py::LifecycleStateContext`

```python
@dataclass(frozen=True)
class LifecycleStateContext:
    artifacts: dict[str, dict[str, Any]]

    def artifact(self, key: str) -> dict[str, Any]:
        return _dict(self.artifacts.get(key))

    def has_content(self, key: str) -> bool:
        return bool(self.artifacts.get(key))

    def summary(self, key: str) -> dict[str, Any]:
        return _dict(self.artifact(key).get("summary"))

    @staticmethod
    def mapping(value: Any) -> dict[str, Any]:
        return _dict(value)

    @staticmethod
    def text(value: Any, default: str = "") -> str:
        return _text(value, default)

    @staticmethod
    def integer(value: Any, default: int = 0) -> int:
        return _int(value, default)

    @staticmethod
    def is_failed(status: str) -> bool:
        return _status_is_failed(status)

    @staticmethod
    def is_blocked(status: str) -> bool:
        return _status_is_blocked(status)
```

Supporting declaration: `tools/idea_maturity_lifecycle_context.py::_dict`

```python
def _dict(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}
```

Supporting declaration: `tools/idea_maturity_lifecycle_context.py::_text`

```python
def _text(value: Any, default: str = "") -> str:
    return value.strip() if isinstance(value, str) and value.strip() else default
```

Supporting declaration: `tools/idea_maturity_lifecycle_context.py::_int`

```python
def _int(value: Any, default: int = 0) -> int:
    if isinstance(value, bool):
        return default
    try:
        return int(value)
    except (TypeError, ValueError):
        return default
```

Supporting declaration: `tools/idea_maturity_lifecycle_context.py::_summary`

```python
def _summary(artifacts: dict[str, dict[str, Any]], key: str) -> dict[str, Any]:
    return _dict(_dict(artifacts.get(key)).get("summary"))
```

Opportunity: ______  Concern kind: ______

Evidence / missing context: ______

## sg-009

[Pinned source](https://github.com/0al-spec/SpecGraph/blob/b7643721b11b5d4768bc966abab7dddd1092a5bd/tools/idea_maturity_metrics_report.py#L1535-L1548)

```python
def _promotion_request_state(artifacts: dict[str, dict[str, Any]]) -> str:
    request = _dict(artifacts.get("promotion_request"))
    if not request:
        return (
            "not_available"
            if _candidate_approval_decision_state(artifacts) == "materialized"
            else "not_reached"
        )
    summary = _summary(artifacts, "promotion_request")
    if request.get("ok") is True or summary.get("promotion_ready") is True:
        return "requested"
    if _int(summary.get("error_count")) > 0:
        return "blocked"
    return "unknown"
```

Supporting declaration: `tools/idea_maturity_metrics_report.py::import@3`

```python
from __future__ import annotations
```

Supporting declaration: `tools/idea_maturity_metrics_report.py::import@5`

```python
import argparse
```

Supporting declaration: `tools/idea_maturity_metrics_report.py::import@6`

```python
import json
```

Supporting declaration: `tools/idea_maturity_metrics_report.py::import@7`

```python
import re
```

Supporting declaration: `tools/idea_maturity_metrics_report.py::import@8`

```python
import sys
```

Supporting declaration: `tools/idea_maturity_metrics_report.py::import@9`

```python
from collections import Counter
```

Supporting declaration: `tools/idea_maturity_metrics_report.py::import@10`

```python
from datetime import datetime, timezone
```

Supporting declaration: `tools/idea_maturity_metrics_report.py::import@11`

```python
from pathlib import Path
```

Supporting declaration: `tools/idea_maturity_metrics_report.py::import@12`

```python
from typing import Any
```

Supporting declaration: `tools/idea_maturity_metrics_report.py::_dict`

```python
def _dict(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}
```

Supporting declaration: `tools/idea_maturity_metrics_report.py::_text`

```python
def _text(value: Any, default: str = "") -> str:
    return value.strip() if isinstance(value, str) and value.strip() else default
```

Supporting declaration: `tools/idea_maturity_metrics_report.py::_int`

```python
def _int(value: Any, default: int = 0) -> int:
    if isinstance(value, bool):
        return default
    try:
        return int(value)
    except (TypeError, ValueError):
        return default
```

Supporting declaration: `tools/idea_maturity_metrics_report.py::_summary`

```python
def _summary(artifacts: dict[str, dict[str, Any]], key: str) -> dict[str, Any]:
    return _dict(_dict(artifacts.get(key)).get("summary"))
```

Opportunity: ______  Concern kind: ______

Evidence / missing context: ______

## sg-010

[Pinned source](https://github.com/0al-spec/SpecGraph/blob/425078cc74e1c2cccbff259b5505b1b958b8e904/tools/idea_maturity_promotion_request_spec.py#L8-L46)

```python
_SPEC = FirstMatch.with_fallback(
    (
        (
            PredicateSpec(
                lambda c: (
                    not c.artifact("promotion_request")
                    and candidate_approval_decision_state(c) == "materialized"
                ),
                name="promotion_request.unavailable_after_approval",
            ),
            "not_available",
        ),
        (
            PredicateSpec(
                lambda c: (
                    c.artifact("promotion_request").get("ok") is True
                    or c.summary("promotion_request").get("promotion_ready") is True
                ),
                name="promotion_request.requested",
            ),
            "requested",
        ),
        (
            PredicateSpec(
                lambda c: c.integer(c.summary("promotion_request").get("error_count")) > 0,
                name="promotion_request.blocked",
            ),
            "blocked",
        ),
        (
            PredicateSpec(
                lambda c: bool(c.artifact("promotion_request")), name="promotion_request.unknown"
            ),
            "unknown",
        ),
    ),
    "not_reached",
    name="promotion_request_state",
)
```

Supporting declaration: `tools/idea_maturity_promotion_request_spec.py::import@3`

```python
from specification_core import FirstMatch, PredicateSpec, TraceRecorder
```

Supporting declaration: `tools/idea_maturity_promotion_request_spec.py::import@5`

```python
from idea_maturity_candidate_approval_decision_spec import candidate_approval_decision_state
```

Supporting declaration: `tools/idea_maturity_promotion_request_spec.py::import@6`

```python
from idea_maturity_lifecycle_context import LifecycleStateContext, decide
```

Supporting declaration: `tools/idea_maturity_lifecycle_context.py::LifecycleStateContext`

```python
@dataclass(frozen=True)
class LifecycleStateContext:
    artifacts: dict[str, dict[str, Any]]

    def artifact(self, key: str) -> dict[str, Any]:
        return _dict(self.artifacts.get(key))

    def has_content(self, key: str) -> bool:
        return bool(self.artifacts.get(key))

    def summary(self, key: str) -> dict[str, Any]:
        return _dict(self.artifact(key).get("summary"))

    @staticmethod
    def mapping(value: Any) -> dict[str, Any]:
        return _dict(value)

    @staticmethod
    def text(value: Any, default: str = "") -> str:
        return _text(value, default)

    @staticmethod
    def integer(value: Any, default: int = 0) -> int:
        return _int(value, default)

    @staticmethod
    def is_failed(status: str) -> bool:
        return _status_is_failed(status)

    @staticmethod
    def is_blocked(status: str) -> bool:
        return _status_is_blocked(status)
```

Supporting declaration: `tools/idea_maturity_lifecycle_context.py::_dict`

```python
def _dict(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}
```

Supporting declaration: `tools/idea_maturity_lifecycle_context.py::_text`

```python
def _text(value: Any, default: str = "") -> str:
    return value.strip() if isinstance(value, str) and value.strip() else default
```

Supporting declaration: `tools/idea_maturity_lifecycle_context.py::_int`

```python
def _int(value: Any, default: int = 0) -> int:
    if isinstance(value, bool):
        return default
    try:
        return int(value)
    except (TypeError, ValueError):
        return default
```

Supporting declaration: `tools/idea_maturity_lifecycle_context.py::_summary`

```python
def _summary(artifacts: dict[str, dict[str, Any]], key: str) -> dict[str, Any]:
    return _dict(_dict(artifacts.get(key)).get("summary"))
```

Opportunity: ______  Concern kind: ______

Evidence / missing context: ______

## sg-011

[Pinned source](https://github.com/0al-spec/SpecGraph/blob/b7643721b11b5d4768bc966abab7dddd1092a5bd/tools/idea_maturity_metrics_report.py#L1551-L1567)

```python
def _promotion_execution_state(artifacts: dict[str, dict[str, Any]]) -> str:
    execution = _dict(artifacts.get("promotion_execution"))
    if not execution:
        return (
            "not_available" if _promotion_request_state(artifacts) == "requested" else "not_reached"
        )
    summary = _summary(artifacts, "promotion_execution")
    status = _text(summary.get("status")) or _text(execution.get("status"))
    if execution.get("dry_run") is True or status == "dry_run":
        return "dry_run"
    if _int(summary.get("error_count")) > 0 or _status_is_failed(status):
        return "failed"
    if _status_is_blocked(status):
        return "blocked"
    if summary.get("commit_created") is True or summary.get("review_opened") is True:
        return "executed"
    return "unknown"
```

Supporting declaration: `tools/idea_maturity_metrics_report.py::import@3`

```python
from __future__ import annotations
```

Supporting declaration: `tools/idea_maturity_metrics_report.py::import@5`

```python
import argparse
```

Supporting declaration: `tools/idea_maturity_metrics_report.py::import@6`

```python
import json
```

Supporting declaration: `tools/idea_maturity_metrics_report.py::import@7`

```python
import re
```

Supporting declaration: `tools/idea_maturity_metrics_report.py::import@8`

```python
import sys
```

Supporting declaration: `tools/idea_maturity_metrics_report.py::import@9`

```python
from collections import Counter
```

Supporting declaration: `tools/idea_maturity_metrics_report.py::import@10`

```python
from datetime import datetime, timezone
```

Supporting declaration: `tools/idea_maturity_metrics_report.py::import@11`

```python
from pathlib import Path
```

Supporting declaration: `tools/idea_maturity_metrics_report.py::import@12`

```python
from typing import Any
```

Supporting declaration: `tools/idea_maturity_metrics_report.py::_dict`

```python
def _dict(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}
```

Supporting declaration: `tools/idea_maturity_metrics_report.py::_text`

```python
def _text(value: Any, default: str = "") -> str:
    return value.strip() if isinstance(value, str) and value.strip() else default
```

Supporting declaration: `tools/idea_maturity_metrics_report.py::_int`

```python
def _int(value: Any, default: int = 0) -> int:
    if isinstance(value, bool):
        return default
    try:
        return int(value)
    except (TypeError, ValueError):
        return default
```

Supporting declaration: `tools/idea_maturity_metrics_report.py::_summary`

```python
def _summary(artifacts: dict[str, dict[str, Any]], key: str) -> dict[str, Any]:
    return _dict(_dict(artifacts.get(key)).get("summary"))
```

Opportunity: ______  Concern kind: ______

Evidence / missing context: ______

## sg-012

[Pinned source](https://github.com/0al-spec/SpecGraph/blob/425078cc74e1c2cccbff259b5505b1b958b8e904/tools/idea_maturity_promotion_execution_spec.py#L15-L71)

```python
_SPEC = FirstMatch.with_fallback(
    (
        (
            PredicateSpec(
                lambda c: (
                    not c.artifact("promotion_execution")
                    and promotion_request_state(c) == "requested"
                ),
                name="promotion_execution.not_available_after_request",
            ),
            "not_available",
        ),
        (
            PredicateSpec(
                lambda c: (
                    c.artifact("promotion_execution").get("dry_run") is True
                    or _status(c) == "dry_run"
                ),
                name="promotion_execution.dry_run",
            ),
            "dry_run",
        ),
        (
            PredicateSpec(
                lambda c: (
                    c.integer(c.summary("promotion_execution").get("error_count")) > 0
                    or c.is_failed(_status(c))
                ),
                name="promotion_execution.failed",
            ),
            "failed",
        ),
        (
            PredicateSpec(lambda c: c.is_blocked(_status(c)), name="promotion_execution.blocked"),
            "blocked",
        ),
        (
            PredicateSpec(
                lambda c: (
                    c.summary("promotion_execution").get("commit_created") is True
                    or c.summary("promotion_execution").get("review_opened") is True
                ),
                name="promotion_execution.executed",
            ),
            "executed",
        ),
        (
            PredicateSpec(
                lambda c: bool(c.artifact("promotion_execution")),
                name="promotion_execution.unknown",
            ),
            "unknown",
        ),
    ),
    "not_reached",
    name="promotion_execution_state",
)
```

Supporting declaration: `tools/idea_maturity_promotion_execution_spec.py::import@3`

```python
from specification_core import FirstMatch, PredicateSpec, TraceRecorder
```

Supporting declaration: `tools/idea_maturity_promotion_execution_spec.py::import@5`

```python
from idea_maturity_lifecycle_context import LifecycleStateContext, decide
```

Supporting declaration: `tools/idea_maturity_promotion_execution_spec.py::import@6`

```python
from idea_maturity_promotion_request_spec import promotion_request_state
```

Supporting declaration: `tools/idea_maturity_lifecycle_context.py::LifecycleStateContext`

```python
@dataclass(frozen=True)
class LifecycleStateContext:
    artifacts: dict[str, dict[str, Any]]

    def artifact(self, key: str) -> dict[str, Any]:
        return _dict(self.artifacts.get(key))

    def has_content(self, key: str) -> bool:
        return bool(self.artifacts.get(key))

    def summary(self, key: str) -> dict[str, Any]:
        return _dict(self.artifact(key).get("summary"))

    @staticmethod
    def mapping(value: Any) -> dict[str, Any]:
        return _dict(value)

    @staticmethod
    def text(value: Any, default: str = "") -> str:
        return _text(value, default)

    @staticmethod
    def integer(value: Any, default: int = 0) -> int:
        return _int(value, default)

    @staticmethod
    def is_failed(status: str) -> bool:
        return _status_is_failed(status)

    @staticmethod
    def is_blocked(status: str) -> bool:
        return _status_is_blocked(status)
```

Supporting declaration: `tools/idea_maturity_promotion_execution_spec.py::_status`

```python
def _status(c):
    return c.text(c.summary("promotion_execution").get("status")) or c.text(
        c.artifact("promotion_execution").get("status")
    )
```

Supporting declaration: `tools/idea_maturity_lifecycle_context.py::_dict`

```python
def _dict(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}
```

Supporting declaration: `tools/idea_maturity_lifecycle_context.py::_text`

```python
def _text(value: Any, default: str = "") -> str:
    return value.strip() if isinstance(value, str) and value.strip() else default
```

Supporting declaration: `tools/idea_maturity_lifecycle_context.py::_int`

```python
def _int(value: Any, default: int = 0) -> int:
    if isinstance(value, bool):
        return default
    try:
        return int(value)
    except (TypeError, ValueError):
        return default
```

Supporting declaration: `tools/idea_maturity_lifecycle_context.py::_summary`

```python
def _summary(artifacts: dict[str, dict[str, Any]], key: str) -> dict[str, Any]:
    return _dict(_dict(artifacts.get(key)).get("summary"))
```

Opportunity: ______  Concern kind: ______

Evidence / missing context: ______

## sg-013

[Pinned source](https://github.com/0al-spec/SpecGraph/blob/b7643721b11b5d4768bc966abab7dddd1092a5bd/tools/idea_maturity_metrics_report.py#L1570-L1595)

```python
def _review_status(artifacts: dict[str, dict[str, Any]]) -> str:
    review = _dict(artifacts.get("review_status"))
    if not review:
        return (
            "not_reached"
            if _promotion_execution_state(artifacts) == "not_reached"
            else "not_available"
        )
    review_state = _text(review.get("review_state"))
    if review.get("review_probe_only") is True and review_state == "merged":
        return "unknown"
    if review_state in {"open", "merged"}:
        return review_state
    if review_state == "closed":
        return "blocked"
    summary = _summary(artifacts, "review_status")
    status = _text(summary.get("review_status")) or _text(summary.get("status"))
    if status in {"open", "merged", "blocked", "unknown"}:
        return status
    if "merged" in status:
        return "merged"
    if "open" in status:
        return "open"
    if "blocked" in status or "failed" in status:
        return "blocked"
    return "unknown"
```

Supporting declaration: `tools/idea_maturity_metrics_report.py::import@3`

```python
from __future__ import annotations
```

Supporting declaration: `tools/idea_maturity_metrics_report.py::import@5`

```python
import argparse
```

Supporting declaration: `tools/idea_maturity_metrics_report.py::import@6`

```python
import json
```

Supporting declaration: `tools/idea_maturity_metrics_report.py::import@7`

```python
import re
```

Supporting declaration: `tools/idea_maturity_metrics_report.py::import@8`

```python
import sys
```

Supporting declaration: `tools/idea_maturity_metrics_report.py::import@9`

```python
from collections import Counter
```

Supporting declaration: `tools/idea_maturity_metrics_report.py::import@10`

```python
from datetime import datetime, timezone
```

Supporting declaration: `tools/idea_maturity_metrics_report.py::import@11`

```python
from pathlib import Path
```

Supporting declaration: `tools/idea_maturity_metrics_report.py::import@12`

```python
from typing import Any
```

Supporting declaration: `tools/idea_maturity_metrics_report.py::_dict`

```python
def _dict(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}
```

Supporting declaration: `tools/idea_maturity_metrics_report.py::_text`

```python
def _text(value: Any, default: str = "") -> str:
    return value.strip() if isinstance(value, str) and value.strip() else default
```

Supporting declaration: `tools/idea_maturity_metrics_report.py::_int`

```python
def _int(value: Any, default: int = 0) -> int:
    if isinstance(value, bool):
        return default
    try:
        return int(value)
    except (TypeError, ValueError):
        return default
```

Supporting declaration: `tools/idea_maturity_metrics_report.py::_summary`

```python
def _summary(artifacts: dict[str, dict[str, Any]], key: str) -> dict[str, Any]:
    return _dict(_dict(artifacts.get(key)).get("summary"))
```

Opportunity: ______  Concern kind: ______

Evidence / missing context: ______

## sg-014

[Pinned source](https://github.com/0al-spec/SpecGraph/blob/425078cc74e1c2cccbff259b5505b1b958b8e904/tools/idea_maturity_review_spec.py#L18-L73)

```python
_SPEC = FirstMatch.with_fallback(
    (
        (
            PredicateSpec(
                lambda c: (
                    not c.artifact("review_status")
                    and promotion_execution_state(c) == "not_reached"
                ),
                name="review.not_reached",
            ),
            "not_reached",
        ),
        (
            PredicateSpec(lambda c: not c.artifact("review_status"), name="review.not_available"),
            "not_available",
        ),
        (
            PredicateSpec(
                lambda c: (
                    c.artifact("review_status").get("review_probe_only") is True
                    and _artifact_state(c) == "merged"
                ),
                name="review.probe_merged_unknown",
            ),
            "unknown",
        ),
        (
            PredicateSpec(
                lambda c: _artifact_state(c) in {"open", "merged"}, name="review.canonical_state"
            ),
            "__canonical__",
        ),
        (PredicateSpec(lambda c: _artifact_state(c) == "closed", name="review.closed"), "blocked"),
        (
            PredicateSpec(
                lambda c: _summary_status(c) in {"open", "merged", "blocked", "unknown"},
                name="review.summary_status",
            ),
            "__summary__",
        ),
        (
            PredicateSpec(lambda c: "merged" in _summary_status(c), name="review.merged_text"),
            "merged",
        ),
        (PredicateSpec(lambda c: "open" in _summary_status(c), name="review.open_text"), "open"),
        (
            PredicateSpec(
                lambda c: "blocked" in _summary_status(c) or "failed" in _summary_status(c),
                name="review.blocked_text",
            ),
            "blocked",
        ),
    ),
    "unknown",
    name="review_status",
)
```

Supporting declaration: `tools/idea_maturity_review_spec.py::import@3`

```python
from specification_core import FirstMatch, PredicateSpec, TraceRecorder
```

Supporting declaration: `tools/idea_maturity_review_spec.py::import@5`

```python
from idea_maturity_lifecycle_context import LifecycleStateContext, decide
```

Supporting declaration: `tools/idea_maturity_review_spec.py::import@6`

```python
from idea_maturity_promotion_execution_spec import promotion_execution_state
```

Supporting declaration: `tools/idea_maturity_lifecycle_context.py::LifecycleStateContext`

```python
@dataclass(frozen=True)
class LifecycleStateContext:
    artifacts: dict[str, dict[str, Any]]

    def artifact(self, key: str) -> dict[str, Any]:
        return _dict(self.artifacts.get(key))

    def has_content(self, key: str) -> bool:
        return bool(self.artifacts.get(key))

    def summary(self, key: str) -> dict[str, Any]:
        return _dict(self.artifact(key).get("summary"))

    @staticmethod
    def mapping(value: Any) -> dict[str, Any]:
        return _dict(value)

    @staticmethod
    def text(value: Any, default: str = "") -> str:
        return _text(value, default)

    @staticmethod
    def integer(value: Any, default: int = 0) -> int:
        return _int(value, default)

    @staticmethod
    def is_failed(status: str) -> bool:
        return _status_is_failed(status)

    @staticmethod
    def is_blocked(status: str) -> bool:
        return _status_is_blocked(status)
```

Supporting declaration: `tools/idea_maturity_lifecycle_context.py::_dict`

```python
def _dict(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}
```

Supporting declaration: `tools/idea_maturity_lifecycle_context.py::_text`

```python
def _text(value: Any, default: str = "") -> str:
    return value.strip() if isinstance(value, str) and value.strip() else default
```

Supporting declaration: `tools/idea_maturity_lifecycle_context.py::_int`

```python
def _int(value: Any, default: int = 0) -> int:
    if isinstance(value, bool):
        return default
    try:
        return int(value)
    except (TypeError, ValueError):
        return default
```

Supporting declaration: `tools/idea_maturity_lifecycle_context.py::_summary`

```python
def _summary(artifacts: dict[str, dict[str, Any]], key: str) -> dict[str, Any]:
    return _dict(_dict(artifacts.get(key)).get("summary"))
```

Opportunity: ______  Concern kind: ______

Evidence / missing context: ______

## sg-015

[Pinned source](https://github.com/0al-spec/SpecGraph/blob/b7643721b11b5d4768bc966abab7dddd1092a5bd/tools/idea_maturity_metrics_report.py#L1620-L1636)

```python
def _read_model_publication_state(artifacts: dict[str, dict[str, Any]]) -> str:
    if _dict(artifacts.get("review_status")).get("review_probe_only") is True:
        return "not_reached"
    publication = _dict(artifacts.get("read_model_publication"))
    if not publication:
        return "not_reached" if _review_status(artifacts) != "merged" else "not_available"
    summary = _summary(artifacts, "read_model_publication")
    status = _text(summary.get("status"))
    if status == "published" or summary.get("published") is True:
        return "published"
    if publication.get("dry_run") is True or status == "dry_run":
        return "dry_run"
    if _int(summary.get("error_count")) > 0 or "failed" in status:
        return "failed"
    if "blocked" in status:
        return "blocked"
    return "unknown"
```

Supporting declaration: `tools/idea_maturity_metrics_report.py::import@3`

```python
from __future__ import annotations
```

Supporting declaration: `tools/idea_maturity_metrics_report.py::import@5`

```python
import argparse
```

Supporting declaration: `tools/idea_maturity_metrics_report.py::import@6`

```python
import json
```

Supporting declaration: `tools/idea_maturity_metrics_report.py::import@7`

```python
import re
```

Supporting declaration: `tools/idea_maturity_metrics_report.py::import@8`

```python
import sys
```

Supporting declaration: `tools/idea_maturity_metrics_report.py::import@9`

```python
from collections import Counter
```

Supporting declaration: `tools/idea_maturity_metrics_report.py::import@10`

```python
from datetime import datetime, timezone
```

Supporting declaration: `tools/idea_maturity_metrics_report.py::import@11`

```python
from pathlib import Path
```

Supporting declaration: `tools/idea_maturity_metrics_report.py::import@12`

```python
from typing import Any
```

Supporting declaration: `tools/idea_maturity_metrics_report.py::_dict`

```python
def _dict(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}
```

Supporting declaration: `tools/idea_maturity_metrics_report.py::_text`

```python
def _text(value: Any, default: str = "") -> str:
    return value.strip() if isinstance(value, str) and value.strip() else default
```

Supporting declaration: `tools/idea_maturity_metrics_report.py::_int`

```python
def _int(value: Any, default: int = 0) -> int:
    if isinstance(value, bool):
        return default
    try:
        return int(value)
    except (TypeError, ValueError):
        return default
```

Supporting declaration: `tools/idea_maturity_metrics_report.py::_summary`

```python
def _summary(artifacts: dict[str, dict[str, Any]], key: str) -> dict[str, Any]:
    return _dict(_dict(artifacts.get(key)).get("summary"))
```

Supporting declaration: `tools/idea_maturity_metrics_report.py::_candidate_approval_intent_state`

```python
def _candidate_approval_intent_state(artifacts: dict[str, dict[str, Any]]) -> str:
    if "approval_intent" not in artifacts:
        return "not_reached" if _candidate_approval_state(artifacts) != "ready" else "not_available"
    summary = _summary(artifacts, "approval_intent")
    status = _text(summary.get("status"))
    if _int(summary.get("active_intent_count")) > 0 or "requested" in status:
        return "requested"
    if "blocked" in status:
        return "blocked"
    return "unknown"
```

Supporting declaration: `tools/idea_maturity_metrics_report.py::_candidate_approval_decision_state`

```python
def _candidate_approval_decision_state(artifacts: dict[str, dict[str, Any]]) -> str:
    decision = _dict(artifacts.get("candidate_approval_decision"))
    if decision:
        summary = _summary(artifacts, "candidate_approval_decision")
        readiness = _dict(decision.get("readiness"))
        decision_payload = _dict(decision.get("decision"))
        state = _text(summary.get("effective_state")) or _text(decision_payload.get("state"))
        status = (
            _text(summary.get("status"))
            or _text(readiness.get("review_state"))
            or _text(decision.get("status"))
        )
        if state == "approved" and readiness.get("ready") is True:
            return "materialized"
        if decision.get("dry_run") is True or status == "dry_run":
            return "dry_run"
        if _status_is_failed(status):
            return "failed"
        if _status_is_blocked(status) or state in {"rejected", "needs_context", "superseded"}:
            return "blocked"
        return "unknown"
    execution = _dict(artifacts.get("approval_execution"))
    if execution:
        summary = _summary(artifacts, "approval_execution")
        status = _text(summary.get("status")) or _text(execution.get("status"))
        if (
            _dict(execution.get("candidate_approval_decision_ref"))
            or summary.get("decision_written") is True
        ):
            return "materialized"
        if execution.get("dry_run") is True:
            return "dry_run"
        if "failed" in status or "blocked" in status:
            return "failed" if "failed" in status else "blocked"
        return "unknown"
    if _candidate_approval_intent_state(artifacts) in {"requested", "ready"}:
        return "not_available"
    return "not_reached"
```

Supporting declaration: `tools/idea_maturity_metrics_report.py::_promotion_request_state`

```python
def _promotion_request_state(artifacts: dict[str, dict[str, Any]]) -> str:
    request = _dict(artifacts.get("promotion_request"))
    if not request:
        return (
            "not_available"
            if _candidate_approval_decision_state(artifacts) == "materialized"
            else "not_reached"
        )
    summary = _summary(artifacts, "promotion_request")
    if request.get("ok") is True or summary.get("promotion_ready") is True:
        return "requested"
    if _int(summary.get("error_count")) > 0:
        return "blocked"
    return "unknown"
```

Supporting declaration: `tools/idea_maturity_metrics_report.py::_promotion_execution_state`

```python
def _promotion_execution_state(artifacts: dict[str, dict[str, Any]]) -> str:
    execution = _dict(artifacts.get("promotion_execution"))
    if not execution:
        return (
            "not_available" if _promotion_request_state(artifacts) == "requested" else "not_reached"
        )
    summary = _summary(artifacts, "promotion_execution")
    status = _text(summary.get("status")) or _text(execution.get("status"))
    if execution.get("dry_run") is True or status == "dry_run":
        return "dry_run"
    if _int(summary.get("error_count")) > 0 or _status_is_failed(status):
        return "failed"
    if _status_is_blocked(status):
        return "blocked"
    if summary.get("commit_created") is True or summary.get("review_opened") is True:
        return "executed"
    return "unknown"
```

Supporting declaration: `tools/idea_maturity_metrics_report.py::_review_status`

```python
def _review_status(artifacts: dict[str, dict[str, Any]]) -> str:
    review = _dict(artifacts.get("review_status"))
    if not review:
        return (
            "not_reached"
            if _promotion_execution_state(artifacts) == "not_reached"
            else "not_available"
        )
    review_state = _text(review.get("review_state"))
    if review.get("review_probe_only") is True and review_state == "merged":
        return "unknown"
    if review_state in {"open", "merged"}:
        return review_state
    if review_state == "closed":
        return "blocked"
    summary = _summary(artifacts, "review_status")
    status = _text(summary.get("review_status")) or _text(summary.get("status"))
    if status in {"open", "merged", "blocked", "unknown"}:
        return status
    if "merged" in status:
        return "merged"
    if "open" in status:
        return "open"
    if "blocked" in status or "failed" in status:
        return "blocked"
    return "unknown"
```

Opportunity: ______  Concern kind: ______

Evidence / missing context: ______

## sg-016

[Pinned source](https://github.com/0al-spec/SpecGraph/blob/425078cc74e1c2cccbff259b5505b1b958b8e904/tools/idea_maturity_read_model_publication_spec.py#L13-L70)

```python
_SPEC = FirstMatch.with_fallback(
    (
        (
            PredicateSpec(
                lambda c: c.artifact("review_status").get("review_probe_only") is True,
                name="publication.probe_only",
            ),
            "not_reached",
        ),
        (
            PredicateSpec(
                lambda c: not c.artifact("read_model_publication") and review_status(c) != "merged",
                name="publication.not_reached",
            ),
            "not_reached",
        ),
        (
            PredicateSpec(
                lambda c: not c.artifact("read_model_publication") and review_status(c) == "merged",
                name="publication.not_available",
            ),
            "not_available",
        ),
        (
            PredicateSpec(
                lambda c: (
                    _status(c) == "published"
                    or c.summary("read_model_publication").get("published") is True
                ),
                name="publication.published",
            ),
            "published",
        ),
        (
            PredicateSpec(
                lambda c: (
                    c.artifact("read_model_publication").get("dry_run") is True
                    or _status(c) == "dry_run"
                ),
                name="publication.dry_run",
            ),
            "dry_run",
        ),
        (
            PredicateSpec(
                lambda c: (
                    c.integer(c.summary("read_model_publication").get("error_count")) > 0
                    or "failed" in _status(c)
                ),
                name="publication.failed",
            ),
            "failed",
        ),
        (PredicateSpec(lambda c: "blocked" in _status(c), name="publication.blocked"), "blocked"),
    ),
    "unknown",
    name="read_model_publication_state",
)
```

Supporting declaration: `tools/idea_maturity_read_model_publication_spec.py::import@3`

```python
from specification_core import FirstMatch, PredicateSpec, TraceRecorder
```

Supporting declaration: `tools/idea_maturity_read_model_publication_spec.py::import@5`

```python
from idea_maturity_lifecycle_context import LifecycleStateContext, decide
```

Supporting declaration: `tools/idea_maturity_read_model_publication_spec.py::import@6`

```python
from idea_maturity_review_spec import review_status
```

Supporting declaration: `tools/idea_maturity_lifecycle_context.py::LifecycleStateContext`

```python
@dataclass(frozen=True)
class LifecycleStateContext:
    artifacts: dict[str, dict[str, Any]]

    def artifact(self, key: str) -> dict[str, Any]:
        return _dict(self.artifacts.get(key))

    def has_content(self, key: str) -> bool:
        return bool(self.artifacts.get(key))

    def summary(self, key: str) -> dict[str, Any]:
        return _dict(self.artifact(key).get("summary"))

    @staticmethod
    def mapping(value: Any) -> dict[str, Any]:
        return _dict(value)

    @staticmethod
    def text(value: Any, default: str = "") -> str:
        return _text(value, default)

    @staticmethod
    def integer(value: Any, default: int = 0) -> int:
        return _int(value, default)

    @staticmethod
    def is_failed(status: str) -> bool:
        return _status_is_failed(status)

    @staticmethod
    def is_blocked(status: str) -> bool:
        return _status_is_blocked(status)
```

Supporting declaration: `tools/idea_maturity_read_model_publication_spec.py::_status`

```python
def _status(c):
    return c.text(c.summary("read_model_publication").get("status"))
```

Supporting declaration: `tools/idea_maturity_lifecycle_context.py::_dict`

```python
def _dict(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}
```

Supporting declaration: `tools/idea_maturity_lifecycle_context.py::_text`

```python
def _text(value: Any, default: str = "") -> str:
    return value.strip() if isinstance(value, str) and value.strip() else default
```

Supporting declaration: `tools/idea_maturity_lifecycle_context.py::_int`

```python
def _int(value: Any, default: int = 0) -> int:
    if isinstance(value, bool):
        return default
    try:
        return int(value)
    except (TypeError, ValueError):
        return default
```

Supporting declaration: `tools/idea_maturity_lifecycle_context.py::_summary`

```python
def _summary(artifacts: dict[str, dict[str, Any]], key: str) -> dict[str, Any]:
    return _dict(_dict(artifacts.get(key)).get("summary"))
```

Opportunity: ______  Concern kind: ______

Evidence / missing context: ______

## sg-017

[Pinned source](https://github.com/0al-spec/SpecGraph/blob/3ad8836b9e14c501bdfb5aeec11bdfdd65974eea/tools/idea_to_spec_promotion_gate.py#L189-L213)

```python
    if _pre_sib_original_blocked(pre_sib, materialization):
        blocked_by = _text_list(_dict(pre_sib.get("readiness")).get("blocked_by"))
        findings.append(
            _finding(
                finding_id="pre_sib_not_ready_without_repair_preview",
                severity="review_required",
                message=(
                    "Original pre-SIB report is not ready and materialization did not "
                    "use a repair loop preview."
                ),
                evidence={"blocked_by": blocked_by},
            )
        )
    elif not _readiness_ready(pre_sib):
        blocked_by = _text_list(_dict(pre_sib.get("readiness")).get("blocked_by"))
        warnings.append(
            _finding(
                finding_id="pre_sib_findings_repaired_by_preview",
                severity="warning",
                message=(
                    "Original pre-SIB findings are allowed only because repair preview was used."
                ),
                evidence={"blocked_by": blocked_by},
            )
        )
```

Supporting declaration: `tools/idea_to_spec_promotion_gate.py::import@3`

```python
from __future__ import annotations
```

Supporting declaration: `tools/idea_to_spec_promotion_gate.py::import@5`

```python
import argparse
```

Supporting declaration: `tools/idea_to_spec_promotion_gate.py::import@6`

```python
import json
```

Supporting declaration: `tools/idea_to_spec_promotion_gate.py::import@7`

```python
from datetime import datetime, timezone
```

Supporting declaration: `tools/idea_to_spec_promotion_gate.py::import@8`

```python
from pathlib import Path
```

Supporting declaration: `tools/idea_to_spec_promotion_gate.py::import@9`

```python
from typing import Any
```

Supporting declaration: `tools/idea_to_spec_promotion_gate.py::_pre_sib_original_blocked`

```python
def _pre_sib_original_blocked(pre_sib: dict[str, Any], materialization: dict[str, Any]) -> bool:
    if _readiness_ready(pre_sib):
        return False
    return _text(materialization.get("materialization_source")) != "repair_loop_preview"
```

Supporting declaration: `tools/idea_to_spec_promotion_gate.py::_readiness_ready`

```python
def _readiness_ready(artifact: dict[str, Any]) -> bool:
    return _dict(artifact.get("readiness")).get("ready") is True
```

Supporting declaration: `tools/idea_to_spec_promotion_gate.py::_dict`

```python
def _dict(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}
```

Supporting declaration: `tools/idea_to_spec_promotion_gate.py::_text`

```python
def _text(value: Any, default: str = "") -> str:
    return value.strip() if isinstance(value, str) and value.strip() else default
```

Supporting declaration: `tools/idea_to_spec_promotion_gate.py::_text_list`

```python
def _text_list(value: Any) -> list[str]:
    return [item.strip() for item in _list(value) if isinstance(item, str) and item.strip()]
```

Supporting declaration: `tools/idea_to_spec_promotion_gate.py::_finding`

```python
def _finding(
    *,
    finding_id: str,
    severity: str,
    message: str,
    evidence: dict[str, Any] | None = None,
) -> dict[str, Any]:
    return {
        "finding_id": finding_id,
        "severity": severity,
        "message": message,
        "source": "idea_to_spec_promotion_gate",
        "evidence": evidence or {},
    }
```

Opportunity: ______  Concern kind: ______

Evidence / missing context: ______

## sg-018

[Pinned source](https://github.com/0al-spec/SpecGraph/blob/50ae667d1fc088c0a3e5f72fdd306feaa4be0b0a/tools/idea_to_spec_promotion_gate.py#L172-L200)

```python
_PRE_SIB_STATE_DECISION = FirstMatch(
    (
        (
            PredicateSpec(lambda context: context.pre_sib_ready, name="pre_sib.ready"),
            _PreSibState.READY,
        ),
        (
            PredicateSpec(
                lambda context: (
                    not context.pre_sib_ready
                    and context.materialization_source != "repair_loop_preview"
                ),
                name="pre_sib.blocked",
            ),
            _PreSibState.BLOCKED,
        ),
        (
            PredicateSpec(
                lambda context: (
                    not context.pre_sib_ready
                    and context.materialization_source == "repair_loop_preview"
                ),
                name="pre_sib.repaired_preview",
            ),
            _PreSibState.REPAIRED_PREVIEW,
        ),
    ),
    name="pre_sib_state",
)
```

Supporting declaration: `tools/idea_to_spec_promotion_gate.py::import@3`

```python
from __future__ import annotations
```

Supporting declaration: `tools/idea_to_spec_promotion_gate.py::import@5`

```python
import argparse
```

Supporting declaration: `tools/idea_to_spec_promotion_gate.py::import@6`

```python
import json
```

Supporting declaration: `tools/idea_to_spec_promotion_gate.py::import@7`

```python
import sys
```

Supporting declaration: `tools/idea_to_spec_promotion_gate.py::import@8`

```python
from dataclasses import dataclass
```

Supporting declaration: `tools/idea_to_spec_promotion_gate.py::import@9`

```python
from datetime import datetime, timezone
```

Supporting declaration: `tools/idea_to_spec_promotion_gate.py::import@10`

```python
from enum import Enum
```

Supporting declaration: `tools/idea_to_spec_promotion_gate.py::import@11`

```python
from pathlib import Path
```

Supporting declaration: `tools/idea_to_spec_promotion_gate.py::import@12`

```python
from typing import Any
```

Supporting declaration: `tools/idea_to_spec_promotion_gate.py::import@14`

```python
from specification_core import FirstMatch, PredicateSpec, TraceRecorder
```

Supporting declaration: `tools/idea_to_spec_promotion_gate.py::_PreSibState`

```python
class _PreSibState(str, Enum):
    READY = "ready"
    BLOCKED = "blocked"
    REPAIRED_PREVIEW = "repaired_preview"
```

Supporting declaration: `tools/idea_to_spec_promotion_gate.py::_PreSibDecisionContext`

```python
@dataclass(frozen=True)
class _PreSibDecisionContext:
    pre_sib_ready: bool
    materialization_source: str
```

Opportunity: ______  Concern kind: ______

Evidence / missing context: ______

## sg-019

[Pinned source](https://github.com/0al-spec/SpecGraph/blob/99b69a9eda02f44b336f7460244abbe9016af18a/tools/candidate_repair_loop.py#L335-L378)

```python
def _repair_acceptance_criteria(candidate_graph: dict[str, Any]) -> list[dict[str, Any]]:
    actions: list[dict[str, Any]] = []
    for node in _nodes(candidate_graph):
        node_id = _text(node.get("id"))
        existing_ac = {
            _text(ac.get("id"))
            for ac in _list(node.get("acceptance_criteria"))
            if isinstance(ac, dict)
        }
        for requirement in _list(node.get("requirements")):
            if not isinstance(requirement, dict):
                continue
            refs = _text_list(requirement.get("acceptance_criteria_refs"))
            if refs and all(ref in existing_ac for ref in refs):
                continue
            req_id = _text(requirement.get("id"), "requirement")
            ac_id = f"ac.repair.{_slug(req_id, 'requirement')}"
            actions.append(
                _action(
                    action_id=f"repair.add-ac.{_slug(req_id, 'requirement')}",
                    kind="add_acceptance_criterion",
                    status="applied_to_preview",
                    target_ref=req_id,
                    source_findings=["pre_sib_acceptance_criteria_gap"],
                    rationale=(
                        "Add a reviewable placeholder acceptance criterion for "
                        "uncovered requirement."
                    ),
                    operation={
                        "op": "add_acceptance_criterion",
                        "node_id": node_id,
                        "requirement_id": req_id,
                        "value": {
                            "id": ac_id,
                            "statement": (
                                "Review criterion needed for requirement: "
                                f"{_text(requirement.get('statement'), req_id)}"
                            ),
                            "repair_generated": True,
                        },
                    },
                )
            )
    return actions
```

Supporting declaration: `tools/candidate_repair_loop.py::import@3`

```python
from __future__ import annotations
```

Supporting declaration: `tools/candidate_repair_loop.py::import@5`

```python
import argparse
```

Supporting declaration: `tools/candidate_repair_loop.py::import@6`

```python
import copy
```

Supporting declaration: `tools/candidate_repair_loop.py::import@7`

```python
import json
```

Supporting declaration: `tools/candidate_repair_loop.py::import@8`

```python
import re
```

Supporting declaration: `tools/candidate_repair_loop.py::import@9`

```python
from collections.abc import Callable
```

Supporting declaration: `tools/candidate_repair_loop.py::import@10`

```python
from dataclasses import dataclass
```

Supporting declaration: `tools/candidate_repair_loop.py::import@11`

```python
from datetime import datetime, timezone
```

Supporting declaration: `tools/candidate_repair_loop.py::import@12`

```python
from pathlib import Path
```

Supporting declaration: `tools/candidate_repair_loop.py::import@13`

```python
from typing import Any
```

Supporting declaration: `tools/candidate_repair_loop.py::import@15`

```python
from specification_core import FirstMatch, PredicateSpec
```

Supporting declaration: `tools/candidate_repair_loop.py::_dict`

```python
def _dict(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}
```

Supporting declaration: `tools/candidate_repair_loop.py::_list`

```python
def _list(value: Any) -> list[Any]:
    return value if isinstance(value, list) else []
```

Supporting declaration: `tools/candidate_repair_loop.py::_text`

```python
def _text(value: Any, default: str = "") -> str:
    return value.strip() if isinstance(value, str) and value.strip() else default
```

Supporting declaration: `tools/candidate_repair_loop.py::_text_list`

```python
def _text_list(value: Any) -> list[str]:
    return [item.strip() for item in _list(value) if isinstance(item, str) and item.strip()]
```

Opportunity: ______  Concern kind: ______

Evidence / missing context: ______

## sg-020

[Pinned source](https://github.com/0al-spec/SpecGraph/blob/cd5dd5e2bc30da59eb936372c8cd6e8d1dcdd4ae/tools/candidate_repair_loop.py#L83-L108)

```python
_ACCEPTANCE_CRITERION_DECISION = FirstMatch.with_fallback(
    (
        (
            PredicateSpec(
                lambda context: not isinstance(context.requirement, dict),
                name="acceptance_criterion.invalid_requirement",
            ),
            _AcceptanceCriterionDisposition.IGNORE,
        ),
        (
            PredicateSpec(
                lambda context: (
                    bool(_text_list(context.requirement.get("acceptance_criteria_refs")))
                    and all(
                        ref in context.existing_acceptance_criteria
                        for ref in _text_list(context.requirement.get("acceptance_criteria_refs"))
                    )
                ),
                name="acceptance_criterion.already_covered",
            ),
            _AcceptanceCriterionDisposition.IGNORE,
        ),
    ),
    _AcceptanceCriterionDisposition.ADD_PLACEHOLDER,
    name="acceptance_criterion_repair",
)
```

Supporting declaration: `tools/candidate_repair_loop.py::import@3`

```python
from __future__ import annotations
```

Supporting declaration: `tools/candidate_repair_loop.py::import@5`

```python
import argparse
```

Supporting declaration: `tools/candidate_repair_loop.py::import@6`

```python
import copy
```

Supporting declaration: `tools/candidate_repair_loop.py::import@7`

```python
import json
```

Supporting declaration: `tools/candidate_repair_loop.py::import@8`

```python
import re
```

Supporting declaration: `tools/candidate_repair_loop.py::import@9`

```python
from collections.abc import Callable
```

Supporting declaration: `tools/candidate_repair_loop.py::import@10`

```python
from dataclasses import dataclass
```

Supporting declaration: `tools/candidate_repair_loop.py::import@11`

```python
from datetime import datetime, timezone
```

Supporting declaration: `tools/candidate_repair_loop.py::import@12`

```python
from enum import Enum
```

Supporting declaration: `tools/candidate_repair_loop.py::import@13`

```python
from pathlib import Path
```

Supporting declaration: `tools/candidate_repair_loop.py::import@14`

```python
from typing import Any
```

Supporting declaration: `tools/candidate_repair_loop.py::import@16`

```python
from specification_core import FirstMatch, PredicateSpec
```

Supporting declaration: `tools/candidate_repair_loop.py::_AcceptanceCriterionContext`

```python
@dataclass(frozen=True)
class _AcceptanceCriterionContext:
    node_id: str
    requirement: Any
    existing_acceptance_criteria: frozenset[str]
```

Supporting declaration: `tools/candidate_repair_loop.py::_AcceptanceCriterionDisposition`

```python
class _AcceptanceCriterionDisposition(Enum):
    IGNORE = "ignore"
    ADD_PLACEHOLDER = "add_placeholder"
```

Supporting declaration: `tools/candidate_repair_loop.py::_text_list`

```python
def _text_list(value: Any) -> list[str]:
    return [item.strip() for item in _list(value) if isinstance(item, str) and item.strip()]
```

Supporting declaration: `tools/candidate_repair_loop.py::_text`

```python
def _text(value: Any, default: str = "") -> str:
    return value.strip() if isinstance(value, str) and value.strip() else default
```

Opportunity: ______  Concern kind: ______

Evidence / missing context: ______

## sg-021

[Pinned source](https://github.com/0al-spec/SpecGraph/blob/cd5dd5e2bc30da59eb936372c8cd6e8d1dcdd4ae/tools/candidate_repair_loop.py#L452-L479)

```python
def _repair_unsupported_claims(candidate_graph: dict[str, Any]) -> list[dict[str, Any]]:
    actions: list[dict[str, Any]] = []
    for node in _nodes(candidate_graph):
        for claim in _list(node.get("claims")):
            if not isinstance(claim, dict):
                continue
            if not _is_strong_claim(claim):
                continue
            if (_claim_reliability(claim) or 0) > 2 or _text_list(claim.get("evidence_refs")):
                continue
            claim_id = _text(claim.get("id"), "claim")
            actions.append(
                _action(
                    action_id=f"repair.downgrade-claim.{_slug(claim_id, 'claim')}",
                    kind="downgrade_claim",
                    status="applied_to_preview",
                    target_ref=claim_id,
                    source_findings=["pre_sib_unsupported_strong_claims"],
                    rationale="Low-reliability strong claims without evidence stay hypotheses.",
                    operation={
                        "op": "replace_claim_type",
                        "node_id": _text(node.get("id")),
                        "claim_id": claim_id,
                        "value": "hypothesis",
                    },
                )
            )
    return actions
```

Supporting declaration: `tools/candidate_repair_loop.py::import@3`

```python
from __future__ import annotations
```

Supporting declaration: `tools/candidate_repair_loop.py::import@5`

```python
import argparse
```

Supporting declaration: `tools/candidate_repair_loop.py::import@6`

```python
import copy
```

Supporting declaration: `tools/candidate_repair_loop.py::import@7`

```python
import json
```

Supporting declaration: `tools/candidate_repair_loop.py::import@8`

```python
import re
```

Supporting declaration: `tools/candidate_repair_loop.py::import@9`

```python
from collections.abc import Callable
```

Supporting declaration: `tools/candidate_repair_loop.py::import@10`

```python
from dataclasses import dataclass
```

Supporting declaration: `tools/candidate_repair_loop.py::import@11`

```python
from datetime import datetime, timezone
```

Supporting declaration: `tools/candidate_repair_loop.py::import@12`

```python
from enum import Enum
```

Supporting declaration: `tools/candidate_repair_loop.py::import@13`

```python
from pathlib import Path
```

Supporting declaration: `tools/candidate_repair_loop.py::import@14`

```python
from typing import Any
```

Supporting declaration: `tools/candidate_repair_loop.py::import@16`

```python
from specification_core import FirstMatch, PredicateSpec
```

Supporting declaration: `tools/candidate_repair_loop.py::_is_strong_claim`

```python
def _is_strong_claim(claim: dict[str, Any]) -> bool:
    claim_type = _text(claim.get("type"), "claim")
    return claim_type in STRONG_CLAIM_TYPES or _text(claim.get("strength")) == "strong"
```

Supporting declaration: `tools/candidate_repair_loop.py::_claim_reliability`

```python
def _claim_reliability(claim: dict[str, Any]) -> int | None:
    value = _text(_dict(claim.get("calibration")).get("R"))
    if len(value) >= 2 and value[0] == "R" and value[1:].isdigit():
        return int(value[1:])
    return None
```

Supporting declaration: `tools/candidate_repair_loop.py::_dict`

```python
def _dict(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}
```

Supporting declaration: `tools/candidate_repair_loop.py::_list`

```python
def _list(value: Any) -> list[Any]:
    return value if isinstance(value, list) else []
```

Supporting declaration: `tools/candidate_repair_loop.py::_text`

```python
def _text(value: Any, default: str = "") -> str:
    return value.strip() if isinstance(value, str) and value.strip() else default
```

Supporting declaration: `tools/candidate_repair_loop.py::_text_list`

```python
def _text_list(value: Any) -> list[str]:
    return [item.strip() for item in _list(value) if isinstance(item, str) and item.strip()]
```

Opportunity: ______  Concern kind: ______

Evidence / missing context: ______

## sg-022

[Pinned source](https://github.com/0al-spec/SpecGraph/blob/710367a01881d34c1291e09b534925f8cd7f79ae/tools/candidate_repair_loop.py#L482-L511)

```python
_UNSUPPORTED_CLAIM_DECISION = FirstMatch.with_fallback(
    (
        (
            PredicateSpec(
                lambda context: not isinstance(context.claim, dict),
                name="claim.invalid",
            ),
            _UnsupportedClaimDisposition.IGNORE,
        ),
        (
            PredicateSpec(
                lambda context: not _is_strong_claim(context.claim),
                name="claim.not_strong",
            ),
            _UnsupportedClaimDisposition.IGNORE,
        ),
        (
            PredicateSpec(
                lambda context: (
                    (_claim_reliability(context.claim) or 0) > 2
                    or bool(_text_list(context.claim.get("evidence_refs")))
                ),
                name="claim.supported",
            ),
            _UnsupportedClaimDisposition.IGNORE,
        ),
    ),
    _UnsupportedClaimDisposition.DOWNGRADE,
    name="unsupported_claim_repair",
)
```

Supporting declaration: `tools/candidate_repair_loop.py::import@3`

```python
from __future__ import annotations
```

Supporting declaration: `tools/candidate_repair_loop.py::import@5`

```python
import argparse
```

Supporting declaration: `tools/candidate_repair_loop.py::import@6`

```python
import copy
```

Supporting declaration: `tools/candidate_repair_loop.py::import@7`

```python
import json
```

Supporting declaration: `tools/candidate_repair_loop.py::import@8`

```python
import re
```

Supporting declaration: `tools/candidate_repair_loop.py::import@9`

```python
from collections.abc import Callable
```

Supporting declaration: `tools/candidate_repair_loop.py::import@10`

```python
from dataclasses import dataclass
```

Supporting declaration: `tools/candidate_repair_loop.py::import@11`

```python
from datetime import datetime, timezone
```

Supporting declaration: `tools/candidate_repair_loop.py::import@12`

```python
from enum import Enum
```

Supporting declaration: `tools/candidate_repair_loop.py::import@13`

```python
from pathlib import Path
```

Supporting declaration: `tools/candidate_repair_loop.py::import@14`

```python
from typing import Any
```

Supporting declaration: `tools/candidate_repair_loop.py::import@16`

```python
from specification_core import FirstMatch, PredicateSpec
```

Supporting declaration: `tools/candidate_repair_loop.py::_UnsupportedClaimContext`

```python
@dataclass(frozen=True)
class _UnsupportedClaimContext:
    node_id: str
    claim: Any
```

Supporting declaration: `tools/candidate_repair_loop.py::_UnsupportedClaimDisposition`

```python
class _UnsupportedClaimDisposition(Enum):
    IGNORE = "ignore"
    DOWNGRADE = "downgrade"
```

Supporting declaration: `tools/candidate_repair_loop.py::_is_strong_claim`

```python
def _is_strong_claim(claim: dict[str, Any]) -> bool:
    claim_type = _text(claim.get("type"), "claim")
    return claim_type in STRONG_CLAIM_TYPES or _text(claim.get("strength")) == "strong"
```

Supporting declaration: `tools/candidate_repair_loop.py::_claim_reliability`

```python
def _claim_reliability(claim: dict[str, Any]) -> int | None:
    value = _text(_dict(claim.get("calibration")).get("R"))
    if len(value) >= 2 and value[0] == "R" and value[1:].isdigit():
        return int(value[1:])
    return None
```

Supporting declaration: `tools/candidate_repair_loop.py::_dict`

```python
def _dict(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}
```

Supporting declaration: `tools/candidate_repair_loop.py::_text`

```python
def _text(value: Any, default: str = "") -> str:
    return value.strip() if isinstance(value, str) and value.strip() else default
```

Supporting declaration: `tools/candidate_repair_loop.py::_text_list`

```python
def _text_list(value: Any) -> list[str]:
    return [item.strip() for item in _list(value) if isinstance(item, str) and item.strip()]
```

Opportunity: ______  Concern kind: ______

Evidence / missing context: ______

## sg-023

[Pinned source](https://github.com/0al-spec/SpecGraph/blob/81d74d540ffffbc6df752e6a1678574446da9197/tools/candidate_repair_loop.py#L472-L520)

```python
def _apply_preview_actions(
    candidate_graph: dict[str, Any],
    actions: list[dict[str, Any]],
    *,
    preview_source_ref: str,
) -> dict[str, Any]:
    preview = copy.deepcopy(candidate_graph)
    preview["source_ref"] = preview_source_ref
    preview["canonical_mutations_allowed"] = False
    preview["tracked_artifacts_written"] = False
    preview["repair_preview"] = {
        "generated_by": CONTRACT_REF,
        "applied_action_count": sum(
            1 for action in actions if action["status"] == "applied_to_preview"
        ),
    }
    for action in actions:
        if action["status"] != "applied_to_preview":
            continue
        operation = _dict(action.get("operation"))
        op = _text(operation.get("op"))
        if op == "append" and operation.get("path") == "/edges":
            preview.setdefault("edges", []).append(operation["value"])
        elif op == "add_acceptance_criterion":
            node = _node_by_id(preview, _text(operation.get("node_id")))
            if node is None:
                continue
            node.setdefault("acceptance_criteria", []).append(operation["value"])
            for requirement in _list(node.get("requirements")):
                if not isinstance(requirement, dict):
                    continue
                if _text(requirement.get("id")) == _text(operation.get("requirement_id")):
                    refs = _text_list(requirement.get("acceptance_criteria_refs"))
                    if operation["value"]["id"] not in refs:
                        refs.append(operation["value"]["id"])
                    requirement["acceptance_criteria_refs"] = refs
        elif op == "replace_claim_type":
            node = _node_by_id(preview, _text(operation.get("node_id")))
            if node is None:
                continue
            for claim in _list(node.get("claims")):
                if isinstance(claim, dict) and _text(claim.get("id")) == _text(
                    operation.get("claim_id")
                ):
                    claim["type"] = operation["value"]
                    if _text(claim.get("strength")) == "strong":
                        claim["strength"] = operation["value"]
                    claim["repair_generated_type_change"] = True
    return preview
```

Supporting declaration: `tools/candidate_repair_loop.py::import@3`

```python
from __future__ import annotations
```

Supporting declaration: `tools/candidate_repair_loop.py::import@5`

```python
import argparse
```

Supporting declaration: `tools/candidate_repair_loop.py::import@6`

```python
import copy
```

Supporting declaration: `tools/candidate_repair_loop.py::import@7`

```python
import json
```

Supporting declaration: `tools/candidate_repair_loop.py::import@8`

```python
import re
```

Supporting declaration: `tools/candidate_repair_loop.py::import@9`

```python
from datetime import datetime, timezone
```

Supporting declaration: `tools/candidate_repair_loop.py::import@10`

```python
from pathlib import Path
```

Supporting declaration: `tools/candidate_repair_loop.py::import@11`

```python
from typing import Any
```

Supporting declaration: `tools/candidate_repair_loop.py::_node_by_id`

```python
def _node_by_id(candidate_graph: dict[str, Any], node_id: str) -> dict[str, Any] | None:
    for node in _nodes(candidate_graph):
        if _text(node.get("id")) == node_id:
            return node
    return None
```

Supporting declaration: `tools/candidate_repair_loop.py::_dict`

```python
def _dict(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}
```

Supporting declaration: `tools/candidate_repair_loop.py::_list`

```python
def _list(value: Any) -> list[Any]:
    return value if isinstance(value, list) else []
```

Supporting declaration: `tools/candidate_repair_loop.py::_text`

```python
def _text(value: Any, default: str = "") -> str:
    return value.strip() if isinstance(value, str) and value.strip() else default
```

Opportunity: ______  Concern kind: ______

Evidence / missing context: ______

## sg-024

[Pinned source](https://github.com/0al-spec/SpecGraph/blob/90d26eeb2974b7af35e5295821897e2ebf8d0e70/tools/candidate_repair_loop.py#L519-L548)

```python
_PREVIEW_OPERATION_DECISION = FirstMatch.with_fallback(
    (
        (
            PredicateSpec(
                lambda context: (
                    context.operation.get("op") == "append"
                    and context.operation.get("path") == "/edges"
                ),
                name="preview.append_edge",
            ),
            _append_preview_edge,
        ),
        (
            PredicateSpec(
                lambda context: context.operation.get("op") == "add_acceptance_criterion",
                name="preview.add_acceptance_criterion",
            ),
            _add_preview_acceptance_criterion,
        ),
        (
            PredicateSpec(
                lambda context: context.operation.get("op") == "replace_claim_type",
                name="preview.replace_claim_type",
            ),
            _replace_preview_claim_type,
        ),
    ),
    _ignore_preview_operation,
    name="preview_operation",
)
```

Supporting declaration: `tools/candidate_repair_loop.py::import@3`

```python
from __future__ import annotations
```

Supporting declaration: `tools/candidate_repair_loop.py::import@5`

```python
import argparse
```

Supporting declaration: `tools/candidate_repair_loop.py::import@6`

```python
import copy
```

Supporting declaration: `tools/candidate_repair_loop.py::import@7`

```python
import json
```

Supporting declaration: `tools/candidate_repair_loop.py::import@8`

```python
import re
```

Supporting declaration: `tools/candidate_repair_loop.py::import@9`

```python
from collections.abc import Callable
```

Supporting declaration: `tools/candidate_repair_loop.py::import@10`

```python
from dataclasses import dataclass
```

Supporting declaration: `tools/candidate_repair_loop.py::import@11`

```python
from datetime import datetime, timezone
```

Supporting declaration: `tools/candidate_repair_loop.py::import@12`

```python
from pathlib import Path
```

Supporting declaration: `tools/candidate_repair_loop.py::import@13`

```python
from typing import Any
```

Supporting declaration: `tools/candidate_repair_loop.py::import@15`

```python
from specification_core import FirstMatch, PredicateSpec
```

Supporting declaration: `tools/candidate_repair_loop.py::_PreviewOperationContext`

```python
@dataclass(frozen=True)
class _PreviewOperationContext:
    operation: dict[str, Any]
```

Supporting declaration: `tools/candidate_repair_loop.py::_ignore_preview_operation`

```python
def _ignore_preview_operation(_preview: dict[str, Any], _operation: dict[str, Any]) -> None:
    return None
```

Supporting declaration: `tools/candidate_repair_loop.py::_append_preview_edge`

```python
def _append_preview_edge(preview: dict[str, Any], operation: dict[str, Any]) -> None:
    preview.setdefault("edges", []).append(operation["value"])
```

Supporting declaration: `tools/candidate_repair_loop.py::_add_preview_acceptance_criterion`

```python
def _add_preview_acceptance_criterion(preview: dict[str, Any], operation: dict[str, Any]) -> None:
    node = _node_by_id(preview, _text(operation.get("node_id")))
    if node is None:
        return
    node.setdefault("acceptance_criteria", []).append(operation["value"])
    for requirement in _list(node.get("requirements")):
        if not isinstance(requirement, dict):
            continue
        if _text(requirement.get("id")) == _text(operation.get("requirement_id")):
            refs = _text_list(requirement.get("acceptance_criteria_refs"))
            if operation["value"]["id"] not in refs:
                refs.append(operation["value"]["id"])
            requirement["acceptance_criteria_refs"] = refs
```

Supporting declaration: `tools/candidate_repair_loop.py::_replace_preview_claim_type`

```python
def _replace_preview_claim_type(preview: dict[str, Any], operation: dict[str, Any]) -> None:
    node = _node_by_id(preview, _text(operation.get("node_id")))
    if node is None:
        return
    for claim in _list(node.get("claims")):
        if isinstance(claim, dict) and _text(claim.get("id")) == _text(operation.get("claim_id")):
            claim["type"] = operation["value"]
            if _text(claim.get("strength")) == "strong":
                claim["strength"] = operation["value"]
            claim["repair_generated_type_change"] = True
```

Supporting declaration: `tools/candidate_repair_loop.py::_node_by_id`

```python
def _node_by_id(candidate_graph: dict[str, Any], node_id: str) -> dict[str, Any] | None:
    for node in _nodes(candidate_graph):
        if _text(node.get("id")) == node_id:
            return node
    return None
```

Supporting declaration: `tools/candidate_repair_loop.py::_dict`

```python
def _dict(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}
```

Supporting declaration: `tools/candidate_repair_loop.py::_list`

```python
def _list(value: Any) -> list[Any]:
    return value if isinstance(value, list) else []
```

Supporting declaration: `tools/candidate_repair_loop.py::_text`

```python
def _text(value: Any, default: str = "") -> str:
    return value.strip() if isinstance(value, str) and value.strip() else default
```

Supporting declaration: `tools/candidate_repair_loop.py::_text_list`

```python
def _text_list(value: Any) -> list[str]:
    return [item.strip() for item in _list(value) if isinstance(item, str) and item.strip()]
```

Opportunity: ______  Concern kind: ______

Evidence / missing context: ______

## sg-025

[Pinned source](https://github.com/0al-spec/SpecGraph/blob/162f17b8c52c1753d4649f0ec56d49cd912e77b4/tools/idea_to_spec_rerun_preview.py#L1447-L1511)

```python
def _candidate_quality_preview(
    ontology_gap_preview: dict[str, Any],
    candidate_gap_preview: dict[str, Any],
) -> dict[str, Any]:
    unresolved_ontology_count = _int(ontology_gap_preview.get("unresolved_ontology_gap_count"))
    resolved_ontology_count = _int(ontology_gap_preview.get("resolved_ontology_gap_count"))
    unresolved_candidate_count = _int(candidate_gap_preview.get("unresolved_candidate_gap_count"))
    resolved_candidate_count = _int(candidate_gap_preview.get("resolved_candidate_gap_count"))
    unresolved_count = unresolved_ontology_count + unresolved_candidate_count
    resolved_count = resolved_ontology_count + resolved_candidate_count
    if unresolved_count == 0 and resolved_count > 0:
        review_state = "candidate_quality_improved"
        ontology_gap_state = (
            "all_preview_resolved" if resolved_ontology_count > 0 else "no_ontology_gaps"
        )
        candidate_gap_state = (
            "all_preview_resolved" if resolved_candidate_count > 0 else "no_candidate_gaps"
        )
    elif resolved_count > 0:
        review_state = "candidate_quality_partially_improved"
        ontology_gap_state = (
            "partially_preview_resolved"
            if unresolved_ontology_count
            else "all_preview_resolved"
            if resolved_ontology_count
            else "no_ontology_gaps"
        )
        candidate_gap_state = (
            "partially_preview_resolved"
            if unresolved_candidate_count
            else "all_preview_resolved"
            if resolved_candidate_count
            else "no_candidate_gaps"
        )
    elif unresolved_ontology_count > 0 and unresolved_candidate_count > 0:
        review_state = "candidate_quality_blocked_by_gaps"
        ontology_gap_state = "unresolved"
        candidate_gap_state = "unresolved"
    elif unresolved_ontology_count > 0:
        review_state = "candidate_quality_blocked_by_ontology_gaps"
        ontology_gap_state = "unresolved"
        candidate_gap_state = "no_candidate_gaps"
    elif unresolved_candidate_count > 0:
        review_state = "candidate_quality_blocked_by_candidate_gaps"
        ontology_gap_state = "no_ontology_gaps"
        candidate_gap_state = "unresolved"
    else:
        review_state = "candidate_quality_unchanged"
        ontology_gap_state = "no_ontology_gaps"
        candidate_gap_state = "no_candidate_gaps"
    return {
        "review_state": review_state,
        "ontology_gap_state": ontology_gap_state,
        "candidate_gap_state": candidate_gap_state,
        "resolved_ontology_gap_count": resolved_ontology_count,
        "unresolved_ontology_gap_count": unresolved_ontology_count,
        "resolved_candidate_gap_count": resolved_candidate_count,
        "unresolved_candidate_gap_count": unresolved_candidate_count,
        "candidate_quality_metric": (
            "candidate_gap_resolution_preview"
            if resolved_candidate_count or unresolved_candidate_count
            else "ontology_gap_resolution_preview"
        ),
        "canonical_mutations_allowed": False,
    }
```

Supporting declaration: `tools/idea_to_spec_rerun_preview.py::import@3`

```python
from __future__ import annotations
```

Supporting declaration: `tools/idea_to_spec_rerun_preview.py::import@5`

```python
import argparse
```

Supporting declaration: `tools/idea_to_spec_rerun_preview.py::import@6`

```python
import json
```

Supporting declaration: `tools/idea_to_spec_rerun_preview.py::import@7`

```python
import re
```

Supporting declaration: `tools/idea_to_spec_rerun_preview.py::import@8`

```python
from datetime import datetime, timezone
```

Supporting declaration: `tools/idea_to_spec_rerun_preview.py::import@9`

```python
from pathlib import Path
```

Supporting declaration: `tools/idea_to_spec_rerun_preview.py::import@10`

```python
from typing import Any
```

Supporting declaration: `tools/idea_to_spec_rerun_preview.py::_int`

```python
def _int(value: Any, default: int = 0) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default
```

Opportunity: ______  Concern kind: ______

Evidence / missing context: ______

## sg-026

[Pinned source](https://github.com/0al-spec/SpecGraph/blob/6786e0c85e8d8dded11d864e6a3f021d88fa80db/tools/idea_to_spec_candidate_quality_review_spec.py#L6-L48)

```python
_CANDIDATE_QUALITY_REVIEW_SPEC = FirstMatch.with_fallback(
    (
        (
            PredicateSpec(
                lambda context: context.unresolved_count == 0 and context.resolved_count > 0,
                name="candidate_quality.all_gaps_resolved",
            ),
            "candidate_quality_improved",
        ),
        (
            PredicateSpec(
                lambda context: context.resolved_count > 0,
                name="candidate_quality.some_gaps_resolved",
            ),
            "candidate_quality_partially_improved",
        ),
        (
            PredicateSpec(
                lambda context: (
                    context.unresolved_ontology_count > 0 and context.unresolved_candidate_count > 0
                ),
                name="candidate_quality.both_gap_families_unresolved",
            ),
            "candidate_quality_blocked_by_gaps",
        ),
        (
            PredicateSpec(
                lambda context: context.unresolved_ontology_count > 0,
                name="candidate_quality.ontology_gaps_unresolved",
            ),
            "candidate_quality_blocked_by_ontology_gaps",
        ),
        (
            PredicateSpec(
                lambda context: context.unresolved_candidate_count > 0,
                name="candidate_quality.candidate_gaps_unresolved",
            ),
            "candidate_quality_blocked_by_candidate_gaps",
        ),
    ),
    "candidate_quality_unchanged",
    name="candidate_quality_review_state",
)
```

Supporting declaration: `tools/idea_to_spec_candidate_quality_review_spec.py::import@3`

```python
from specification_core import FirstMatch, PredicateSpec
```

Supporting declaration: `tools/idea_to_spec_candidate_quality_review_spec.py::import@4`

```python
from tools.idea_to_spec_candidate_quality_context import CandidateQualityContext
```

Supporting declaration: `tools/idea_to_spec_candidate_quality_context.py::CandidateQualityContext`

```python
@dataclass(frozen=True)
class CandidateQualityContext:
    resolved_ontology_count: int
    unresolved_ontology_count: int
    resolved_candidate_count: int
    unresolved_candidate_count: int

    @property
    def resolved_count(self) -> int:
        return self.resolved_ontology_count + self.resolved_candidate_count

    @property
    def unresolved_count(self) -> int:
        return self.unresolved_ontology_count + self.unresolved_candidate_count
```

Opportunity: ______  Concern kind: ______

Evidence / missing context: ______

## sg-027

[Pinned source](https://github.com/0al-spec/SpecGraph/blob/0d3b0048055919e67b745cc2261977e5e4f76def/tools/repaired_candidate_promotion_handoff.py#L338-L379)

```python
def _repair_loop_for_repaired_handoff(
    repair_loop: dict[str, Any],
    *,
    pre_sib_report: dict[str, Any],
) -> dict[str, Any]:
    if _dict(pre_sib_report.get("readiness")).get("ready") is not True:
        return repair_loop
    if _dict(repair_loop.get("readiness")).get("ready") is True:
        return repair_loop
    if _list(repair_loop.get("findings")):
        return repair_loop
    summary = _dict(repair_loop.get("summary"))
    if summary.get("applied_action_count", 0) != 0:
        return repair_loop
    if summary.get("context_required_count", 0) != 0:
        return repair_loop

    normalized = copy.deepcopy(repair_loop)
    readiness = dict(_dict(normalized.get("readiness")))
    readiness.update(
        {
            "ready": True,
            "review_state": "repair_preview_ready",
            "blocked_by": [],
        }
    )
    normalized["readiness"] = readiness
    normalized_summary = dict(summary)
    normalized_summary.update(
        {
            "status": "repair_preview_ready",
            "no_op_repair_loop": True,
        }
    )
    normalized["summary"] = normalized_summary
    normalized["repaired_candidate_promotion_handoff"] = {
        "proposal_id": PROPOSAL_ID,
        "contract_ref": CONTRACT_REF,
        "state": "clean_pre_sib_pass_through",
        "reason": "repaired pre-SIB report is already ready and no repair action is required",
    }
    return normalized
```

Supporting declaration: `tools/repaired_candidate_promotion_handoff.py::import@3`

```python
from __future__ import annotations
```

Supporting declaration: `tools/repaired_candidate_promotion_handoff.py::import@5`

```python
import argparse
```

Supporting declaration: `tools/repaired_candidate_promotion_handoff.py::import@6`

```python
import copy
```

Supporting declaration: `tools/repaired_candidate_promotion_handoff.py::import@7`

```python
import json
```

Supporting declaration: `tools/repaired_candidate_promotion_handoff.py::import@8`

```python
import sys
```

Supporting declaration: `tools/repaired_candidate_promotion_handoff.py::import@9`

```python
from datetime import datetime, timezone
```

Supporting declaration: `tools/repaired_candidate_promotion_handoff.py::import@10`

```python
from pathlib import Path
```

Supporting declaration: `tools/repaired_candidate_promotion_handoff.py::import@11`

```python
from typing import Any
```

Supporting declaration: `tools/repaired_candidate_promotion_handoff.py::import@17`

```python
import active_idea_to_spec_candidate_source  # noqa: E402
```

Supporting declaration: `tools/repaired_candidate_promotion_handoff.py::import@18`

```python
import candidate_repair_loop  # noqa: E402
```

Supporting declaration: `tools/repaired_candidate_promotion_handoff.py::import@19`

```python
import candidate_spec_materialization  # noqa: E402
```

Supporting declaration: `tools/repaired_candidate_promotion_handoff.py::import@20`

```python
import idea_to_spec_promotion_gate  # noqa: E402
```

Supporting declaration: `tools/repaired_candidate_promotion_handoff.py::import@21`

```python
import idea_to_spec_repair_session_journal  # noqa: E402
```

Supporting declaration: `tools/repaired_candidate_promotion_handoff.py::import@22`

```python
import pre_sib_coherence_report  # noqa: E402
```

Supporting declaration: `tools/repaired_candidate_promotion_handoff.py::_dict`

```python
def _dict(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}
```

Supporting declaration: `tools/repaired_candidate_promotion_handoff.py::_list`

```python
def _list(value: Any) -> list[Any]:
    return value if isinstance(value, list) else []
```

Opportunity: ______  Concern kind: ______

Evidence / missing context: ______

## sg-028

[Pinned source](https://github.com/0al-spec/SpecGraph/blob/7fc2836acf68815edfc68d0dc8a500ddb067f304/tools/repaired_handoff_noop_passthrough_spec.py#L18-L21)

```python
CLEAN_PRE_SIB_NOOP_PASSTHROUGH = PredicateSpec(
    _is_clean_pre_sib_noop_passthrough,
    name="repaired_handoff.clean_pre_sib_noop_passthrough",
)
```

Supporting declaration: `tools/repaired_handoff_noop_passthrough_spec.py::import@3`

```python
from specification_core import PredicateSpec
```

Supporting declaration: `tools/repaired_handoff_noop_passthrough_spec.py::import@5`

```python
from repaired_handoff_context import RepairedHandoffContext
```

Supporting declaration: `tools/repaired_handoff_noop_passthrough_spec.py::_is_clean_pre_sib_noop_passthrough`

```python
def _is_clean_pre_sib_noop_passthrough(context: RepairedHandoffContext) -> bool:
    return (
        context.pre_sib_ready
        and not context.repair_loop_ready
        and not context.has_findings
        and context.applied_action_count == 0
        and context.context_required_count == 0
    )
```

Supporting declaration: `tools/repaired_handoff_context.py::RepairedHandoffContext`

```python
@dataclass(frozen=True)
class RepairedHandoffContext:
    pre_sib_ready: bool
    repair_loop_ready: bool
    has_findings: bool
    applied_action_count: object
    context_required_count: object
```

Opportunity: ______  Concern kind: ______

Evidence / missing context: ______

## sg-029

[Pinned source](https://github.com/0al-spec/SpecGraph/blob/425078cc74e1c2cccbff259b5505b1b958b8e904/tools/ontology_imports.py#L6038-L6038)

```python
    accepted_count = sum(1 for decision in decisions if decision["decision_state"] == "accepted")
```

Supporting declaration: `tools/ontology_imports.py::import@4`

```python
from __future__ import annotations
```

Supporting declaration: `tools/ontology_imports.py::import@6`

```python
import argparse
```

Supporting declaration: `tools/ontology_imports.py::import@7`

```python
import copy
```

Supporting declaration: `tools/ontology_imports.py::import@8`

```python
import hashlib
```

Supporting declaration: `tools/ontology_imports.py::import@9`

```python
import json
```

Supporting declaration: `tools/ontology_imports.py::import@10`

```python
import re
```

Supporting declaration: `tools/ontology_imports.py::import@11`

```python
from pathlib import Path
```

Supporting declaration: `tools/ontology_imports.py::import@12`

```python
from typing import Any
```

Supporting declaration: `tools/ontology_imports.py::import@14`

```python
import yaml
```

Supporting declaration: `tools/ontology_imports.py::build_ontology_owner_decision_report`

```python
    rejected_count = sum(1 for decision in decisions if decision["decision_state"] == "rejected")
```

Supporting declaration: `tools/ontology_imports.py::build_ontology_owner_decision_report`

```python
    clarification_count = sum(
        1 for decision in decisions if decision["decision_state"] == "needs_clarification"
    )
```

Opportunity: ______  Concern kind: ______

Evidence / missing context: ______

## sg-030

[Pinned source](https://github.com/0al-spec/SpecGraph/blob/11e7e1356f1a207d26767ea857e5d2a2ae4e482f/tools/ontology_decision_state_spec.py#L22-L35)

```python
def count_decision_states(records: Sequence[Mapping[str, object]]) -> DecisionStateCounts:
    """Count exact state values in already prepared report rows.

    Unknown values contribute to no bucket. A missing decision_state remains a
    KeyError, as in the original report code. Keep the three traversal passes
    so this extraction preserves evaluation order as well as report counts.
    """
    return DecisionStateCounts(
        accepted=sum(1 for row in records if ACCEPTED.is_satisfied_by(row["decision_state"])),
        rejected=sum(1 for row in records if REJECTED.is_satisfied_by(row["decision_state"])),
        clarification=sum(
            1 for row in records if NEEDS_CLARIFICATION.is_satisfied_by(row["decision_state"])
        ),
    )
```

Supporting declaration: `tools/ontology_decision_state_spec.py::import@3`

```python
from collections.abc import Mapping, Sequence
```

Supporting declaration: `tools/ontology_decision_state_spec.py::import@4`

```python
from dataclasses import dataclass
```

Supporting declaration: `tools/ontology_decision_state_spec.py::import@6`

```python
from specification_core import PredicateSpec
```

Supporting declaration: `tools/ontology_decision_state_spec.py::ACCEPTED`

```python
ACCEPTED = PredicateSpec(lambda state: state == "accepted", name="ontology_decision.accepted")
```

Supporting declaration: `tools/ontology_decision_state_spec.py::REJECTED`

```python
REJECTED = PredicateSpec(lambda state: state == "rejected", name="ontology_decision.rejected")
```

Supporting declaration: `tools/ontology_decision_state_spec.py::NEEDS_CLARIFICATION`

```python
NEEDS_CLARIFICATION = PredicateSpec(
    lambda state: state == "needs_clarification", name="ontology_decision.needs_clarification"
)
```

Supporting declaration: `tools/ontology_decision_state_spec.py::DecisionStateCounts`

```python
@dataclass(frozen=True)
class DecisionStateCounts:
    accepted: int
    rejected: int
    clarification: int
```

Opportunity: ______  Concern kind: ______

Evidence / missing context: ______

## sg-031

[Pinned source](https://github.com/0al-spec/SpecGraph/blob/a5ab64363d054bae759b81441da6b79dbd4a9e86/tools/idea_to_spec_promotion_gate.py#L34-L35)

```python
def _dict(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}
```

Supporting declaration: `tools/idea_to_spec_promotion_gate.py::import@3`

```python
from __future__ import annotations
```

Supporting declaration: `tools/idea_to_spec_promotion_gate.py::import@5`

```python
import argparse
```

Supporting declaration: `tools/idea_to_spec_promotion_gate.py::import@6`

```python
import json
```

Supporting declaration: `tools/idea_to_spec_promotion_gate.py::import@7`

```python
import sys
```

Supporting declaration: `tools/idea_to_spec_promotion_gate.py::import@8`

```python
from dataclasses import dataclass
```

Supporting declaration: `tools/idea_to_spec_promotion_gate.py::import@9`

```python
from datetime import datetime, timezone
```

Supporting declaration: `tools/idea_to_spec_promotion_gate.py::import@10`

```python
from enum import Enum
```

Supporting declaration: `tools/idea_to_spec_promotion_gate.py::import@11`

```python
from pathlib import Path
```

Supporting declaration: `tools/idea_to_spec_promotion_gate.py::import@12`

```python
from typing import Any
```

Supporting declaration: `tools/idea_to_spec_promotion_gate.py::import@14`

```python
from specification_core import FirstMatch, PredicateSpec, TraceRecorder
```

Supporting declaration: `tools/idea_to_spec_promotion_gate.py::_dict`

```python
def _dict(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}
```

Supporting declaration: `tools/idea_to_spec_promotion_gate.py::_list`

```python
def _list(value: Any) -> list[Any]:
    return value if isinstance(value, list) else []
```

Supporting declaration: `tools/idea_to_spec_promotion_gate.py::_text`

```python
def _text(value: Any, default: str = "") -> str:
    return value.strip() if isinstance(value, str) and value.strip() else default
```

Supporting declaration: `tools/idea_to_spec_promotion_gate.py::_text_list`

```python
def _text_list(value: Any) -> list[str]:
    return [item.strip() for item in _list(value) if isinstance(item, str) and item.strip()]
```

Opportunity: ______  Concern kind: ______

Evidence / missing context: ______

## sg-032

[Pinned source](https://github.com/0al-spec/SpecGraph/blob/a5ab64363d054bae759b81441da6b79dbd4a9e86/tools/idea_to_spec_promotion_gate.py#L42-L43)

```python
def _text(value: Any, default: str = "") -> str:
    return value.strip() if isinstance(value, str) and value.strip() else default
```

Supporting declaration: `tools/idea_to_spec_promotion_gate.py::import@3`

```python
from __future__ import annotations
```

Supporting declaration: `tools/idea_to_spec_promotion_gate.py::import@5`

```python
import argparse
```

Supporting declaration: `tools/idea_to_spec_promotion_gate.py::import@6`

```python
import json
```

Supporting declaration: `tools/idea_to_spec_promotion_gate.py::import@7`

```python
import sys
```

Supporting declaration: `tools/idea_to_spec_promotion_gate.py::import@8`

```python
from dataclasses import dataclass
```

Supporting declaration: `tools/idea_to_spec_promotion_gate.py::import@9`

```python
from datetime import datetime, timezone
```

Supporting declaration: `tools/idea_to_spec_promotion_gate.py::import@10`

```python
from enum import Enum
```

Supporting declaration: `tools/idea_to_spec_promotion_gate.py::import@11`

```python
from pathlib import Path
```

Supporting declaration: `tools/idea_to_spec_promotion_gate.py::import@12`

```python
from typing import Any
```

Supporting declaration: `tools/idea_to_spec_promotion_gate.py::import@14`

```python
from specification_core import FirstMatch, PredicateSpec, TraceRecorder
```

Supporting declaration: `tools/idea_to_spec_promotion_gate.py::_dict`

```python
def _dict(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}
```

Supporting declaration: `tools/idea_to_spec_promotion_gate.py::_list`

```python
def _list(value: Any) -> list[Any]:
    return value if isinstance(value, list) else []
```

Supporting declaration: `tools/idea_to_spec_promotion_gate.py::_text`

```python
def _text(value: Any, default: str = "") -> str:
    return value.strip() if isinstance(value, str) and value.strip() else default
```

Supporting declaration: `tools/idea_to_spec_promotion_gate.py::_text_list`

```python
def _text_list(value: Any) -> list[str]:
    return [item.strip() for item in _list(value) if isinstance(item, str) and item.strip()]
```

Opportunity: ______  Concern kind: ______

Evidence / missing context: ______

## sg-033

[Pinned source](https://github.com/0al-spec/SpecGraph/blob/9b285a2e018331460c1a6bee46a697b24a26d3fb/tools/subject_publication.py#L499-L508)

```python
        require(
            allocation["workspace_identity"] == request.topology.workspace_identity
            and allocation["source_ref"] == request.source_ref
            and allocation["expected_commit"] == request.expected_commit
            and allocation["identity_allocation_authorized"] is True
            and allocation["source_ref_initialization_authorized"] is True
            and allocation["declaration_sha256"]
            == hashlib.sha256(request.workspace_declaration_yaml.encode()).hexdigest(),
            "workspace allocation covers a different bootstrap",
        )
```

Supporting declaration: `tools/subject_publication.py::import@7`

```python
from __future__ import annotations
```

Supporting declaration: `tools/subject_publication.py::import@9`

```python
import hashlib
```

Supporting declaration: `tools/subject_publication.py::import@10`

```python
import json
```

Supporting declaration: `tools/subject_publication.py::import@11`

```python
import re
```

Supporting declaration: `tools/subject_publication.py::import@12`

```python
from dataclasses import asdict, dataclass
```

Supporting declaration: `tools/subject_publication.py::import@13`

```python
from datetime import datetime
```

Supporting declaration: `tools/subject_publication.py::import@14`

```python
from pathlib import Path, PurePosixPath
```

Supporting declaration: `tools/subject_publication.py::import@15`

```python
from typing import TYPE_CHECKING
```

Supporting declaration: `tools/subject_publication.py::import@17`

```python
from yaml import YAMLError
```

Supporting declaration: `tools/subject_publication.py::import@19`

```python
from spec_yaml import load_yaml_text
```

Supporting declaration: `tools/subject_publication.py::import@20`

```python
from subject_canonical_source import parse_topology_selection
```

Supporting declaration: `tools/subject_publication.py::import@21`

```python
from subject_human_approval_spec import HUMAN_APPROVAL_SPEC
```

Supporting declaration: `tools/subject_publication.py::import@22`

```python
from subject_publication_context import (
    HumanApprovalContext,
    ReviewedRecordContext,
    TransitionApprovalContext,
)
```

Supporting declaration: `tools/subject_publication.py::import@27`

```python
from subject_read_model_io import SubjectDocumentError, _object
```

Supporting declaration: `tools/subject_publication.py::import@28`

```python
from subject_reviewed_record_spec import REVIEWED_RECORD_SPEC
```

Supporting declaration: `tools/subject_publication.py::import@29`

```python
from subject_source_git import git_command, require_commit_id
```

Supporting declaration: `tools/subject_publication.py::import@30`

```python
from subject_transition_approval_spec import TRANSITION_APPROVAL_SPEC
```

Supporting declaration: `tools/subject_publication.py::require`

```python
def require(condition: bool, message: str) -> None:
    if not condition:
        raise PublicationGovernanceError(f"publication governance: {message}")
```

Opportunity: ______  Concern kind: ______

Evidence / missing context: ______

## sg-034

[Pinned source](https://github.com/0al-spec/SpecGraph/blob/a5ab64363d054bae759b81441da6b79dbd4a9e86/tools/candidate_repair_loop.py#L139-L141)

```python
def _slug(value: str, fallback: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")
    return slug or fallback
```

Supporting declaration: `tools/candidate_repair_loop.py::import@3`

```python
from __future__ import annotations
```

Supporting declaration: `tools/candidate_repair_loop.py::import@5`

```python
import argparse
```

Supporting declaration: `tools/candidate_repair_loop.py::import@6`

```python
import copy
```

Supporting declaration: `tools/candidate_repair_loop.py::import@7`

```python
import json
```

Supporting declaration: `tools/candidate_repair_loop.py::import@8`

```python
import re
```

Supporting declaration: `tools/candidate_repair_loop.py::import@9`

```python
import sys
```

Supporting declaration: `tools/candidate_repair_loop.py::import@10`

```python
from collections.abc import Callable
```

Supporting declaration: `tools/candidate_repair_loop.py::import@11`

```python
from dataclasses import dataclass
```

Supporting declaration: `tools/candidate_repair_loop.py::import@12`

```python
from datetime import datetime, timezone
```

Supporting declaration: `tools/candidate_repair_loop.py::import@13`

```python
from enum import Enum
```

Supporting declaration: `tools/candidate_repair_loop.py::import@14`

```python
from pathlib import Path
```

Supporting declaration: `tools/candidate_repair_loop.py::import@15`

```python
from typing import Any
```

Supporting declaration: `tools/candidate_repair_loop.py::import@17`

```python
from specification_core import FirstMatch, PredicateSpec
```

Supporting declaration: `tools/candidate_repair_loop.py::import@23`

```python
from candidate_repair_readiness_context import CandidateRepairReadinessContext  # noqa: E402
```

Supporting declaration: `tools/candidate_repair_loop.py::import@24`

```python
from candidate_repair_readiness_spec import candidate_repair_readiness  # noqa: E402
```

Supporting declaration: `tools/candidate_repair_loop.py::_dict`

```python
def _dict(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}
```

Supporting declaration: `tools/candidate_repair_loop.py::_list`

```python
def _list(value: Any) -> list[Any]:
    return value if isinstance(value, list) else []
```

Supporting declaration: `tools/candidate_repair_loop.py::_text`

```python
def _text(value: Any, default: str = "") -> str:
    return value.strip() if isinstance(value, str) and value.strip() else default
```

Supporting declaration: `tools/candidate_repair_loop.py::_text_list`

```python
def _text_list(value: Any) -> list[str]:
    return [item.strip() for item in _list(value) if isinstance(item, str) and item.strip()]
```

Opportunity: ______  Concern kind: ______

Evidence / missing context: ______

## sg-035

[Pinned source](https://github.com/0al-spec/SpecGraph/blob/a5ab64363d054bae759b81441da6b79dbd4a9e86/tools/candidate_repair_loop.py#L277-L286)

```python
def _edge_degrees(candidate_graph: dict[str, Any]) -> dict[str, int]:
    degrees = {
        _text(node.get("id")): 0 for node in _nodes(candidate_graph) if _text(node.get("id"))
    }
    for edge in _edges(candidate_graph):
        for field in ("from", "to"):
            ref = _text(edge.get(field))
            if ref in degrees:
                degrees[ref] += 1
    return degrees
```

Supporting declaration: `tools/candidate_repair_loop.py::import@3`

```python
from __future__ import annotations
```

Supporting declaration: `tools/candidate_repair_loop.py::import@5`

```python
import argparse
```

Supporting declaration: `tools/candidate_repair_loop.py::import@6`

```python
import copy
```

Supporting declaration: `tools/candidate_repair_loop.py::import@7`

```python
import json
```

Supporting declaration: `tools/candidate_repair_loop.py::import@8`

```python
import re
```

Supporting declaration: `tools/candidate_repair_loop.py::import@9`

```python
import sys
```

Supporting declaration: `tools/candidate_repair_loop.py::import@10`

```python
from collections.abc import Callable
```

Supporting declaration: `tools/candidate_repair_loop.py::import@11`

```python
from dataclasses import dataclass
```

Supporting declaration: `tools/candidate_repair_loop.py::import@12`

```python
from datetime import datetime, timezone
```

Supporting declaration: `tools/candidate_repair_loop.py::import@13`

```python
from enum import Enum
```

Supporting declaration: `tools/candidate_repair_loop.py::import@14`

```python
from pathlib import Path
```

Supporting declaration: `tools/candidate_repair_loop.py::import@15`

```python
from typing import Any
```

Supporting declaration: `tools/candidate_repair_loop.py::import@17`

```python
from specification_core import FirstMatch, PredicateSpec
```

Supporting declaration: `tools/candidate_repair_loop.py::import@23`

```python
from candidate_repair_readiness_context import CandidateRepairReadinessContext  # noqa: E402
```

Supporting declaration: `tools/candidate_repair_loop.py::import@24`

```python
from candidate_repair_readiness_spec import candidate_repair_readiness  # noqa: E402
```

Supporting declaration: `tools/candidate_repair_loop.py::_dict`

```python
def _dict(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}
```

Supporting declaration: `tools/candidate_repair_loop.py::_list`

```python
def _list(value: Any) -> list[Any]:
    return value if isinstance(value, list) else []
```

Supporting declaration: `tools/candidate_repair_loop.py::_text`

```python
def _text(value: Any, default: str = "") -> str:
    return value.strip() if isinstance(value, str) and value.strip() else default
```

Supporting declaration: `tools/candidate_repair_loop.py::_text_list`

```python
def _text_list(value: Any) -> list[str]:
    return [item.strip() for item in _list(value) if isinstance(item, str) and item.strip()]
```

Opportunity: ______  Concern kind: ______

Evidence / missing context: ______

## sg-036

[Pinned source](https://github.com/0al-spec/SpecGraph/blob/a5ab64363d054bae759b81441da6b79dbd4a9e86/tools/candidate_repair_loop.py#L565-L569)

```python
def _node_by_id(candidate_graph: dict[str, Any], node_id: str) -> dict[str, Any] | None:
    for node in _nodes(candidate_graph):
        if _text(node.get("id")) == node_id:
            return node
    return None
```

Supporting declaration: `tools/candidate_repair_loop.py::import@3`

```python
from __future__ import annotations
```

Supporting declaration: `tools/candidate_repair_loop.py::import@5`

```python
import argparse
```

Supporting declaration: `tools/candidate_repair_loop.py::import@6`

```python
import copy
```

Supporting declaration: `tools/candidate_repair_loop.py::import@7`

```python
import json
```

Supporting declaration: `tools/candidate_repair_loop.py::import@8`

```python
import re
```

Supporting declaration: `tools/candidate_repair_loop.py::import@9`

```python
import sys
```

Supporting declaration: `tools/candidate_repair_loop.py::import@10`

```python
from collections.abc import Callable
```

Supporting declaration: `tools/candidate_repair_loop.py::import@11`

```python
from dataclasses import dataclass
```

Supporting declaration: `tools/candidate_repair_loop.py::import@12`

```python
from datetime import datetime, timezone
```

Supporting declaration: `tools/candidate_repair_loop.py::import@13`

```python
from enum import Enum
```

Supporting declaration: `tools/candidate_repair_loop.py::import@14`

```python
from pathlib import Path
```

Supporting declaration: `tools/candidate_repair_loop.py::import@15`

```python
from typing import Any
```

Supporting declaration: `tools/candidate_repair_loop.py::import@17`

```python
from specification_core import FirstMatch, PredicateSpec
```

Supporting declaration: `tools/candidate_repair_loop.py::import@23`

```python
from candidate_repair_readiness_context import CandidateRepairReadinessContext  # noqa: E402
```

Supporting declaration: `tools/candidate_repair_loop.py::import@24`

```python
from candidate_repair_readiness_spec import candidate_repair_readiness  # noqa: E402
```

Supporting declaration: `tools/candidate_repair_loop.py::_dict`

```python
def _dict(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}
```

Supporting declaration: `tools/candidate_repair_loop.py::_list`

```python
def _list(value: Any) -> list[Any]:
    return value if isinstance(value, list) else []
```

Supporting declaration: `tools/candidate_repair_loop.py::_text`

```python
def _text(value: Any, default: str = "") -> str:
    return value.strip() if isinstance(value, str) and value.strip() else default
```

Supporting declaration: `tools/candidate_repair_loop.py::_text_list`

```python
def _text_list(value: Any) -> list[str]:
    return [item.strip() for item in _list(value) if isinstance(item, str) and item.strip()]
```

Opportunity: ______  Concern kind: ______

Evidence / missing context: ______

## sg-037

[Pinned source](https://github.com/0al-spec/SpecGraph/blob/a5ab64363d054bae759b81441da6b79dbd4a9e86/tools/idea_maturity_metrics_report.py#L351-L357)

```python
def _parse_time(value: Any) -> datetime | None:
    if not isinstance(value, str) or not value.strip():
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
```

Supporting declaration: `tools/idea_maturity_metrics_report.py::import@3`

```python
from __future__ import annotations
```

Supporting declaration: `tools/idea_maturity_metrics_report.py::import@5`

```python
import argparse
```

Supporting declaration: `tools/idea_maturity_metrics_report.py::import@6`

```python
import json
```

Supporting declaration: `tools/idea_maturity_metrics_report.py::import@7`

```python
import re
```

Supporting declaration: `tools/idea_maturity_metrics_report.py::import@8`

```python
import sys
```

Supporting declaration: `tools/idea_maturity_metrics_report.py::import@9`

```python
from collections import Counter
```

Supporting declaration: `tools/idea_maturity_metrics_report.py::import@10`

```python
from datetime import datetime, timezone
```

Supporting declaration: `tools/idea_maturity_metrics_report.py::import@11`

```python
from pathlib import Path
```

Supporting declaration: `tools/idea_maturity_metrics_report.py::import@12`

```python
from typing import Any
```

Supporting declaration: `tools/idea_maturity_metrics_report.py::import@14`

```python
from idea_maturity_candidate_approval_decision_spec import (
    candidate_approval_decision_state as _candidate_approval_decision_state_spec,
)
```

Supporting declaration: `tools/idea_maturity_metrics_report.py::import@17`

```python
from idea_maturity_candidate_approval_intent_spec import (
    candidate_approval_intent_state as _candidate_approval_intent_state_spec,
)
```

Supporting declaration: `tools/idea_maturity_metrics_report.py::import@20`

```python
from idea_maturity_candidate_approval_spec import (
    candidate_approval_state as _candidate_approval_state_spec,
)
```

Supporting declaration: `tools/idea_maturity_metrics_report.py::import@23`

```python
from idea_maturity_lifecycle_context import (
    LifecycleStateContext,
    _dict,
    _int,
    _status_is_blocked,
    _status_is_failed,
    _summary,
    _text,
)
```

Supporting declaration: `tools/idea_maturity_metrics_report.py::import@32`

```python
from idea_maturity_lifecycle_state_set import lifecycle_state_values
```

Supporting declaration: `tools/idea_maturity_metrics_report.py::import@33`

```python
from idea_maturity_platform_promotion_spec import (
    platform_promotion_state as _platform_promotion_state_spec,
)
```

Supporting declaration: `tools/idea_maturity_metrics_report.py::import@36`

```python
from idea_maturity_promotion_execution_spec import (
    promotion_execution_state as _promotion_execution_state_spec,
)
```

Supporting declaration: `tools/idea_maturity_metrics_report.py::import@39`

```python
from idea_maturity_promotion_request_spec import (
    promotion_request_state as _promotion_request_state_spec,
)
```

Supporting declaration: `tools/idea_maturity_metrics_report.py::import@42`

```python
from idea_maturity_read_model_publication_spec import (
    read_model_publication_state as _read_model_publication_state_spec,
)
```

Supporting declaration: `tools/idea_maturity_metrics_report.py::import@45`

```python
from idea_maturity_review_spec import review_status as _review_status_spec
```

Supporting declaration: `tools/idea_maturity_metrics_report.py::_list`

```python
def _list(value: Any) -> list[Any]:
    return value if isinstance(value, list) else []
```

Supporting declaration: `tools/idea_maturity_metrics_report.py::_text_list`

```python
def _text_list(value: Any) -> list[str]:
    if isinstance(value, str) and value.strip():
        return [value.strip()]
    if not isinstance(value, list):
        return []
    return [item.strip() for item in value if isinstance(item, str) and item.strip()]
```

Supporting declaration: `tools/idea_maturity_metrics_report.py::_parse_time`

```python
def _parse_time(value: Any) -> datetime | None:
    if not isinstance(value, str) or not value.strip():
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
```

Opportunity: ______  Concern kind: ______

Evidence / missing context: ______

## sg-038

[Pinned source](https://github.com/0al-spec/SpecGraph/blob/a5ab64363d054bae759b81441da6b79dbd4a9e86/tools/idea_maturity_metrics_report.py#L379-L385)

```python
def _seconds_between(start: datetime | None, end: datetime | None) -> float | None:
    if start is None or end is None:
        return None
    seconds = (end - start).total_seconds()
    if seconds < 0:
        return None
    return round(seconds, 3)
```

Supporting declaration: `tools/idea_maturity_metrics_report.py::import@3`

```python
from __future__ import annotations
```

Supporting declaration: `tools/idea_maturity_metrics_report.py::import@5`

```python
import argparse
```

Supporting declaration: `tools/idea_maturity_metrics_report.py::import@6`

```python
import json
```

Supporting declaration: `tools/idea_maturity_metrics_report.py::import@7`

```python
import re
```

Supporting declaration: `tools/idea_maturity_metrics_report.py::import@8`

```python
import sys
```

Supporting declaration: `tools/idea_maturity_metrics_report.py::import@9`

```python
from collections import Counter
```

Supporting declaration: `tools/idea_maturity_metrics_report.py::import@10`

```python
from datetime import datetime, timezone
```

Supporting declaration: `tools/idea_maturity_metrics_report.py::import@11`

```python
from pathlib import Path
```

Supporting declaration: `tools/idea_maturity_metrics_report.py::import@12`

```python
from typing import Any
```

Supporting declaration: `tools/idea_maturity_metrics_report.py::import@14`

```python
from idea_maturity_candidate_approval_decision_spec import (
    candidate_approval_decision_state as _candidate_approval_decision_state_spec,
)
```

Supporting declaration: `tools/idea_maturity_metrics_report.py::import@17`

```python
from idea_maturity_candidate_approval_intent_spec import (
    candidate_approval_intent_state as _candidate_approval_intent_state_spec,
)
```

Supporting declaration: `tools/idea_maturity_metrics_report.py::import@20`

```python
from idea_maturity_candidate_approval_spec import (
    candidate_approval_state as _candidate_approval_state_spec,
)
```

Supporting declaration: `tools/idea_maturity_metrics_report.py::import@23`

```python
from idea_maturity_lifecycle_context import (
    LifecycleStateContext,
    _dict,
    _int,
    _status_is_blocked,
    _status_is_failed,
    _summary,
    _text,
)
```

Supporting declaration: `tools/idea_maturity_metrics_report.py::import@32`

```python
from idea_maturity_lifecycle_state_set import lifecycle_state_values
```

Supporting declaration: `tools/idea_maturity_metrics_report.py::import@33`

```python
from idea_maturity_platform_promotion_spec import (
    platform_promotion_state as _platform_promotion_state_spec,
)
```

Supporting declaration: `tools/idea_maturity_metrics_report.py::import@36`

```python
from idea_maturity_promotion_execution_spec import (
    promotion_execution_state as _promotion_execution_state_spec,
)
```

Supporting declaration: `tools/idea_maturity_metrics_report.py::import@39`

```python
from idea_maturity_promotion_request_spec import (
    promotion_request_state as _promotion_request_state_spec,
)
```

Supporting declaration: `tools/idea_maturity_metrics_report.py::import@42`

```python
from idea_maturity_read_model_publication_spec import (
    read_model_publication_state as _read_model_publication_state_spec,
)
```

Supporting declaration: `tools/idea_maturity_metrics_report.py::import@45`

```python
from idea_maturity_review_spec import review_status as _review_status_spec
```

Supporting declaration: `tools/idea_maturity_metrics_report.py::_list`

```python
def _list(value: Any) -> list[Any]:
    return value if isinstance(value, list) else []
```

Supporting declaration: `tools/idea_maturity_metrics_report.py::_text_list`

```python
def _text_list(value: Any) -> list[str]:
    if isinstance(value, str) and value.strip():
        return [value.strip()]
    if not isinstance(value, list):
        return []
    return [item.strip() for item in value if isinstance(item, str) and item.strip()]
```

Supporting declaration: `tools/idea_maturity_metrics_report.py::_parse_time`

```python
def _parse_time(value: Any) -> datetime | None:
    if not isinstance(value, str) or not value.strip():
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
```

Opportunity: ______  Concern kind: ______

Evidence / missing context: ______

## sg-039

[Pinned source](https://github.com/0al-spec/SpecGraph/blob/a5ab64363d054bae759b81441da6b79dbd4a9e86/tools/idea_maturity_metrics_report.py#L333-L336)

```python
def _rate(numerator: int, denominator: int) -> float | None:
    if denominator <= 0:
        return None
    return round(numerator / denominator, 6)
```

Supporting declaration: `tools/idea_maturity_metrics_report.py::import@3`

```python
from __future__ import annotations
```

Supporting declaration: `tools/idea_maturity_metrics_report.py::import@5`

```python
import argparse
```

Supporting declaration: `tools/idea_maturity_metrics_report.py::import@6`

```python
import json
```

Supporting declaration: `tools/idea_maturity_metrics_report.py::import@7`

```python
import re
```

Supporting declaration: `tools/idea_maturity_metrics_report.py::import@8`

```python
import sys
```

Supporting declaration: `tools/idea_maturity_metrics_report.py::import@9`

```python
from collections import Counter
```

Supporting declaration: `tools/idea_maturity_metrics_report.py::import@10`

```python
from datetime import datetime, timezone
```

Supporting declaration: `tools/idea_maturity_metrics_report.py::import@11`

```python
from pathlib import Path
```

Supporting declaration: `tools/idea_maturity_metrics_report.py::import@12`

```python
from typing import Any
```

Supporting declaration: `tools/idea_maturity_metrics_report.py::import@14`

```python
from idea_maturity_candidate_approval_decision_spec import (
    candidate_approval_decision_state as _candidate_approval_decision_state_spec,
)
```

Supporting declaration: `tools/idea_maturity_metrics_report.py::import@17`

```python
from idea_maturity_candidate_approval_intent_spec import (
    candidate_approval_intent_state as _candidate_approval_intent_state_spec,
)
```

Supporting declaration: `tools/idea_maturity_metrics_report.py::import@20`

```python
from idea_maturity_candidate_approval_spec import (
    candidate_approval_state as _candidate_approval_state_spec,
)
```

Supporting declaration: `tools/idea_maturity_metrics_report.py::import@23`

```python
from idea_maturity_lifecycle_context import (
    LifecycleStateContext,
    _dict,
    _int,
    _status_is_blocked,
    _status_is_failed,
    _summary,
    _text,
)
```

Supporting declaration: `tools/idea_maturity_metrics_report.py::import@32`

```python
from idea_maturity_lifecycle_state_set import lifecycle_state_values
```

Supporting declaration: `tools/idea_maturity_metrics_report.py::import@33`

```python
from idea_maturity_platform_promotion_spec import (
    platform_promotion_state as _platform_promotion_state_spec,
)
```

Supporting declaration: `tools/idea_maturity_metrics_report.py::import@36`

```python
from idea_maturity_promotion_execution_spec import (
    promotion_execution_state as _promotion_execution_state_spec,
)
```

Supporting declaration: `tools/idea_maturity_metrics_report.py::import@39`

```python
from idea_maturity_promotion_request_spec import (
    promotion_request_state as _promotion_request_state_spec,
)
```

Supporting declaration: `tools/idea_maturity_metrics_report.py::import@42`

```python
from idea_maturity_read_model_publication_spec import (
    read_model_publication_state as _read_model_publication_state_spec,
)
```

Supporting declaration: `tools/idea_maturity_metrics_report.py::import@45`

```python
from idea_maturity_review_spec import review_status as _review_status_spec
```

Supporting declaration: `tools/idea_maturity_metrics_report.py::_list`

```python
def _list(value: Any) -> list[Any]:
    return value if isinstance(value, list) else []
```

Supporting declaration: `tools/idea_maturity_metrics_report.py::_text_list`

```python
def _text_list(value: Any) -> list[str]:
    if isinstance(value, str) and value.strip():
        return [value.strip()]
    if not isinstance(value, list):
        return []
    return [item.strip() for item in value if isinstance(item, str) and item.strip()]
```

Supporting declaration: `tools/idea_maturity_metrics_report.py::_parse_time`

```python
def _parse_time(value: Any) -> datetime | None:
    if not isinstance(value, str) or not value.strip():
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
```

Opportunity: ______  Concern kind: ______

Evidence / missing context: ______

## sg-040

[Pinned source](https://github.com/0al-spec/SpecGraph/blob/a5ab64363d054bae759b81441da6b79dbd4a9e86/tools/idea_maturity_metrics_report.py#L668-L683)

```python
def _dedupe_records(records: list[dict[str, Any]]) -> list[dict[str, Any]]:
    deduped: list[dict[str, Any]] = []
    seen: set[tuple[Any, ...]] = set()
    for record in records:
        key = (
            record.get("node_id") or _dict(record.get("match")).get("node_id"),
            record.get("gap_id"),
            record.get("decision_id") or record.get("request_id"),
            record.get("match_kind") or _dict(record.get("match")).get("match_kind"),
            record.get("resolution_kind"),
        )
        if key in seen:
            continue
        seen.add(key)
        deduped.append(record)
    return deduped
```

Supporting declaration: `tools/idea_maturity_metrics_report.py::import@3`

```python
from __future__ import annotations
```

Supporting declaration: `tools/idea_maturity_metrics_report.py::import@5`

```python
import argparse
```

Supporting declaration: `tools/idea_maturity_metrics_report.py::import@6`

```python
import json
```

Supporting declaration: `tools/idea_maturity_metrics_report.py::import@7`

```python
import re
```

Supporting declaration: `tools/idea_maturity_metrics_report.py::import@8`

```python
import sys
```

Supporting declaration: `tools/idea_maturity_metrics_report.py::import@9`

```python
from collections import Counter
```

Supporting declaration: `tools/idea_maturity_metrics_report.py::import@10`

```python
from datetime import datetime, timezone
```

Supporting declaration: `tools/idea_maturity_metrics_report.py::import@11`

```python
from pathlib import Path
```

Supporting declaration: `tools/idea_maturity_metrics_report.py::import@12`

```python
from typing import Any
```

Supporting declaration: `tools/idea_maturity_metrics_report.py::import@14`

```python
from idea_maturity_candidate_approval_decision_spec import (
    candidate_approval_decision_state as _candidate_approval_decision_state_spec,
)
```

Supporting declaration: `tools/idea_maturity_metrics_report.py::import@17`

```python
from idea_maturity_candidate_approval_intent_spec import (
    candidate_approval_intent_state as _candidate_approval_intent_state_spec,
)
```

Supporting declaration: `tools/idea_maturity_metrics_report.py::import@20`

```python
from idea_maturity_candidate_approval_spec import (
    candidate_approval_state as _candidate_approval_state_spec,
)
```

Supporting declaration: `tools/idea_maturity_metrics_report.py::import@23`

```python
from idea_maturity_lifecycle_context import (
    LifecycleStateContext,
    _dict,
    _int,
    _status_is_blocked,
    _status_is_failed,
    _summary,
    _text,
)
```

Supporting declaration: `tools/idea_maturity_metrics_report.py::import@32`

```python
from idea_maturity_lifecycle_state_set import lifecycle_state_values
```

Supporting declaration: `tools/idea_maturity_metrics_report.py::import@33`

```python
from idea_maturity_platform_promotion_spec import (
    platform_promotion_state as _platform_promotion_state_spec,
)
```

Supporting declaration: `tools/idea_maturity_metrics_report.py::import@36`

```python
from idea_maturity_promotion_execution_spec import (
    promotion_execution_state as _promotion_execution_state_spec,
)
```

Supporting declaration: `tools/idea_maturity_metrics_report.py::import@39`

```python
from idea_maturity_promotion_request_spec import (
    promotion_request_state as _promotion_request_state_spec,
)
```

Supporting declaration: `tools/idea_maturity_metrics_report.py::import@42`

```python
from idea_maturity_read_model_publication_spec import (
    read_model_publication_state as _read_model_publication_state_spec,
)
```

Supporting declaration: `tools/idea_maturity_metrics_report.py::import@45`

```python
from idea_maturity_review_spec import review_status as _review_status_spec
```

Supporting declaration: `tools/idea_maturity_metrics_report.py::_list`

```python
def _list(value: Any) -> list[Any]:
    return value if isinstance(value, list) else []
```

Supporting declaration: `tools/idea_maturity_metrics_report.py::_text_list`

```python
def _text_list(value: Any) -> list[str]:
    if isinstance(value, str) and value.strip():
        return [value.strip()]
    if not isinstance(value, list):
        return []
    return [item.strip() for item in value if isinstance(item, str) and item.strip()]
```

Supporting declaration: `tools/idea_maturity_metrics_report.py::_parse_time`

```python
def _parse_time(value: Any) -> datetime | None:
    if not isinstance(value, str) or not value.strip():
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
```

Opportunity: ______  Concern kind: ______

Evidence / missing context: ______

## sg-041

[Pinned source](https://github.com/0al-spec/SpecGraph/blob/a5ab64363d054bae759b81441da6b79dbd4a9e86/tools/evidence_claim_gate.py#L218-L224)

```python
def unique_object(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError(f"duplicate JSON key: {key}")
        result[key] = value
    return result
```

Supporting declaration: `tools/evidence_claim_gate.py::import@3`

```python
from __future__ import annotations
```

Supporting declaration: `tools/evidence_claim_gate.py::import@5`

```python
import argparse
```

Supporting declaration: `tools/evidence_claim_gate.py::import@6`

```python
import hashlib
```

Supporting declaration: `tools/evidence_claim_gate.py::import@7`

```python
import json
```

Supporting declaration: `tools/evidence_claim_gate.py::import@8`

```python
import os
```

Supporting declaration: `tools/evidence_claim_gate.py::import@9`

```python
import re
```

Supporting declaration: `tools/evidence_claim_gate.py::import@10`

```python
import selectors
```

Supporting declaration: `tools/evidence_claim_gate.py::import@11`

```python
import signal
```

Supporting declaration: `tools/evidence_claim_gate.py::import@12`

```python
import stat
```

Supporting declaration: `tools/evidence_claim_gate.py::import@13`

```python
import subprocess
```

Supporting declaration: `tools/evidence_claim_gate.py::import@14`

```python
import tempfile
```

Supporting declaration: `tools/evidence_claim_gate.py::import@15`

```python
import time
```

Supporting declaration: `tools/evidence_claim_gate.py::import@16`

```python
from pathlib import Path
```

Opportunity: ______  Concern kind: ______

Evidence / missing context: ______

## sg-042

[Pinned source](https://github.com/0al-spec/SpecGraph/blob/a5ab64363d054bae759b81441da6b79dbd4a9e86/tools/evidence_claim_gate.py#L238-L249)

```python
def read_bounded(path, limit, label):
    descriptor = os.open(path, os.O_RDONLY | getattr(os, "O_NONBLOCK", 0))
    try:
        if not stat.S_ISREG(os.fstat(descriptor).st_mode):
            raise ValueError(f"{label} must be a regular file")
        with os.fdopen(descriptor, "rb", closefd=False) as stream:
            raw = stream.read(limit + 1)
    finally:
        os.close(descriptor)
    if len(raw) > limit:
        raise ValueError(f"{label} exceeds {limit}-byte limit")
    return raw
```

Supporting declaration: `tools/evidence_claim_gate.py::import@3`

```python
from __future__ import annotations
```

Supporting declaration: `tools/evidence_claim_gate.py::import@5`

```python
import argparse
```

Supporting declaration: `tools/evidence_claim_gate.py::import@6`

```python
import hashlib
```

Supporting declaration: `tools/evidence_claim_gate.py::import@7`

```python
import json
```

Supporting declaration: `tools/evidence_claim_gate.py::import@8`

```python
import os
```

Supporting declaration: `tools/evidence_claim_gate.py::import@9`

```python
import re
```

Supporting declaration: `tools/evidence_claim_gate.py::import@10`

```python
import selectors
```

Supporting declaration: `tools/evidence_claim_gate.py::import@11`

```python
import signal
```

Supporting declaration: `tools/evidence_claim_gate.py::import@12`

```python
import stat
```

Supporting declaration: `tools/evidence_claim_gate.py::import@13`

```python
import subprocess
```

Supporting declaration: `tools/evidence_claim_gate.py::import@14`

```python
import tempfile
```

Supporting declaration: `tools/evidence_claim_gate.py::import@15`

```python
import time
```

Supporting declaration: `tools/evidence_claim_gate.py::import@16`

```python
from pathlib import Path
```

Opportunity: ______  Concern kind: ______

Evidence / missing context: ______

## sg-043

[Pinned source](https://github.com/0al-spec/SpecGraph/blob/a5ab64363d054bae759b81441da6b79dbd4a9e86/tools/evidence_claim_gate.py#L214-L215)

```python
def digest(data):
    return hashlib.sha256(data).hexdigest()
```

Supporting declaration: `tools/evidence_claim_gate.py::import@3`

```python
from __future__ import annotations
```

Supporting declaration: `tools/evidence_claim_gate.py::import@5`

```python
import argparse
```

Supporting declaration: `tools/evidence_claim_gate.py::import@6`

```python
import hashlib
```

Supporting declaration: `tools/evidence_claim_gate.py::import@7`

```python
import json
```

Supporting declaration: `tools/evidence_claim_gate.py::import@8`

```python
import os
```

Supporting declaration: `tools/evidence_claim_gate.py::import@9`

```python
import re
```

Supporting declaration: `tools/evidence_claim_gate.py::import@10`

```python
import selectors
```

Supporting declaration: `tools/evidence_claim_gate.py::import@11`

```python
import signal
```

Supporting declaration: `tools/evidence_claim_gate.py::import@12`

```python
import stat
```

Supporting declaration: `tools/evidence_claim_gate.py::import@13`

```python
import subprocess
```

Supporting declaration: `tools/evidence_claim_gate.py::import@14`

```python
import tempfile
```

Supporting declaration: `tools/evidence_claim_gate.py::import@15`

```python
import time
```

Supporting declaration: `tools/evidence_claim_gate.py::import@16`

```python
from pathlib import Path
```

Opportunity: ______  Concern kind: ______

Evidence / missing context: ______

## sg-044

[Pinned source](https://github.com/0al-spec/SpecGraph/blob/a5ab64363d054bae759b81441da6b79dbd4a9e86/tools/subject_read_model_io.py#L44-L53)

```python
def _object(value: object, required: set[str], optional: set[str] | None = None) -> Mapping:
    if not isinstance(value, Mapping):
        raise SubjectDocumentError("expected a mapping")
    if set(value) - required - (optional or set()):
        raise SubjectDocumentError(
            f"unknown fields: {sorted(map(str, set(value) - required - (optional or set())))}"
        )
    if required - set(value):
        raise SubjectDocumentError(f"missing fields: {sorted(required - set(value))}")
    return value
```

Supporting declaration: `tools/subject_read_model_io.py::import@8`

```python
from __future__ import annotations
```

Supporting declaration: `tools/subject_read_model_io.py::import@10`

```python
import argparse
```

Supporting declaration: `tools/subject_read_model_io.py::import@11`

```python
import json
```

Supporting declaration: `tools/subject_read_model_io.py::import@12`

```python
import sys
```

Supporting declaration: `tools/subject_read_model_io.py::import@13`

```python
from collections.abc import Mapping
```

Supporting declaration: `tools/subject_read_model_io.py::import@14`

```python
from dataclasses import asdict
```

Supporting declaration: `tools/subject_read_model_io.py::import@15`

```python
from pathlib import Path
```

Supporting declaration: `tools/subject_read_model_io.py::import@17`

```python
from yaml import YAMLError
```

Supporting declaration: `tools/subject_read_model_io.py::import@19`

```python
from spec_yaml import load_yaml_text
```

Supporting declaration: `tools/subject_read_model_io.py::import@20`

```python
from subject_read_model import (
    CriterionNodeFields,
    CurrentSubjectDisposition,
    DispositionTransition,
    LookupResult,
    NodeProvenance,
    RelationEndpoint,
    RelationSource,
    RequirementNodeFields,
    RevisionSelection,
    SubjectClass,
    SubjectIndex,
    SubjectRecord,
    SubjectRef,
    SubjectRelation,
    SubjectRevision,
    WorkspaceSnapshot,
)
```

Supporting declaration: `tools/subject_read_model_io.py::_list`

```python
def _list(value: object) -> list:
    if not isinstance(value, list):
        raise SubjectDocumentError("expected a list")
    return value
```

Opportunity: ______  Concern kind: ______

Evidence / missing context: ______

## sg-045

[Pinned source](https://github.com/0al-spec/SpecGraph/blob/a5ab64363d054bae759b81441da6b79dbd4a9e86/tools/subject_read_model_io.py#L62-L71)

```python
def _require_string_trace_keys(value: object) -> None:
    """Reject YAML keys that JSON would rewrite, including in nested trace data."""
    if isinstance(value, Mapping):
        if any(not isinstance(key, str) for key in value):
            raise SubjectDocumentError("trace_context mappings must use string keys")
        for item in value.values():
            _require_string_trace_keys(item)
    elif isinstance(value, (list, tuple)):
        for item in value:
            _require_string_trace_keys(item)
```

Supporting declaration: `tools/subject_read_model_io.py::import@8`

```python
from __future__ import annotations
```

Supporting declaration: `tools/subject_read_model_io.py::import@10`

```python
import argparse
```

Supporting declaration: `tools/subject_read_model_io.py::import@11`

```python
import json
```

Supporting declaration: `tools/subject_read_model_io.py::import@12`

```python
import sys
```

Supporting declaration: `tools/subject_read_model_io.py::import@13`

```python
from collections.abc import Mapping
```

Supporting declaration: `tools/subject_read_model_io.py::import@14`

```python
from dataclasses import asdict
```

Supporting declaration: `tools/subject_read_model_io.py::import@15`

```python
from pathlib import Path
```

Supporting declaration: `tools/subject_read_model_io.py::import@17`

```python
from yaml import YAMLError
```

Supporting declaration: `tools/subject_read_model_io.py::import@19`

```python
from spec_yaml import load_yaml_text
```

Supporting declaration: `tools/subject_read_model_io.py::import@20`

```python
from subject_read_model import (
    CriterionNodeFields,
    CurrentSubjectDisposition,
    DispositionTransition,
    LookupResult,
    NodeProvenance,
    RelationEndpoint,
    RelationSource,
    RequirementNodeFields,
    RevisionSelection,
    SubjectClass,
    SubjectIndex,
    SubjectRecord,
    SubjectRef,
    SubjectRelation,
    SubjectRevision,
    WorkspaceSnapshot,
)
```

Supporting declaration: `tools/subject_read_model_io.py::_list`

```python
def _list(value: object) -> list:
    if not isinstance(value, list):
        raise SubjectDocumentError("expected a list")
    return value
```

Opportunity: ______  Concern kind: ______

Evidence / missing context: ______

## sg-046

[Pinned source](https://github.com/0al-spec/SpecGraph/blob/a5ab64363d054bae759b81441da6b79dbd4a9e86/tools/subject_read_model_io.py#L144-L159)

```python
def revision_payload(revision: SubjectRevision) -> dict:
    """Keep legacy exchange output stable; export source metadata without losing trace shape."""
    result = asdict(revision)
    if revision.node_fields is None:
        result.pop("node_fields")
        result.pop("revision_scope")
    elif isinstance(revision.node_fields, RequirementNodeFields):
        provenance = result["node_fields"]["provenance"]
        trace = provenance.pop("trace_context_json")
        supplied = provenance.pop("present_optional_fields") or ()
        for key in list(provenance):
            if provenance[key] is None and key not in supplied:
                provenance.pop(key)
        if trace is not None:
            provenance["trace_context"] = json.loads(trace)
    return result
```

Supporting declaration: `tools/subject_read_model_io.py::import@8`

```python
from __future__ import annotations
```

Supporting declaration: `tools/subject_read_model_io.py::import@10`

```python
import argparse
```

Supporting declaration: `tools/subject_read_model_io.py::import@11`

```python
import json
```

Supporting declaration: `tools/subject_read_model_io.py::import@12`

```python
import sys
```

Supporting declaration: `tools/subject_read_model_io.py::import@13`

```python
from collections.abc import Mapping
```

Supporting declaration: `tools/subject_read_model_io.py::import@14`

```python
from dataclasses import asdict
```

Supporting declaration: `tools/subject_read_model_io.py::import@15`

```python
from pathlib import Path
```

Supporting declaration: `tools/subject_read_model_io.py::import@17`

```python
from yaml import YAMLError
```

Supporting declaration: `tools/subject_read_model_io.py::import@19`

```python
from spec_yaml import load_yaml_text
```

Supporting declaration: `tools/subject_read_model_io.py::import@20`

```python
from subject_read_model import (
    CriterionNodeFields,
    CurrentSubjectDisposition,
    DispositionTransition,
    LookupResult,
    NodeProvenance,
    RelationEndpoint,
    RelationSource,
    RequirementNodeFields,
    RevisionSelection,
    SubjectClass,
    SubjectIndex,
    SubjectRecord,
    SubjectRef,
    SubjectRelation,
    SubjectRevision,
    WorkspaceSnapshot,
)
```

Supporting declaration: `tools/subject_read_model_io.py::_list`

```python
def _list(value: object) -> list:
    if not isinstance(value, list):
        raise SubjectDocumentError("expected a list")
    return value
```

Opportunity: ______  Concern kind: ______

Evidence / missing context: ______

## sg-047

[Pinned source](https://github.com/0al-spec/SpecGraph/blob/a5ab64363d054bae759b81441da6b79dbd4a9e86/tools/subject_source_write.py#L141-L185)

```python
def parse_write_request(value: object) -> SubjectSourceWriteRequest:
    data = _object(
        value,
        {
            "schema_version",
            "artifact_kind",
            "source_ref",
            "expected_commit",
            "recorded_at",
            "topology_selection",
            "expected_source_file_sha256",
            "changes",
        },
        {"workspace_declaration"},
    )
    _version(data, "subject_source_write_request")
    digests = data["expected_source_file_sha256"]
    if not isinstance(digests, dict):
        raise SubjectDocumentError("expected source digests must be a path/SHA256 mapping")
    changes = []
    for value in _list(data["changes"]):
        item = _object(value, {"operation", "path", "expected_prior_sha256", "proposed_record"})
        document = item["proposed_record"]
        if not isinstance(document, dict):
            raise SubjectDocumentError("proposed_record must be a mapping")
        changes.append(
            SubjectSourceChange(
                item["operation"],
                parse_subject_ref(document["subject"]),
                item["path"],
                dump_canonical_yaml(document),
                item["expected_prior_sha256"],
            )
        )
    return SubjectSourceWriteRequest(
        data["source_ref"],
        data["expected_commit"],
        data["recorded_at"],
        parse_topology_selection(data["topology_selection"]),
        tuple(sorted(digests.items())),
        tuple(changes),
        dump_canonical_yaml(data["workspace_declaration"])
        if "workspace_declaration" in data
        else None,
    )
```

Supporting declaration: `tools/subject_source_write.py::import@4`

```python
from __future__ import annotations
```

Supporting declaration: `tools/subject_source_write.py::import@6`

```python
import argparse
```

Supporting declaration: `tools/subject_source_write.py::import@7`

```python
import hashlib
```

Supporting declaration: `tools/subject_source_write.py::import@8`

```python
import json
```

Supporting declaration: `tools/subject_source_write.py::import@9`

```python
import re
```

Supporting declaration: `tools/subject_source_write.py::import@10`

```python
from dataclasses import asdict, dataclass, replace
```

Supporting declaration: `tools/subject_source_write.py::import@11`

```python
from datetime import datetime
```

Supporting declaration: `tools/subject_source_write.py::import@12`

```python
from pathlib import Path
```

Supporting declaration: `tools/subject_source_write.py::import@14`

```python
from yaml import YAMLError
```

Supporting declaration: `tools/subject_source_write.py::import@16`

```python
from spec_yaml import dump_canonical_yaml, load_yaml_text
```

Supporting declaration: `tools/subject_source_write.py::import@17`

```python
from subject_canonical_source import (
    DECLARATION,
    CanonicalTopologySelection,
    _storage_path,
    _version,
    parse_topology_selection,
    read_canonical_source,
)
```

Supporting declaration: `tools/subject_source_write.py::import@25`

```python
from subject_read_model import SubjectRecord, SubjectRef, require_text, require_tuple
```

Supporting declaration: `tools/subject_source_write.py::import@26`

```python
from subject_read_model_io import SubjectDocumentError, _list, _object, parse_subject_ref
```

Supporting declaration: `tools/subject_source_write.py::import@27`

```python
from subject_source_git import (
    SubjectSourceCommit,
    SubjectSourceConflict,
    require_commit_id,
    selected_source_commit,
)
```

Opportunity: ______  Concern kind: ______

Evidence / missing context: ______

## sg-048

[Pinned source](https://github.com/0al-spec/SpecGraph/blob/a5ab64363d054bae759b81441da6b79dbd4a9e86/tools/subject_source_write.py#L39-L41)

```python
def _require_digest(value: str) -> None:
    if not isinstance(value, str) or not re.fullmatch(r"[0-9a-f]{64}", value):
        raise SubjectDocumentError("source digest must be a complete lowercase SHA256")
```

Supporting declaration: `tools/subject_source_write.py::import@4`

```python
from __future__ import annotations
```

Supporting declaration: `tools/subject_source_write.py::import@6`

```python
import argparse
```

Supporting declaration: `tools/subject_source_write.py::import@7`

```python
import hashlib
```

Supporting declaration: `tools/subject_source_write.py::import@8`

```python
import json
```

Supporting declaration: `tools/subject_source_write.py::import@9`

```python
import re
```

Supporting declaration: `tools/subject_source_write.py::import@10`

```python
from dataclasses import asdict, dataclass, replace
```

Supporting declaration: `tools/subject_source_write.py::import@11`

```python
from datetime import datetime
```

Supporting declaration: `tools/subject_source_write.py::import@12`

```python
from pathlib import Path
```

Supporting declaration: `tools/subject_source_write.py::import@14`

```python
from yaml import YAMLError
```

Supporting declaration: `tools/subject_source_write.py::import@16`

```python
from spec_yaml import dump_canonical_yaml, load_yaml_text
```

Supporting declaration: `tools/subject_source_write.py::import@17`

```python
from subject_canonical_source import (
    DECLARATION,
    CanonicalTopologySelection,
    _storage_path,
    _version,
    parse_topology_selection,
    read_canonical_source,
)
```

Supporting declaration: `tools/subject_source_write.py::import@25`

```python
from subject_read_model import SubjectRecord, SubjectRef, require_text, require_tuple
```

Supporting declaration: `tools/subject_source_write.py::import@26`

```python
from subject_read_model_io import SubjectDocumentError, _list, _object, parse_subject_ref
```

Supporting declaration: `tools/subject_source_write.py::import@27`

```python
from subject_source_git import (
    SubjectSourceCommit,
    SubjectSourceConflict,
    require_commit_id,
    selected_source_commit,
)
```

Opportunity: ______  Concern kind: ______

Evidence / missing context: ______

## sg-049

[Pinned source](https://github.com/0al-spec/SpecGraph/blob/a5ab64363d054bae759b81441da6b79dbd4a9e86/tools/idea_to_spec_promotion_gate.py#L138-L142)

```python
def _promotion_path_allowed(path: str) -> bool:
    normalized = path.replace("\\", "/")
    if normalized.startswith("/") or "/../" in f"/{normalized}/":
        return False
    return any(normalized.startswith(prefix) for prefix in PROMOTION_PATH_PREFIXES)
```

Supporting declaration: `tools/idea_to_spec_promotion_gate.py::import@3`

```python
from __future__ import annotations
```

Supporting declaration: `tools/idea_to_spec_promotion_gate.py::import@5`

```python
import argparse
```

Supporting declaration: `tools/idea_to_spec_promotion_gate.py::import@6`

```python
import json
```

Supporting declaration: `tools/idea_to_spec_promotion_gate.py::import@7`

```python
import sys
```

Supporting declaration: `tools/idea_to_spec_promotion_gate.py::import@8`

```python
from dataclasses import dataclass
```

Supporting declaration: `tools/idea_to_spec_promotion_gate.py::import@9`

```python
from datetime import datetime, timezone
```

Supporting declaration: `tools/idea_to_spec_promotion_gate.py::import@10`

```python
from enum import Enum
```

Supporting declaration: `tools/idea_to_spec_promotion_gate.py::import@11`

```python
from pathlib import Path
```

Supporting declaration: `tools/idea_to_spec_promotion_gate.py::import@12`

```python
from typing import Any
```

Supporting declaration: `tools/idea_to_spec_promotion_gate.py::import@14`

```python
from specification_core import FirstMatch, PredicateSpec, TraceRecorder
```

Supporting declaration: `tools/idea_to_spec_promotion_gate.py::_dict`

```python
def _dict(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}
```

Supporting declaration: `tools/idea_to_spec_promotion_gate.py::_list`

```python
def _list(value: Any) -> list[Any]:
    return value if isinstance(value, list) else []
```

Supporting declaration: `tools/idea_to_spec_promotion_gate.py::_text`

```python
def _text(value: Any, default: str = "") -> str:
    return value.strip() if isinstance(value, str) and value.strip() else default
```

Supporting declaration: `tools/idea_to_spec_promotion_gate.py::_text_list`

```python
def _text_list(value: Any) -> list[str]:
    return [item.strip() for item in _list(value) if isinstance(item, str) and item.strip()]
```

Supporting declaration: `tools/idea_to_spec_promotion_gate.py::_readiness_ready`

```python
def _readiness_ready(artifact: dict[str, Any]) -> bool:
    return _dict(artifact.get("readiness")).get("ready") is True
```

Opportunity: ______  Concern kind: ______

Evidence / missing context: ______

## sg-050

[Pinned source](https://github.com/0al-spec/SpecGraph/blob/a5ab64363d054bae759b81441da6b79dbd4a9e86/tools/candidate_approval_decision.py#L155-L161)

```python
def _promotion_path_allowed(value: object) -> bool:
    if not isinstance(value, str) or not value.strip():
        return False
    path = value.strip().replace("\\", "/")
    if path.startswith("/") or "/../" in f"/{path}/" or "/./" in f"/{path}/":
        return False
    return any(path.startswith(prefix) for prefix in PROMOTION_PATH_PREFIXES)
```

Supporting declaration: `tools/candidate_approval_decision.py::import@3`

```python
from __future__ import annotations
```

Supporting declaration: `tools/candidate_approval_decision.py::import@5`

```python
import argparse
```

Supporting declaration: `tools/candidate_approval_decision.py::import@6`

```python
import hashlib
```

Supporting declaration: `tools/candidate_approval_decision.py::import@7`

```python
import json
```

Supporting declaration: `tools/candidate_approval_decision.py::import@8`

```python
import re
```

Supporting declaration: `tools/candidate_approval_decision.py::import@9`

```python
from datetime import datetime, timezone
```

Supporting declaration: `tools/candidate_approval_decision.py::import@10`

```python
from pathlib import Path
```

Supporting declaration: `tools/candidate_approval_decision.py::import@11`

```python
from typing import Any
```

Supporting declaration: `tools/candidate_approval_decision.py::_dict`

```python
def _dict(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}
```

Supporting declaration: `tools/candidate_approval_decision.py::_list`

```python
def _list(value: Any) -> list[Any]:
    return value if isinstance(value, list) else []
```

Supporting declaration: `tools/candidate_approval_decision.py::_text`

```python
def _text(value: Any, default: str = "") -> str:
    return value.strip() if isinstance(value, str) and value.strip() else default
```

Supporting declaration: `tools/candidate_approval_decision.py::_readiness_ready`

```python
def _readiness_ready(artifact: dict[str, Any]) -> bool:
    return _dict(artifact.get("readiness")).get("ready") is True
```

Opportunity: ______  Concern kind: ______

Evidence / missing context: ______

## sg-051

[Pinned source](https://github.com/0al-spec/SpecGraph/blob/a5ab64363d054bae759b81441da6b79dbd4a9e86/tools/candidate_approval_decision.py#L241-L328)

```python
def _validate_active_candidate(
    active_candidate: dict[str, Any],
    *,
    active_candidate_path: Path,
) -> list[dict[str, Any]]:
    findings: list[dict[str, Any]] = _input_path_findings(
        path=active_candidate_path,
        field="active_candidate",
        label="Active candidate source",
    )
    if active_candidate.get("artifact_kind") != "active_idea_to_spec_candidate":
        findings.append(
            _finding(
                finding_id="active_candidate_wrong_artifact_kind",
                severity="review_required",
                message="Approval requires an active_idea_to_spec_candidate artifact.",
                evidence={"artifact_kind": active_candidate.get("artifact_kind")},
            )
        )
    if active_candidate.get("contract_ref") != ACTIVE_CANDIDATE_CONTRACT_REF:
        findings.append(
            _finding(
                finding_id="active_candidate_contract_ref_unsupported",
                severity="review_required",
                message="Approval requires the active candidate source contract.",
                evidence={"contract_ref": active_candidate.get("contract_ref")},
            )
        )
    if active_candidate.get("canonical_mutations_allowed") is not False:
        findings.append(
            _finding(
                finding_id="active_candidate_authority_expanded",
                severity="review_required",
                message="Active candidate source must not allow canonical mutations.",
            )
        )
    if active_candidate.get("tracked_artifacts_written") is not False:
        findings.append(
            _finding(
                finding_id="active_candidate_tracked_write_expanded",
                severity="review_required",
                message="Active candidate source must be review-only.",
            )
        )
    if active_candidate.get("source_mode") != "active_candidate":
        findings.append(
            _finding(
                finding_id="active_candidate_source_mode_unsupported",
                severity="review_required",
                message="Approval requires a real active candidate source.",
                evidence={"source_mode": active_candidate.get("source_mode")},
            )
        )
    if not _readiness_ready(active_candidate):
        findings.append(
            _finding(
                finding_id="active_candidate_not_ready",
                severity="review_required",
                message="Active candidate source must be ready before approval.",
                evidence={"readiness": _dict(active_candidate.get("readiness"))},
            )
        )
    candidate = _dict(active_candidate.get("candidate"))
    expected = {
        "workflow_lane": "product_idea_to_spec",
        "governance_profile": "product_workspace",
        "target_repository_role": "product_spec_workspace",
    }
    for field, expected_value in expected.items():
        observed = candidate.get(field)
        if observed != expected_value:
            findings.append(
                _finding(
                    finding_id=f"active_candidate_{field}_unsupported",
                    severity="review_required",
                    message=f"Approval requires candidate {field}={expected_value!r}.",
                    evidence={"expected": expected_value, "observed": observed},
                )
            )
    if not _text(candidate.get("candidate_id")):
        findings.append(
            _finding(
                finding_id="active_candidate_candidate_id_missing",
                severity="review_required",
                message="Approval requires a stable candidate_id.",
            )
        )
    return findings
```

Supporting declaration: `tools/candidate_approval_decision.py::import@3`

```python
from __future__ import annotations
```

Supporting declaration: `tools/candidate_approval_decision.py::import@5`

```python
import argparse
```

Supporting declaration: `tools/candidate_approval_decision.py::import@6`

```python
import hashlib
```

Supporting declaration: `tools/candidate_approval_decision.py::import@7`

```python
import json
```

Supporting declaration: `tools/candidate_approval_decision.py::import@8`

```python
import re
```

Supporting declaration: `tools/candidate_approval_decision.py::import@9`

```python
from datetime import datetime, timezone
```

Supporting declaration: `tools/candidate_approval_decision.py::import@10`

```python
from pathlib import Path
```

Supporting declaration: `tools/candidate_approval_decision.py::import@11`

```python
from typing import Any
```

Supporting declaration: `tools/candidate_approval_decision.py::_dict`

```python
def _dict(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}
```

Supporting declaration: `tools/candidate_approval_decision.py::_list`

```python
def _list(value: Any) -> list[Any]:
    return value if isinstance(value, list) else []
```

Supporting declaration: `tools/candidate_approval_decision.py::_text`

```python
def _text(value: Any, default: str = "") -> str:
    return value.strip() if isinstance(value, str) and value.strip() else default
```

Supporting declaration: `tools/candidate_approval_decision.py::_readiness_ready`

```python
def _readiness_ready(artifact: dict[str, Any]) -> bool:
    return _dict(artifact.get("readiness")).get("ready") is True
```

Opportunity: ______  Concern kind: ______

Evidence / missing context: ______

## sg-052

[Pinned source](https://github.com/0al-spec/SpecGraph/blob/a5ab64363d054bae759b81441da6b79dbd4a9e86/tools/evidence_claim_gate.py#L121-L170)

```python
def source_claim_reason(claim, passport, resolution):
    """Interpret only the upstream pinned Swift source-resolution contract."""
    spec = passport["spec"]
    criteria = passport_criterion_ids(passport)
    requested = set(claim["passport_criterion_ids"])
    if not requested <= criteria:
        return "unknown_passport_criterion"
    implementation = spec.get("implementation", {})
    bindings = implementation.get("bindings", [])
    relevant = [b for b in bindings if requested & set(b["acceptance_criteria_ids"])]
    covered = {c for b in relevant for c in b["acceptance_criteria_ids"]}
    if not requested <= covered:
        return "missing_criterion_binding"
    required_elements = {
        e for b in relevant for e in b["element_ids"] + b.get("test_element_ids", [])
    }
    elements = implementation.get("elements", [])
    by_id = {e["id"]: e for e in elements}
    if len(by_id) != len(elements) or not required_elements or not required_elements <= set(by_id):
        return "invalid_element_binding"
    if resolution.get("validation_issues") != []:
        return "passport_validation_failed"
    anchors = resolution.get("anchors")
    if not isinstance(anchors, list) or not anchors:
        return "missing_source_evidence"
    observed = {}
    for anchor in anchors:
        if not isinstance(anchor, dict):
            return "malformed_source_evidence"
        key = (anchor.get("element_id"), anchor.get("anchor_index"))
        if not isinstance(key[0], str) or type(key[1]) is not int or key in observed:
            return "ambiguous_source_evidence"
        observed[key] = anchor
    expected_keys = {(e["id"], i) for e in elements for i, _ in enumerate(e["anchors"])}
    if set(observed) != expected_keys:
        return "incomplete_or_extra_source_evidence"
    for element_id in sorted(required_elements):
        expected = by_id[element_id]["anchors"]
        if not expected:
            return "missing_source_anchors"
        for index, authored in enumerate(expected):
            actual = observed[(element_id, index)]
            fields = ("repository", "revision", "module", "path", "symbol")
            if any(actual.get(field) != authored[field] for field in fields):
                return "source_identity_mismatch"
            if actual.get("status") != "resolved":
                return "source_unresolved"
            if not re.fullmatch(r"[a-fA-F0-9]{40}|[a-fA-F0-9]{64}", actual.get("blob_oid", "")):
                return "missing_blob_identity"
    return None
```

Supporting declaration: `tools/evidence_claim_gate.py::import@3`

```python
from __future__ import annotations
```

Supporting declaration: `tools/evidence_claim_gate.py::import@5`

```python
import argparse
```

Supporting declaration: `tools/evidence_claim_gate.py::import@6`

```python
import hashlib
```

Supporting declaration: `tools/evidence_claim_gate.py::import@7`

```python
import json
```

Supporting declaration: `tools/evidence_claim_gate.py::import@8`

```python
import os
```

Supporting declaration: `tools/evidence_claim_gate.py::import@9`

```python
import re
```

Supporting declaration: `tools/evidence_claim_gate.py::import@10`

```python
import selectors
```

Supporting declaration: `tools/evidence_claim_gate.py::import@11`

```python
import signal
```

Supporting declaration: `tools/evidence_claim_gate.py::import@12`

```python
import stat
```

Supporting declaration: `tools/evidence_claim_gate.py::import@13`

```python
import subprocess
```

Supporting declaration: `tools/evidence_claim_gate.py::import@14`

```python
import tempfile
```

Supporting declaration: `tools/evidence_claim_gate.py::import@15`

```python
import time
```

Supporting declaration: `tools/evidence_claim_gate.py::import@16`

```python
from pathlib import Path
```

Opportunity: ______  Concern kind: ______

Evidence / missing context: ______

## sg-053

[Pinned source](https://github.com/0al-spec/SpecGraph/blob/a5ab64363d054bae759b81441da6b79dbd4a9e86/tools/evidence_claim_gate.py#L338-L429)

```python
def _validate_runtime_decision(
    decision, mapping, passport_raw, policy_raw, bundle_raw, receipt_trust_raw, bundle
):
    fields = {
        "artifact_kind",
        "schema_version",
        "decision_profile",
        "decision_digest",
        "decision",
        "feature_id",
        "passport_id",
        "passport_version",
        "claim_id",
        "claim_policy_id",
        "claim_policy_version",
        "claim_policy_digest",
        "predicate_profile",
        "evaluation_time",
        "passport_digest",
        "bundle_digest",
        "receipt_trust_store_digest",
        "pair_digests",
        "issuer",
        "signature",
    }
    if not isinstance(decision, dict) or set(decision) != fields:
        raise ValueError("invalid signed aggregate decision fields")
    if (
        decision["artifact_kind"] != "aggregate_claim_decision"
        or type(decision["schema_version"]) is not int
        or decision["schema_version"] != 1
        or decision["decision_profile"] != "fp-aggregate-decision-v1-fields"
    ):
        raise ValueError("unsupported signed decision profile")
    for field in (
        "decision_digest",
        "passport_digest",
        "bundle_digest",
        "receipt_trust_store_digest",
    ):
        if not isinstance(decision[field], str) or not re.fullmatch(
            r"sha256:[0-9a-f]{64}", decision[field]
        ):
            raise ValueError(f"invalid signed decision digest: {field}")
    if decision["passport_digest"] != prefixed_digest(passport_raw):
        raise ValueError("signed decision passport digest mismatch")
    if decision["bundle_digest"] != prefixed_digest(bundle_raw):
        raise ValueError("signed decision bundle digest mismatch")
    if decision["claim_policy_digest"] != prefixed_digest(policy_raw):
        raise ValueError("signed decision claim policy digest mismatch")
    if decision["receipt_trust_store_digest"] != prefixed_digest(receipt_trust_raw):
        raise ValueError("signed decision receipt trust store digest mismatch")
    identity_fields = {
        "feature_id": "feature_id",
        "passport_id": "passport_id",
        "passport_version": "passport_version",
        "claim_id": "claim_id",
        "claim_policy_id": "claim_policy_id",
        "claim_policy_version": "claim_policy_version",
        "claim_policy_digest": "claim_policy_digest",
        "predicate_profile": "predicate_profile",
    }
    if any(decision[source] != mapping[target] for source, target in identity_fields.items()):
        raise ValueError("signed decision identity does not match canonical declaration")
    issuer = decision["issuer"]
    if (
        not isinstance(issuer, dict)
        or set(issuer) != {"authority_id", "key_id"}
        or any(issuer[field] != mapping[field] for field in ("authority_id", "key_id"))
    ):
        raise ValueError("signed decision authority does not match canonical declaration")
    signature = decision["signature"]
    if (
        not isinstance(signature, dict)
        or set(signature) != {"algorithm", "profile", "value"}
        or not all(nonempty(value) for value in signature.values())
    ):
        raise ValueError("invalid signed decision signature envelope")
    if not nonempty(decision["evaluation_time"]) or decision["decision"] not in {
        "accepted",
        "not_satisfied",
    }:
        raise ValueError("invalid signed decision verdict")
    pairs = bundle.get("pairs") if isinstance(bundle, dict) else None
    pair_digests = decision["pair_digests"]
    if (
        not isinstance(pairs, list)
        or not isinstance(pair_digests, list)
        or len(pairs) != len(pair_digests)
    ):
        raise ValueError("signed decision pair list does not match bundle")
    return decision
```

Supporting declaration: `tools/evidence_claim_gate.py::import@3`

```python
from __future__ import annotations
```

Supporting declaration: `tools/evidence_claim_gate.py::import@5`

```python
import argparse
```

Supporting declaration: `tools/evidence_claim_gate.py::import@6`

```python
import hashlib
```

Supporting declaration: `tools/evidence_claim_gate.py::import@7`

```python
import json
```

Supporting declaration: `tools/evidence_claim_gate.py::import@8`

```python
import os
```

Supporting declaration: `tools/evidence_claim_gate.py::import@9`

```python
import re
```

Supporting declaration: `tools/evidence_claim_gate.py::import@10`

```python
import selectors
```

Supporting declaration: `tools/evidence_claim_gate.py::import@11`

```python
import signal
```

Supporting declaration: `tools/evidence_claim_gate.py::import@12`

```python
import stat
```

Supporting declaration: `tools/evidence_claim_gate.py::import@13`

```python
import subprocess
```

Supporting declaration: `tools/evidence_claim_gate.py::import@14`

```python
import tempfile
```

Supporting declaration: `tools/evidence_claim_gate.py::import@15`

```python
import time
```

Supporting declaration: `tools/evidence_claim_gate.py::import@16`

```python
from pathlib import Path
```

Opportunity: ______  Concern kind: ______

Evidence / missing context: ______

## sg-054

[Pinned source](https://github.com/0al-spec/SpecGraph/blob/a5ab64363d054bae759b81441da6b79dbd4a9e86/tools/subject_source_write.py#L217-L244)

```python
def _check_transition(
    change: SubjectSourceChange, before: SubjectRecord | None, after: SubjectRecord
):
    if change.operation == "origin":
        if before is not None:
            raise SubjectSourceConflict("origin subject already exists")
        if (
            len(after.revisions) != 1
            or len(after.disposition_history) != 1
            or (after.disposition_history[0].transition != "activation")
        ):
            raise SubjectDocumentError("origin requires revision 1 and one activation event")
    else:
        if before is None:
            raise SubjectDocumentError("content revision requires an existing subject")
        if (
            after.revisions[:-1] != before.revisions
            or after.current_revision != before.current_revision + 1
        ):
            raise SubjectDocumentError(
                "content revision must append exactly one revision; history is immutable"
            )
        if after.revisions[-1].containment != before.revisions[-1].containment:
            raise SubjectDocumentError("containment_move is unsupported by the first writer")
        if after.current_disposition != before.current_disposition or (
            after.disposition_history != before.disposition_history
        ):
            raise SubjectDocumentError("disposition changes are unsupported by the first writer")
```

Supporting declaration: `tools/subject_source_write.py::import@4`

```python
from __future__ import annotations
```

Supporting declaration: `tools/subject_source_write.py::import@6`

```python
import argparse
```

Supporting declaration: `tools/subject_source_write.py::import@7`

```python
import hashlib
```

Supporting declaration: `tools/subject_source_write.py::import@8`

```python
import json
```

Supporting declaration: `tools/subject_source_write.py::import@9`

```python
import re
```

Supporting declaration: `tools/subject_source_write.py::import@10`

```python
from dataclasses import asdict, dataclass, replace
```

Supporting declaration: `tools/subject_source_write.py::import@11`

```python
from datetime import datetime
```

Supporting declaration: `tools/subject_source_write.py::import@12`

```python
from pathlib import Path
```

Supporting declaration: `tools/subject_source_write.py::import@14`

```python
from yaml import YAMLError
```

Supporting declaration: `tools/subject_source_write.py::import@16`

```python
from spec_yaml import dump_canonical_yaml, load_yaml_text
```

Supporting declaration: `tools/subject_source_write.py::import@17`

```python
from subject_canonical_source import (
    DECLARATION,
    CanonicalTopologySelection,
    _storage_path,
    _version,
    parse_topology_selection,
    read_canonical_source,
)
```

Supporting declaration: `tools/subject_source_write.py::import@25`

```python
from subject_read_model import SubjectRecord, SubjectRef, require_text, require_tuple
```

Supporting declaration: `tools/subject_source_write.py::import@26`

```python
from subject_read_model_io import SubjectDocumentError, _list, _object, parse_subject_ref
```

Supporting declaration: `tools/subject_source_write.py::import@27`

```python
from subject_source_git import (
    SubjectSourceCommit,
    SubjectSourceConflict,
    require_commit_id,
    selected_source_commit,
)
```

Opportunity: ______  Concern kind: ______

Evidence / missing context: ______

## sg-055

[Pinned source](https://github.com/0al-spec/SpecGraph/blob/a5ab64363d054bae759b81441da6b79dbd4a9e86/tools/idea_maturity_metrics_report.py#L1382-L1401)

```python
def _lifecycle_state_from_metrics_fragment(artifacts: dict[str, dict[str, Any]]) -> str:
    if _read_model_publication_state(artifacts) == "published":
        return "read_model_publication_complete"
    if _review_status(artifacts) in {"open", "merged"}:
        return "git_review_active"
    if _promotion_request_state(artifacts) == "requested":
        return "promotion_requested"
    if _candidate_approval_decision_state(artifacts) == "materialized":
        return "approval_materialized"
    if _candidate_approval_state(artifacts) == "ready":
        return "approval_ready"
    if artifacts.get("repaired_repair_session") or artifacts.get("repaired_handoff"):
        return "repaired_candidate_ready"
    if artifacts.get("specspace_rerun_request") or artifacts.get("rerun_input"):
        return "repair_rerun_requested"
    if artifacts.get("candidate_graph") or artifacts.get("clarification_requests"):
        return "repair_required"
    if artifacts.get("intake"):
        return "intake_ready"
    return "blocked"
```

Supporting declaration: `tools/idea_maturity_metrics_report.py::import@3`

```python
from __future__ import annotations
```

Supporting declaration: `tools/idea_maturity_metrics_report.py::import@5`

```python
import argparse
```

Supporting declaration: `tools/idea_maturity_metrics_report.py::import@6`

```python
import json
```

Supporting declaration: `tools/idea_maturity_metrics_report.py::import@7`

```python
import re
```

Supporting declaration: `tools/idea_maturity_metrics_report.py::import@8`

```python
import sys
```

Supporting declaration: `tools/idea_maturity_metrics_report.py::import@9`

```python
from collections import Counter
```

Supporting declaration: `tools/idea_maturity_metrics_report.py::import@10`

```python
from datetime import datetime, timezone
```

Supporting declaration: `tools/idea_maturity_metrics_report.py::import@11`

```python
from pathlib import Path
```

Supporting declaration: `tools/idea_maturity_metrics_report.py::import@12`

```python
from typing import Any
```

Supporting declaration: `tools/idea_maturity_metrics_report.py::import@14`

```python
from idea_maturity_candidate_approval_decision_spec import (
    candidate_approval_decision_state as _candidate_approval_decision_state_spec,
)
```

Supporting declaration: `tools/idea_maturity_metrics_report.py::import@17`

```python
from idea_maturity_candidate_approval_intent_spec import (
    candidate_approval_intent_state as _candidate_approval_intent_state_spec,
)
```

Supporting declaration: `tools/idea_maturity_metrics_report.py::import@20`

```python
from idea_maturity_candidate_approval_spec import (
    candidate_approval_state as _candidate_approval_state_spec,
)
```

Supporting declaration: `tools/idea_maturity_metrics_report.py::import@23`

```python
from idea_maturity_lifecycle_context import (
    LifecycleStateContext,
    _dict,
    _int,
    _status_is_blocked,
    _status_is_failed,
    _summary,
    _text,
)
```

Supporting declaration: `tools/idea_maturity_metrics_report.py::import@32`

```python
from idea_maturity_lifecycle_state_set import lifecycle_state_values
```

Supporting declaration: `tools/idea_maturity_metrics_report.py::import@33`

```python
from idea_maturity_platform_promotion_spec import (
    platform_promotion_state as _platform_promotion_state_spec,
)
```

Supporting declaration: `tools/idea_maturity_metrics_report.py::import@36`

```python
from idea_maturity_promotion_execution_spec import (
    promotion_execution_state as _promotion_execution_state_spec,
)
```

Supporting declaration: `tools/idea_maturity_metrics_report.py::import@39`

```python
from idea_maturity_promotion_request_spec import (
    promotion_request_state as _promotion_request_state_spec,
)
```

Supporting declaration: `tools/idea_maturity_metrics_report.py::import@42`

```python
from idea_maturity_read_model_publication_spec import (
    read_model_publication_state as _read_model_publication_state_spec,
)
```

Supporting declaration: `tools/idea_maturity_metrics_report.py::import@45`

```python
from idea_maturity_review_spec import review_status as _review_status_spec
```

Supporting declaration: `tools/idea_maturity_metrics_report.py::_list`

```python
def _list(value: Any) -> list[Any]:
    return value if isinstance(value, list) else []
```

Supporting declaration: `tools/idea_maturity_metrics_report.py::_text_list`

```python
def _text_list(value: Any) -> list[str]:
    if isinstance(value, str) and value.strip():
        return [value.strip()]
    if not isinstance(value, list):
        return []
    return [item.strip() for item in value if isinstance(item, str) and item.strip()]
```

Opportunity: ______  Concern kind: ______

Evidence / missing context: ______

## sg-056

[Pinned source](https://github.com/0al-spec/SpecGraph/blob/a5ab64363d054bae759b81441da6b79dbd4a9e86/tools/idea_maturity_metrics_report.py#L2292-L2341)

```python
def _derived_state(
    metrics: dict[str, Any], policy_findings: list[dict[str, Any]]
) -> dict[str, Any]:
    if metrics["read_model_publication_state"] == "published":
        lifecycle_state = "read_model_publication_complete"
    elif metrics["review_status"] in {"open", "merged"}:
        lifecycle_state = "git_review_active"
    elif metrics["promotion_request_state"] == "requested":
        lifecycle_state = "promotion_requested"
    elif metrics["candidate_approval_decision_state"] == "materialized":
        lifecycle_state = "approval_materialized"
    elif metrics["candidate_approval_state"] == "ready":
        lifecycle_state = "approval_ready"
    elif metrics["rerun_request_count"] > 0:
        lifecycle_state = "repair_rerun_requested"
    elif (
        metrics["candidate_node_count"] > 0
        and metrics["clarification_question_count"] > 0
        and metrics["candidate_gap_unresolved_count"] == 0
        and metrics["ontology_gap_unresolved_count"] == 0
    ):
        lifecycle_state = "repaired_candidate_ready"
    elif (
        metrics["candidate_gap_count_initial"] > 0
        or metrics["ontology_gap_count_initial"] > 0
        or metrics["clarification_question_count"] > 0
    ):
        lifecycle_state = "repair_required"
    elif metrics["candidate_node_count"] > 0:
        lifecycle_state = "intake_ready"
    else:
        lifecycle_state = "blocked" if policy_findings else "intake_ready"

    blockers = [
        finding["finding_id"]
        for finding in policy_findings
        if finding.get("severity") in {"high", "medium"}
    ]
    if metrics["remaining_blocker_count"] > 0 and "remaining_blockers" not in blockers:
        blockers.append("remaining_blockers")
    return {
        "lifecycle_state": "blocked"
        if blockers and lifecycle_state == "unknown"
        else lifecycle_state,
        "blockers": blockers,
        "candidate_approval_state": metrics["candidate_approval_state"],
        "platform_promotion_state": metrics["platform_promotion_state"],
        "review_status": metrics["review_status"],
        "read_model_publication_state": metrics["read_model_publication_state"],
    }
```

Supporting declaration: `tools/idea_maturity_metrics_report.py::import@3`

```python
from __future__ import annotations
```

Supporting declaration: `tools/idea_maturity_metrics_report.py::import@5`

```python
import argparse
```

Supporting declaration: `tools/idea_maturity_metrics_report.py::import@6`

```python
import json
```

Supporting declaration: `tools/idea_maturity_metrics_report.py::import@7`

```python
import re
```

Supporting declaration: `tools/idea_maturity_metrics_report.py::import@8`

```python
import sys
```

Supporting declaration: `tools/idea_maturity_metrics_report.py::import@9`

```python
from collections import Counter
```

Supporting declaration: `tools/idea_maturity_metrics_report.py::import@10`

```python
from datetime import datetime, timezone
```

Supporting declaration: `tools/idea_maturity_metrics_report.py::import@11`

```python
from pathlib import Path
```

Supporting declaration: `tools/idea_maturity_metrics_report.py::import@12`

```python
from typing import Any
```

Supporting declaration: `tools/idea_maturity_metrics_report.py::import@14`

```python
from idea_maturity_candidate_approval_decision_spec import (
    candidate_approval_decision_state as _candidate_approval_decision_state_spec,
)
```

Supporting declaration: `tools/idea_maturity_metrics_report.py::import@17`

```python
from idea_maturity_candidate_approval_intent_spec import (
    candidate_approval_intent_state as _candidate_approval_intent_state_spec,
)
```

Supporting declaration: `tools/idea_maturity_metrics_report.py::import@20`

```python
from idea_maturity_candidate_approval_spec import (
    candidate_approval_state as _candidate_approval_state_spec,
)
```

Supporting declaration: `tools/idea_maturity_metrics_report.py::import@23`

```python
from idea_maturity_lifecycle_context import (
    LifecycleStateContext,
    _dict,
    _int,
    _status_is_blocked,
    _status_is_failed,
    _summary,
    _text,
)
```

Supporting declaration: `tools/idea_maturity_metrics_report.py::import@32`

```python
from idea_maturity_lifecycle_state_set import lifecycle_state_values
```

Supporting declaration: `tools/idea_maturity_metrics_report.py::import@33`

```python
from idea_maturity_platform_promotion_spec import (
    platform_promotion_state as _platform_promotion_state_spec,
)
```

Supporting declaration: `tools/idea_maturity_metrics_report.py::import@36`

```python
from idea_maturity_promotion_execution_spec import (
    promotion_execution_state as _promotion_execution_state_spec,
)
```

Supporting declaration: `tools/idea_maturity_metrics_report.py::import@39`

```python
from idea_maturity_promotion_request_spec import (
    promotion_request_state as _promotion_request_state_spec,
)
```

Supporting declaration: `tools/idea_maturity_metrics_report.py::import@42`

```python
from idea_maturity_read_model_publication_spec import (
    read_model_publication_state as _read_model_publication_state_spec,
)
```

Supporting declaration: `tools/idea_maturity_metrics_report.py::import@45`

```python
from idea_maturity_review_spec import review_status as _review_status_spec
```

Supporting declaration: `tools/idea_maturity_metrics_report.py::_list`

```python
def _list(value: Any) -> list[Any]:
    return value if isinstance(value, list) else []
```

Supporting declaration: `tools/idea_maturity_metrics_report.py::_text_list`

```python
def _text_list(value: Any) -> list[str]:
    if isinstance(value, str) and value.strip():
        return [value.strip()]
    if not isinstance(value, list):
        return []
    return [item.strip() for item in value if isinstance(item, str) and item.strip()]
```

Opportunity: ______  Concern kind: ______

Evidence / missing context: ______

## sg-057

[Pinned source](https://github.com/0al-spec/SpecGraph/blob/a5ab64363d054bae759b81441da6b79dbd4a9e86/tools/idea_maturity_metrics_report.py#L339-L348)

```python
def _public_safe(value: Any) -> Any:
    if isinstance(value, dict):
        return {
            key: _public_safe(item)
            for key, item in value.items()
            if isinstance(key, str) and key not in RAW_TRACE_FIELDS and not key.startswith("raw_")
        }
    if isinstance(value, list):
        return [_public_safe(item) for item in value]
    return value
```

Supporting declaration: `tools/idea_maturity_metrics_report.py::import@3`

```python
from __future__ import annotations
```

Supporting declaration: `tools/idea_maturity_metrics_report.py::import@5`

```python
import argparse
```

Supporting declaration: `tools/idea_maturity_metrics_report.py::import@6`

```python
import json
```

Supporting declaration: `tools/idea_maturity_metrics_report.py::import@7`

```python
import re
```

Supporting declaration: `tools/idea_maturity_metrics_report.py::import@8`

```python
import sys
```

Supporting declaration: `tools/idea_maturity_metrics_report.py::import@9`

```python
from collections import Counter
```

Supporting declaration: `tools/idea_maturity_metrics_report.py::import@10`

```python
from datetime import datetime, timezone
```

Supporting declaration: `tools/idea_maturity_metrics_report.py::import@11`

```python
from pathlib import Path
```

Supporting declaration: `tools/idea_maturity_metrics_report.py::import@12`

```python
from typing import Any
```

Supporting declaration: `tools/idea_maturity_metrics_report.py::import@14`

```python
from idea_maturity_candidate_approval_decision_spec import (
    candidate_approval_decision_state as _candidate_approval_decision_state_spec,
)
```

Supporting declaration: `tools/idea_maturity_metrics_report.py::import@17`

```python
from idea_maturity_candidate_approval_intent_spec import (
    candidate_approval_intent_state as _candidate_approval_intent_state_spec,
)
```

Supporting declaration: `tools/idea_maturity_metrics_report.py::import@20`

```python
from idea_maturity_candidate_approval_spec import (
    candidate_approval_state as _candidate_approval_state_spec,
)
```

Supporting declaration: `tools/idea_maturity_metrics_report.py::import@23`

```python
from idea_maturity_lifecycle_context import (
    LifecycleStateContext,
    _dict,
    _int,
    _status_is_blocked,
    _status_is_failed,
    _summary,
    _text,
)
```

Supporting declaration: `tools/idea_maturity_metrics_report.py::import@32`

```python
from idea_maturity_lifecycle_state_set import lifecycle_state_values
```

Supporting declaration: `tools/idea_maturity_metrics_report.py::import@33`

```python
from idea_maturity_platform_promotion_spec import (
    platform_promotion_state as _platform_promotion_state_spec,
)
```

Supporting declaration: `tools/idea_maturity_metrics_report.py::import@36`

```python
from idea_maturity_promotion_execution_spec import (
    promotion_execution_state as _promotion_execution_state_spec,
)
```

Supporting declaration: `tools/idea_maturity_metrics_report.py::import@39`

```python
from idea_maturity_promotion_request_spec import (
    promotion_request_state as _promotion_request_state_spec,
)
```

Supporting declaration: `tools/idea_maturity_metrics_report.py::import@42`

```python
from idea_maturity_read_model_publication_spec import (
    read_model_publication_state as _read_model_publication_state_spec,
)
```

Supporting declaration: `tools/idea_maturity_metrics_report.py::import@45`

```python
from idea_maturity_review_spec import review_status as _review_status_spec
```

Supporting declaration: `tools/idea_maturity_metrics_report.py::_list`

```python
def _list(value: Any) -> list[Any]:
    return value if isinstance(value, list) else []
```

Supporting declaration: `tools/idea_maturity_metrics_report.py::_text_list`

```python
def _text_list(value: Any) -> list[str]:
    if isinstance(value, str) and value.strip():
        return [value.strip()]
    if not isinstance(value, list):
        return []
    return [item.strip() for item in value if isinstance(item, str) and item.strip()]
```

Supporting declaration: `tools/idea_maturity_metrics_report.py::_seconds_between`

```python
def _seconds_between(start: datetime | None, end: datetime | None) -> float | None:
    if start is None or end is None:
        return None
    seconds = (end - start).total_seconds()
    if seconds < 0:
        return None
    return round(seconds, 3)
```

Opportunity: ______  Concern kind: ______

Evidence / missing context: ______

## sg-058

[Pinned source](https://github.com/0al-spec/SpecGraph/blob/a5ab64363d054bae759b81441da6b79dbd4a9e86/tools/idea_maturity_metrics_report.py#L1714-L1724)

```python
def _selected_artifact_key(
    artifacts: dict[str, dict[str, Any]],
    *,
    preferred: str,
    fallback: str,
) -> str | None:
    if artifacts.get(preferred):
        return preferred
    if artifacts.get(fallback):
        return fallback
    return None
```

Supporting declaration: `tools/idea_maturity_metrics_report.py::import@3`

```python
from __future__ import annotations
```

Supporting declaration: `tools/idea_maturity_metrics_report.py::import@5`

```python
import argparse
```

Supporting declaration: `tools/idea_maturity_metrics_report.py::import@6`

```python
import json
```

Supporting declaration: `tools/idea_maturity_metrics_report.py::import@7`

```python
import re
```

Supporting declaration: `tools/idea_maturity_metrics_report.py::import@8`

```python
import sys
```

Supporting declaration: `tools/idea_maturity_metrics_report.py::import@9`

```python
from collections import Counter
```

Supporting declaration: `tools/idea_maturity_metrics_report.py::import@10`

```python
from datetime import datetime, timezone
```

Supporting declaration: `tools/idea_maturity_metrics_report.py::import@11`

```python
from pathlib import Path
```

Supporting declaration: `tools/idea_maturity_metrics_report.py::import@12`

```python
from typing import Any
```

Supporting declaration: `tools/idea_maturity_metrics_report.py::import@14`

```python
from idea_maturity_candidate_approval_decision_spec import (
    candidate_approval_decision_state as _candidate_approval_decision_state_spec,
)
```

Supporting declaration: `tools/idea_maturity_metrics_report.py::import@17`

```python
from idea_maturity_candidate_approval_intent_spec import (
    candidate_approval_intent_state as _candidate_approval_intent_state_spec,
)
```

Supporting declaration: `tools/idea_maturity_metrics_report.py::import@20`

```python
from idea_maturity_candidate_approval_spec import (
    candidate_approval_state as _candidate_approval_state_spec,
)
```

Supporting declaration: `tools/idea_maturity_metrics_report.py::import@23`

```python
from idea_maturity_lifecycle_context import (
    LifecycleStateContext,
    _dict,
    _int,
    _status_is_blocked,
    _status_is_failed,
    _summary,
    _text,
)
```

Supporting declaration: `tools/idea_maturity_metrics_report.py::import@32`

```python
from idea_maturity_lifecycle_state_set import lifecycle_state_values
```

Supporting declaration: `tools/idea_maturity_metrics_report.py::import@33`

```python
from idea_maturity_platform_promotion_spec import (
    platform_promotion_state as _platform_promotion_state_spec,
)
```

Supporting declaration: `tools/idea_maturity_metrics_report.py::import@36`

```python
from idea_maturity_promotion_execution_spec import (
    promotion_execution_state as _promotion_execution_state_spec,
)
```

Supporting declaration: `tools/idea_maturity_metrics_report.py::import@39`

```python
from idea_maturity_promotion_request_spec import (
    promotion_request_state as _promotion_request_state_spec,
)
```

Supporting declaration: `tools/idea_maturity_metrics_report.py::import@42`

```python
from idea_maturity_read_model_publication_spec import (
    read_model_publication_state as _read_model_publication_state_spec,
)
```

Supporting declaration: `tools/idea_maturity_metrics_report.py::import@45`

```python
from idea_maturity_review_spec import review_status as _review_status_spec
```

Supporting declaration: `tools/idea_maturity_metrics_report.py::_list`

```python
def _list(value: Any) -> list[Any]:
    return value if isinstance(value, list) else []
```

Supporting declaration: `tools/idea_maturity_metrics_report.py::_text_list`

```python
def _text_list(value: Any) -> list[str]:
    if isinstance(value, str) and value.strip():
        return [value.strip()]
    if not isinstance(value, list):
        return []
    return [item.strip() for item in value if isinstance(item, str) and item.strip()]
```

Supporting declaration: `tools/idea_maturity_metrics_report.py::_seconds_between`

```python
def _seconds_between(start: datetime | None, end: datetime | None) -> float | None:
    if start is None or end is None:
        return None
    seconds = (end - start).total_seconds()
    if seconds < 0:
        return None
    return round(seconds, 3)
```

Opportunity: ______  Concern kind: ______

Evidence / missing context: ______

## sg-059

[Pinned source](https://github.com/0al-spec/SpecGraph/blob/a5ab64363d054bae759b81441da6b79dbd4a9e86/tools/idea_maturity_metrics_report.py#L1341-L1361)

```python
def _phase_dwell_seconds(
    phases: list[tuple[str, datetime]],
    *,
    lifecycle_state: str,
    blocked_or_open: bool,
) -> dict[str, float]:
    if not phases:
        return {}
    dwell: dict[str, float] = {}
    for index, (phase, timestamp) in enumerate(phases):
        next_timestamp = phases[index + 1][1] if index + 1 < len(phases) else None
        seconds = _seconds_between(timestamp, next_timestamp)
        if seconds is not None:
            dwell[phase] = seconds
    last_phase, last_timestamp = phases[-1]
    if blocked_or_open or last_phase == lifecycle_state:
        now = datetime.now(tz=timezone.utc)
        seconds = _seconds_between(last_timestamp, now)
        if seconds is not None:
            dwell[last_phase] = max(dwell.get(last_phase, 0), seconds)
    return dwell
```

Supporting declaration: `tools/idea_maturity_metrics_report.py::import@3`

```python
from __future__ import annotations
```

Supporting declaration: `tools/idea_maturity_metrics_report.py::import@5`

```python
import argparse
```

Supporting declaration: `tools/idea_maturity_metrics_report.py::import@6`

```python
import json
```

Supporting declaration: `tools/idea_maturity_metrics_report.py::import@7`

```python
import re
```

Supporting declaration: `tools/idea_maturity_metrics_report.py::import@8`

```python
import sys
```

Supporting declaration: `tools/idea_maturity_metrics_report.py::import@9`

```python
from collections import Counter
```

Supporting declaration: `tools/idea_maturity_metrics_report.py::import@10`

```python
from datetime import datetime, timezone
```

Supporting declaration: `tools/idea_maturity_metrics_report.py::import@11`

```python
from pathlib import Path
```

Supporting declaration: `tools/idea_maturity_metrics_report.py::import@12`

```python
from typing import Any
```

Supporting declaration: `tools/idea_maturity_metrics_report.py::import@14`

```python
from idea_maturity_candidate_approval_decision_spec import (
    candidate_approval_decision_state as _candidate_approval_decision_state_spec,
)
```

Supporting declaration: `tools/idea_maturity_metrics_report.py::import@17`

```python
from idea_maturity_candidate_approval_intent_spec import (
    candidate_approval_intent_state as _candidate_approval_intent_state_spec,
)
```

Supporting declaration: `tools/idea_maturity_metrics_report.py::import@20`

```python
from idea_maturity_candidate_approval_spec import (
    candidate_approval_state as _candidate_approval_state_spec,
)
```

Supporting declaration: `tools/idea_maturity_metrics_report.py::import@23`

```python
from idea_maturity_lifecycle_context import (
    LifecycleStateContext,
    _dict,
    _int,
    _status_is_blocked,
    _status_is_failed,
    _summary,
    _text,
)
```

Supporting declaration: `tools/idea_maturity_metrics_report.py::import@32`

```python
from idea_maturity_lifecycle_state_set import lifecycle_state_values
```

Supporting declaration: `tools/idea_maturity_metrics_report.py::import@33`

```python
from idea_maturity_platform_promotion_spec import (
    platform_promotion_state as _platform_promotion_state_spec,
)
```

Supporting declaration: `tools/idea_maturity_metrics_report.py::import@36`

```python
from idea_maturity_promotion_execution_spec import (
    promotion_execution_state as _promotion_execution_state_spec,
)
```

Supporting declaration: `tools/idea_maturity_metrics_report.py::import@39`

```python
from idea_maturity_promotion_request_spec import (
    promotion_request_state as _promotion_request_state_spec,
)
```

Supporting declaration: `tools/idea_maturity_metrics_report.py::import@42`

```python
from idea_maturity_read_model_publication_spec import (
    read_model_publication_state as _read_model_publication_state_spec,
)
```

Supporting declaration: `tools/idea_maturity_metrics_report.py::import@45`

```python
from idea_maturity_review_spec import review_status as _review_status_spec
```

Supporting declaration: `tools/idea_maturity_metrics_report.py::_list`

```python
def _list(value: Any) -> list[Any]:
    return value if isinstance(value, list) else []
```

Supporting declaration: `tools/idea_maturity_metrics_report.py::_text_list`

```python
def _text_list(value: Any) -> list[str]:
    if isinstance(value, str) and value.strip():
        return [value.strip()]
    if not isinstance(value, list):
        return []
    return [item.strip() for item in value if isinstance(item, str) and item.strip()]
```

Supporting declaration: `tools/idea_maturity_metrics_report.py::_seconds_between`

```python
def _seconds_between(start: datetime | None, end: datetime | None) -> float | None:
    if start is None or end is None:
        return None
    seconds = (end - start).total_seconds()
    if seconds < 0:
        return None
    return round(seconds, 3)
```

Opportunity: ______  Concern kind: ______

Evidence / missing context: ______

## sg-060

[Pinned source](https://github.com/0al-spec/SpecGraph/blob/a5ab64363d054bae759b81441da6b79dbd4a9e86/tools/repaired_candidate_promotion_handoff.py#L208-L262)

```python
def _candidate_graph_preview(
    rerun_materialization: dict[str, Any],
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    findings: list[dict[str, Any]] = []
    preview = _dict(
        _dict(rerun_materialization.get("materialization_preview")).get("candidate_graph_preview")
    )
    if not preview:
        findings.append(
            _finding(
                finding_id="candidate_graph_preview_missing",
                severity="review_required",
                message="Rerun materialization must contain a candidate_graph_preview.",
            )
        )
        return {}, findings
    if preview.get("artifact_kind") != "candidate_spec_graph":
        findings.append(
            _finding(
                finding_id="candidate_graph_preview_wrong_artifact_kind",
                severity="review_required",
                message="Nested repaired preview must be a candidate_spec_graph.",
                evidence={"artifact_kind": preview.get("artifact_kind")},
            )
        )
    if preview.get("contract_ref") != CANDIDATE_GRAPH_CONTRACT_REF:
        findings.append(
            _finding(
                finding_id="candidate_graph_preview_contract_ref_unsupported",
                severity="review_required",
                message=(
                    f"Nested candidate graph contract_ref must be {CANDIDATE_GRAPH_CONTRACT_REF}."
                ),
                evidence={"contract_ref": preview.get("contract_ref")},
            )
        )
    for field in ("canonical_mutations_allowed", "tracked_artifacts_written"):
        if preview.get(field) is not False:
            findings.append(
                _finding(
                    finding_id="candidate_graph_preview_authority_expanded",
                    severity="review_required",
                    message=f"Nested candidate graph {field} must be false.",
                    evidence={field: preview.get(field)},
                )
            )
    if not _list(preview.get("nodes")):
        findings.append(
            _finding(
                finding_id="candidate_graph_preview_nodes_missing",
                severity="review_required",
                message="Nested repaired candidate graph must contain candidate nodes.",
            )
        )
    return preview, findings
```

Supporting declaration: `tools/repaired_candidate_promotion_handoff.py::import@3`

```python
from __future__ import annotations
```

Supporting declaration: `tools/repaired_candidate_promotion_handoff.py::import@5`

```python
import argparse
```

Supporting declaration: `tools/repaired_candidate_promotion_handoff.py::import@6`

```python
import copy
```

Supporting declaration: `tools/repaired_candidate_promotion_handoff.py::import@7`

```python
import json
```

Supporting declaration: `tools/repaired_candidate_promotion_handoff.py::import@8`

```python
import sys
```

Supporting declaration: `tools/repaired_candidate_promotion_handoff.py::import@9`

```python
from datetime import datetime, timezone
```

Supporting declaration: `tools/repaired_candidate_promotion_handoff.py::import@10`

```python
from pathlib import Path
```

Supporting declaration: `tools/repaired_candidate_promotion_handoff.py::import@11`

```python
from typing import Any
```

Supporting declaration: `tools/repaired_candidate_promotion_handoff.py::import@17`

```python
import active_idea_to_spec_candidate_source  # noqa: E402
```

Supporting declaration: `tools/repaired_candidate_promotion_handoff.py::import@18`

```python
import candidate_repair_loop  # noqa: E402
```

Supporting declaration: `tools/repaired_candidate_promotion_handoff.py::import@19`

```python
import candidate_spec_materialization  # noqa: E402
```

Supporting declaration: `tools/repaired_candidate_promotion_handoff.py::import@20`

```python
import idea_to_spec_promotion_gate  # noqa: E402
```

Supporting declaration: `tools/repaired_candidate_promotion_handoff.py::import@21`

```python
import idea_to_spec_repair_session_journal  # noqa: E402
```

Supporting declaration: `tools/repaired_candidate_promotion_handoff.py::import@22`

```python
import pre_sib_coherence_report  # noqa: E402
```

Supporting declaration: `tools/repaired_candidate_promotion_handoff.py::_dict`

```python
def _dict(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}
```

Supporting declaration: `tools/repaired_candidate_promotion_handoff.py::_list`

```python
def _list(value: Any) -> list[Any]:
    return value if isinstance(value, list) else []
```

Supporting declaration: `tools/repaired_candidate_promotion_handoff.py::_text`

```python
def _text(value: Any, default: str = "") -> str:
    return value.strip() if isinstance(value, str) and value.strip() else default
```

Opportunity: ______  Concern kind: ______

Evidence / missing context: ______
