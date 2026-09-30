"""End-to-end evaluation runner tests (Phase 4): the real graph/runtime
with the LLM mocked -- proving the full Dataset -> Runner -> NexusRuntime
-> Structured Run Data -> Evaluators -> Result -> Summary pipeline, and
thread isolation between evaluation cases/runs and normal sessions.
"""

import pytest

import access
import main
import run_store
import runtime as nexus_runtime
from evals import evaluator
from evals.models import EvaluationCase, EvaluationDataset


class _FakeMessage:
    def __init__(self, content):
        self.content = content


@pytest.fixture(autouse=True)
def _fake_llm_calls(monkeypatch):
    # Route by input text so different cases can exercise different routes
    # deterministically.
    def fake_classify(messages):
        text = messages[-1]["content"]
        if "reverse" in text:
            return main.MessageClassifier(message_type="coding")
        if "overwhelmed" in text:
            return main.MessageClassifier(message_type="emotional")
        return main.MessageClassifier(message_type="math")

    monkeypatch.setattr(main, "_call_classifier", fake_classify)
    monkeypatch.setattr(main, "_call_llm", lambda messages: _FakeMessage("391 is the answer"))


def _dataset(*cases: EvaluationCase) -> EvaluationDataset:
    return EvaluationDataset(name="test-dataset", version="1.0.0", cases=list(cases))


async def test_run_evaluation_produces_a_summary_and_results(tmp_path):
    ds = _dataset(
        EvaluationCase(id="math-1", name="Math", input="what is 17*23?", expected_route="math"),
        EvaluationCase(id="code-1", name="Code", input="reverse a string", expected_route="coding"),
    )
    db_path = str(tmp_path / "t.sqlite")
    async with nexus_runtime.create_runtime(main.graph_builder, checkpoint_db=db_path) as rt:
        store = run_store.RunStore()
        run = await evaluator.run_evaluation(rt, ds, store)

    assert run.summary.total_cases == 2
    assert run.summary.passed_cases == 2
    assert len(run.results) == 2
    assert {r.case_id for r in run.results} == {"math-1", "code-1"}


async def test_wrong_route_is_detected_as_a_failure(tmp_path):
    ds = _dataset(
        EvaluationCase(id="math-1", name="Math", input="what is 17*23?", expected_route="coding"),
    )
    db_path = str(tmp_path / "t.sqlite")
    async with nexus_runtime.create_runtime(main.graph_builder, checkpoint_db=db_path) as rt:
        store = run_store.RunStore()
        run = await evaluator.run_evaluation(rt, ds, store)

    assert run.summary.failed_cases == 1
    assert run.results[0].passed is False
    routing_dim = [d for d in run.results[0].dimensions if d.dimension == "routing"][0]
    assert routing_dim.passed is False


async def test_each_case_gets_its_own_isolated_thread(tmp_path):
    ds = _dataset(
        EvaluationCase(id="math-1", name="Math", input="what is 17*23?"),
        EvaluationCase(id="code-1", name="Code", input="reverse a string"),
    )
    db_path = str(tmp_path / "t.sqlite")
    async with nexus_runtime.create_runtime(main.graph_builder, checkpoint_db=db_path) as rt:
        store = run_store.RunStore()
        run = await evaluator.run_evaluation(rt, ds, store, evaluation_id="eval-iso-test")

    thread_ids = {r.thread_id for r in run.results}
    assert thread_ids == {"eval-eval-iso-test-math-1", "eval-eval-iso-test-code-1"}
    assert len(thread_ids) == 2  # never shared between cases


async def test_eval_thread_ids_never_collide_with_normal_session_ids():
    normal_id = nexus_runtime.new_thread_id()
    eval_id = evaluator.eval_thread_id("eval-1", "case-1")
    assert not eval_id.startswith("thread-")
    assert eval_id.startswith("eval-")
    assert eval_id != normal_id


async def test_evaluation_does_not_contaminate_a_normal_session(tmp_path):
    ds = _dataset(EvaluationCase(id="math-1", name="Math", input="what is 17*23?"))
    db_path = str(tmp_path / "t.sqlite")
    async with nexus_runtime.create_runtime(main.graph_builder, checkpoint_db=db_path) as rt:
        # A normal CLI-style session, untouched by evaluation.
        normal_thread = nexus_runtime.new_thread_id()
        await rt.execute(normal_thread, "hello there", principal_id=access.LOCAL_CLI_PRINCIPAL)

        store = run_store.RunStore()
        await evaluator.run_evaluation(rt, ds, store, evaluation_id="eval-contamination-test")

        normal_state = await rt.get_state(normal_thread, principal_id=access.LOCAL_CLI_PRINCIPAL)
        contents = [m.content for m in normal_state.values["messages"]]

    assert "hello there" in contents
    assert "what is 17*23?" not in contents  # eval traffic never lands in the normal thread


async def test_two_separate_evaluation_runs_are_isolated_from_each_other(tmp_path):
    ds = _dataset(EvaluationCase(id="math-1", name="Math", input="what is 17*23?"))
    db_path = str(tmp_path / "t.sqlite")
    async with nexus_runtime.create_runtime(main.graph_builder, checkpoint_db=db_path) as rt:
        store = run_store.RunStore()
        run_a = await evaluator.run_evaluation(rt, ds, store)  # fresh evaluation_id each time
        run_b = await evaluator.run_evaluation(rt, ds, store)

    assert run_a.evaluation_id != run_b.evaluation_id
    assert run_a.results[0].thread_id != run_b.results[0].thread_id


async def test_rerun_case_executes_independently_of_the_original_run(tmp_path):
    case = EvaluationCase(id="math-1", name="Math", input="what is 17*23?")
    db_path = str(tmp_path / "t.sqlite")
    async with nexus_runtime.create_runtime(main.graph_builder, checkpoint_db=db_path) as rt:
        store = run_store.RunStore()
        first = await evaluator.run_case(rt, "eval-1", case, store)
        rerun = await evaluator.rerun_case(rt, case, store)

    assert first.request_id != rerun.request_id
    assert first.thread_id != rerun.thread_id  # a re-run is a fresh execution, not a resume
