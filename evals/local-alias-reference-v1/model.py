"""Independent, offline reference model; never executes inspected Python."""

import ast
from dataclasses import dataclass
import io
import tokenize


CONTRACT = "specification-metrics.local-alias-flow-contract/v1-draft"
DEFAULT_LIMITS = {"max_tracked_names": 8, "max_following_named_sibling_nodes": 64}


@dataclass(frozen=True)
class Operation:
    kind: str
    anchor: dict
    target: str | None = None
    source: str | None = None
    projection: str | None = None
    reason: str | None = None


class Machine:
    """One origin, monotonically growing name history, one terminal outcome."""

    def __init__(self, variable, projection, origin_id, limits=None):
        self.limits = dict(DEFAULT_LIMITS if limits is None else limits)
        if set(self.limits) != set(DEFAULT_LIMITS) or any(
            type(v) is not int or v < 1 for v in self.limits.values()
        ):
            raise ValueError("positive integer limits required")
        if projection not in ("raw", "value", "matched"):
            raise ValueError("invalid origin projection")
        self.origin_id = origin_id
        self.projection = projection
        self.states = {variable: "origin"}
        self.events = []
        self.visited = 0
        self.outcome = None
        self.consumer = None

    def halt(self, status, reason, stop, reference=None):
        self.outcome = {
            "status": status,
            "reason": reason,
            "stop": stop,
            "reference": reference,
        }
        return self.outcome

    def step(self, op):
        if self.outcome is not None:
            raise ValueError("cannot step a terminal machine")
        self.visited += 1
        if self.visited > self.limits["max_following_named_sibling_nodes"]:
            return self.halt("unresolved", "statement_limit", op.anchor)
        if op.kind == "noop":
            return None
        if op.kind == "copy":
            state = self.states.get(op.source)
            if state == "deleted":
                return self.halt("unresolved", "alias_copy_source_deleted", op.anchor)
            if state is None:
                return self.halt(
                    "unresolved", "intervening_expression_barrier", op.anchor
                )
            if (
                op.target not in self.states
                and len(self.states) >= self.limits["max_tracked_names"]
            ):
                return self.halt("unresolved", "alias_name_limit", op.anchor)
        elif op.kind == "literal":
            if op.target not in self.states:
                return None
            state = "other"
        elif op.kind == "delete":
            if self.states.get(op.target) in (None, "deleted"):
                return self.halt("unresolved", "deletion_state_unproven", op.anchor)
            state = "deleted"
        elif op.kind == "guard":
            if (
                self.projection == "raw"
                and op.projection not in ("value", "matched")
                or self.projection != "raw"
                and op.projection != self.projection
            ):
                return self.halt(
                    "unresolved", "condition_or_control_flow_unsupported", op.anchor
                )
            state = self.states.get(op.target)
            if state is None:
                return self.halt(
                    "unresolved", "condition_or_control_flow_unsupported", op.anchor
                )
            self.consumer = {
                "name": op.target,
                "state": state,
                "projection": op.projection,
                "anchor": op.anchor,
            }
            status, reason = {
                "origin": ("linked", "local_alias_read"),
                "other": ("not_linked", "branch_reference_rebound"),
                "deleted": ("not_linked", "branch_reference_deleted"),
            }[state]
            return self.halt(
                status, reason, op.anchor, {"name": op.target, "state": state}
            )
        else:
            return self.halt(
                "unresolved", op.reason or "intervening_expression_barrier", op.anchor
            )
        before = {op.target: self.states.get(op.target)}
        if op.source is not None:
            before[op.source] = self.states.get(op.source)
        self.states[op.target] = state
        self.events.append(
            {
                "kind": op.kind,
                "anchor": op.anchor,
                "source": op.source,
                "target": op.target,
                "before": before,
                "after": {op.target: state},
            }
        )
        return None

    def finish(self):
        if self.outcome is None:
            self.halt("not_linked", "no_supported_branch_before_scope_end", None)
        return {
            "outcome": self.outcome,
            "evidence": {
                "contract": CONTRACT,
                "origin_token": self.origin_id,
                "origin_projection": self.projection,
                "limits": self.limits,
                "visited_nodes": self.visited,
                "states": dict(self.states),
                "events": self.events,
                "consumer_reference": self.consumer,
            },
        }


