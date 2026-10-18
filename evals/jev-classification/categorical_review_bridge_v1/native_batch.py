"""One caller-owned System One batch, projected through the public SDK API."""
from dataclasses import replace

from mellea_jev import (
    CategoricalCapabilities, CategoricalTask, TypeSafeProvider, project_choice_results,
)


class NativeBatchCategoricalProvider:
    """Borrow a TypeSafeProvider without closing it or splitting its questions.

    Calling classify can perform inference. The caller owns authorization,
    capture, budgets and provider lifetime; this class adds no retry/fallback.
    """

    capabilities = CategoricalCapabilities(False, True, True)

    def __init__(self, provider: TypeSafeProvider):
        if not isinstance(provider, TypeSafeProvider):
            raise TypeError('native batching requires a TypeSafeProvider')
        self.provider = provider

    def classify(self, task: CategoricalTask):
        if not isinstance(task, CategoricalTask):
            raise TypeError('classify requires a CategoricalTask')
        requested_model = self.provider.model
        response = self.provider.system_one(state=task.state, questions=task.questions)
        return replace(project_choice_results(task, response.answers,
            requested_model=requested_model, request_id=response.request_id, usage=response.usage),
            adapter_revision='specmetrics.typesafe-batch-categorical/v1')
