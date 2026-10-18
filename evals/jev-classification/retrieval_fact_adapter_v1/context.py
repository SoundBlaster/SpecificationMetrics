from dataclasses import dataclass

from recommendation_policy_v1.context import Kind, Ownership, Support, Tool


@dataclass(frozen=True)
class NativeProposal:
    role: Kind
    support: Support
    ownership: Ownership
    tool: Tool