def anchor(node):
    kind = {
        ast.Assign: "expression_statement",
        ast.AnnAssign: "expression_statement",
        ast.AugAssign: "expression_statement",
        ast.Expr: "expression_statement",
        ast.If: "if_statement",
        ast.Delete: "delete_statement",
        ast.Pass: "pass_statement",
        ast.Return: "return_statement",
        ast.Raise: "raise_statement",
        ast.Assert: "assert_statement",
        ast.FunctionDef: "function_definition",
        ast.AsyncFunctionDef: "function_definition",
        ast.ClassDef: "class_definition",
        ast.For: "for_statement",
        ast.While: "while_statement",
    }.get(type(node), "unsupported_statement")
    return {"line": node.lineno, "column": node.col_offset + 1, "syntax_kind": kind}


def literal(node):
    return isinstance(node, ast.Constant) and (
        node.value is None or type(node.value) in (bool, int, float, str, bytes)
    )


def reference(node, names, projection):
    if isinstance(node, ast.Name) and node.id in names and projection != "raw":
        return node.id, projection
    if (
        projection == "raw"
        and isinstance(node, ast.Attribute)
        and isinstance(node.value, ast.Name)
        and node.value.id in names
        and node.attr in ("value", "matched")
    ):
        return node.value.id, node.attr
    return None


def condition(node, names, projection, enum_facts):
    if isinstance(node, ast.UnaryOp) and isinstance(node.op, ast.Not):
        return condition(node.operand, names, projection, enum_facts)
    direct = reference(node, names, projection)
    if direct:
        return direct
    if not isinstance(node, ast.Compare):
        return None
    found = []
    enums = []
    for operand in [node.left, *node.comparators]:
        ref = reference(operand, names, projection)
        if ref:
            found.append(ref)
        elif literal(operand):
            continue
        elif (
            isinstance(operand, ast.Attribute)
            and isinstance(operand.value, ast.Name)
            and operand.value.id not in names
            and (operand.value.id, operand.attr) in enum_facts
        ):
            enums.append((operand.value.id, operand.attr))
        else:
            return None
    if len(found) != 1:
        return None
    if enums and (
        len(enums) != 1
        or len(node.ops) != 1
        or not isinstance(node.ops[0], (ast.Eq, ast.NotEq, ast.Is, ast.IsNot))
    ):
        return None
    return found[0]


def scope_directive(nodes):
    for node in nodes:
        if isinstance(node, (ast.Global, ast.Nonlocal)):
            return True
        if isinstance(
            node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef, ast.Lambda)
        ):
            continue
        if scope_directive(ast.iter_child_nodes(node)):
            return True
    return False


def source_range(code, node):
    lines = code.splitlines(keepends=True)
    offsets = [0]
    for line in lines:
        offsets.append(offsets[-1] + len(line.encode()))
    return offsets[node.lineno - 1] + node.col_offset, offsets[
        node.end_lineno - 1
    ] + node.end_col_offset


def exact_rhs(code, assignment):
    """AST removes parentheses; reject those not in plain-copy/literal syntax."""
    start, end = source_range(code, assignment)
    segment = code.encode()[start:end].decode()
    tokens = [
        t
        for t in tokenize.generate_tokens(io.StringIO(segment).readline)
        if t.type
        not in (tokenize.NL, tokenize.NEWLINE, tokenize.ENDMARKER, tokenize.COMMENT)
    ]
    equal = next(
        i for i, t in enumerate(tokens) if t.type == tokenize.OP and t.string == "="
    )
    rhs = tokens[equal + 1 :]
    return bool(rhs) and rhs[0].string != "(" and rhs[-1].string != ")"


def operation(code, node, machine, enum_facts):
    at = anchor(node)

    def barrier(reason):
        return Operation("barrier", at, reason=reason)

    if isinstance(node, ast.Pass):
        return Operation("noop", at)
    if isinstance(node, ast.If):
        ref = condition(node.test, machine.states, machine.projection, enum_facts)
        return (
            Operation("guard", at, target=ref[0], projection=ref[1])
            if ref
            else barrier("condition_or_control_flow_unsupported")
        )
    if isinstance(node, ast.AugAssign):
        return barrier("object_mutation_barrier")
    if isinstance(node, (ast.Assign, ast.AnnAssign, ast.Delete)):
        targets = (
            node.targets
            if isinstance(node, (ast.Assign, ast.Delete))
            else [node.target]
        )
        if any(
            isinstance(n, (ast.Attribute, ast.Subscript))
            for t in targets
            for n in ast.walk(t)
        ):
            return barrier("object_mutation_barrier")
        if isinstance(node, ast.AnnAssign):
            return (
                Operation("noop", at)
                if isinstance(node.target, ast.Name) and node.value is None
                else barrier("intervening_expression_barrier")
            )
        if len(targets) != 1 or not isinstance(targets[0], ast.Name):
            return barrier("intervening_expression_barrier")
        target = targets[0].id
        if isinstance(node, ast.Delete):
            return Operation("delete", at, target=target)
        if not exact_rhs(code, node):
            return barrier("intervening_expression_barrier")
        if isinstance(node.value, ast.Name):
            return Operation("copy", at, target=target, source=node.value.id)
        if literal(node.value):
            return Operation("literal", at, target=target)
        return barrier("intervening_expression_barrier")
    if isinstance(node, ast.Expr):
        return barrier("intervening_expression_barrier")
    return barrier("control_flow_or_effect_barrier")


def following_nodes(code, owner, siblings):
    """Include direct sibling comments, including trailing inline comments."""
    following = siblings[siblings.index(owner) + 1 :]
    lines = code.splitlines()
    end = len(lines) + 1
    for lineno in range(owner.end_lineno + 1, len(lines) + 1):
        text = lines[lineno - 1]
        if not text.strip() or text.lstrip().startswith("#"):
            continue
        if any(s.lineno <= lineno <= s.end_lineno for s in following):
            continue
        if len(text) - len(text.lstrip()) < owner.col_offset:
            end = lineno
            break
    comments = []
    for token in tokenize.generate_tokens(io.StringIO(code).readline):
        line, column = token.start
        position = (
            line,
            len(lines[line - 1][:column].encode()) if line <= len(lines) else column,
        )
        inside_statement = any(
            (s.lineno, s.col_offset) <= position < (s.end_lineno, s.end_col_offset)
            for s in [owner, *following]
        )
        if (
            token.type == tokenize.COMMENT
            and (owner.end_lineno, owner.end_col_offset) <= position
            and line < end
            and column >= owner.col_offset
            and not inside_statement
        ):
            comments.append(
                {
                    "line": line,
                    "column": len(lines[line - 1][:column].encode()) + 1,
                    "syntax_kind": "comment",
                }
            )
    return sorted(
        [*following, *comments],
        key=lambda n: (n["line"], n["column"])
        if isinstance(n, dict)
        else (n.lineno, n.col_offset + 1),
    )


def analyze(
    code,
    origin_anchor,
    projection,
    *,
    origin_id,
    origin_proven,
    enum_facts=(),
    limits=None,
):
    """Origin/enum proofs are supplied preconditions, never inferred by spelling."""
    tree = ast.parse(code)
    parents = {
        child: node for node in ast.walk(tree) for child in ast.iter_child_nodes(node)
    }
    call = next(
        (
            n
            for n in ast.walk(tree)
            if isinstance(n, ast.Call)
            and (n.lineno, n.col_offset + 1)
            == (origin_anchor["line"], origin_anchor["column"])
        ),
        None,
    )
    if call is None:
        raise ValueError("origin call anchor unavailable")
    value = call
    actual_projection = "raw"
    parent = parents.get(value)
    if isinstance(parent, ast.Attribute) and parent.attr in ("value", "matched"):
        actual_projection, value = parent.attr, parent
    if actual_projection != projection:
        raise ValueError("supplied projection disagrees with source")
    owner = parents.get(value)
    if not isinstance(owner, (ast.Assign, ast.AnnAssign)) or owner.value is not value:
        raise ValueError("origin is not an immediate assignment")
    targets = owner.targets if isinstance(owner, ast.Assign) else [owner.target]
    if len(targets) != 1 or not isinstance(targets[0], ast.Name):
        raise ValueError("single origin identifier required")
    machine = Machine(targets[0].id, projection, origin_id, limits)
    gate = None
    if not origin_proven:
        gate = "firstmatch_binding_not_proven"
    block_owner, child = parents.get(owner), owner
    while gate is None:
        if (
            isinstance(block_owner, (ast.FunctionDef, ast.AsyncFunctionDef))
            and child in block_owner.body
        ):
            if scope_directive(block_owner.body):
                gate = "global_or_nonlocal_scope"
            break
        if isinstance(block_owner, (ast.For, ast.While)) and child in block_owner.body:
            child, block_owner = block_owner, parents.get(block_owner)
            continue
        gate = (
            "function_body_required"
            if isinstance(block_owner, (ast.Module, ast.ClassDef))
            else "straight_line_function_body_required"
        )
    if gate:
        machine.halt("unresolved", gate, None)
        return machine.finish()
    siblings = parents[owner].body
    for node in following_nodes(code, owner, siblings):
        op = (
            Operation("noop", node)
            if isinstance(node, dict)
            else operation(code, node, machine, enum_facts)
        )
        if machine.step(op) is not None:
            break
    return machine.finish()
