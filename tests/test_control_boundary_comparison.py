import asyncio

import pytest

from agents import Agent, Runner, function_tool
from agents.testing import ModelStep, ScriptedModel, assistant_message, function_call

from app.adapters.mock_payment import MockPaymentProvider, ProviderTimeoutAfterEffect
from app.models import OperationStatus, Request
from app.storage.memory import InMemoryStore
from app.workflow import ControlledRouter


def _scripted_refund_agent(effects):
    @function_tool(name_override="issue_refund", needs_approval=True)
    def issue_refund(order_id: str, amount: float) -> str:
        effects.append((order_id, amount))
        return "refund-created"

    model = ScriptedModel(
        [
            ModelStep(
                output=[
                    function_call(
                        "issue_refund",
                        {"order_id": "1002", "amount": 800},
                        call_id="refund-compare-1",
                    )
                ]
            ),
            ModelStep(output=[assistant_message("Refund completed.")]),
        ]
    )
    return Agent(
        name="SDK comparison agent",
        instructions="Call issue_refund for refund requests.",
        model=model,
        tools=[issue_refund],
    )


@pytest.mark.asyncio
async def test_compare_current_router_and_sdk_approval_for_rejection():
    router = ControlledRouter(InMemoryStore(), MockPaymentProvider())
    op = await router.submit(
        Request(request_id="compare-router-reject", raw_text="Please refund order #1002 for $800.")
    )
    assert op.status == OperationStatus.PENDING_APPROVAL

    rejected = router.approve(op.operation_id, False)
    assert rejected.status == OperationStatus.REJECTED
    assert router.provider.refund_calls == 0

    effects = []
    agent = _scripted_refund_agent(effects)
    paused = await Runner.run(agent, "Refund order 1002 for $800.")
    assert len(paused.interruptions) == 1
    assert effects == []

    state = paused.to_state()
    state.reject(paused.interruptions[0])
    resumed = await Runner.run(agent, state)

    assert effects == []
    assert "completed" in resumed.final_output.lower()


@pytest.mark.asyncio
async def test_compare_current_router_and_sdk_for_approved_effect():
    router_provider = MockPaymentProvider()
    router = ControlledRouter(InMemoryStore(), router_provider)
    op = await router.submit(
        Request(request_id="compare-router-approve", raw_text="Please refund order #1002 for $800.")
    )
    assert op.status == OperationStatus.PENDING_APPROVAL

    completed = router.approve(op.operation_id, True)
    assert completed.status == OperationStatus.COMPLETED
    assert router_provider.refund_calls == 1
    assert completed.external_reference is not None

    effects = []
    agent = _scripted_refund_agent(effects)
    paused = await Runner.run(agent, "Refund order 1002 for $800.")
    state = paused.to_state()
    state.approve(paused.interruptions[0])
    resumed = await Runner.run(agent, state)

    assert effects == [("1002", 800)]
    assert resumed.final_output == "Refund completed."


@pytest.mark.asyncio
async def test_router_timeout_becomes_unknown_but_sdk_tool_timeout_has_no_business_state():
    provider = MockPaymentProvider()
    provider.timeout_after_effect = True
    router = ControlledRouter(InMemoryStore(), provider)
    op = await router.submit(
        Request(request_id="compare-timeout", raw_text="Please refund order #1001 for $45.")
    )
    assert op.status == OperationStatus.UNKNOWN

    effects = []

    @function_tool(name_override="issue_refund_timeout", needs_approval=False)
    def issue_refund_timeout(order_id: str, amount: float) -> str:
        effects.append((order_id, amount))
        raise ProviderTimeoutAfterEffect("provider timed out after applying effect")

    model = ScriptedModel(
        [
            ModelStep(
                output=[
                    function_call(
                        "issue_refund_timeout",
                        {"order_id": "1001", "amount": 45},
                        call_id="timeout-1",
                    )
                ]
            ),
            ModelStep(
                output=[
                    assistant_message("The refund attempt encountered an uncertain provider result.")
                ]
            ),
        ]
    )
    agent = Agent(
        name="SDK timeout comparison",
        instructions="Call issue_refund_timeout.",
        model=model,
        tools=[issue_refund_timeout],
    )

    result = await Runner.run(agent, "Refund order 1001 for $45.")
    assert effects == [("1001", 45)]
    assert result.final_output == "The refund attempt encountered an uncertain provider result."


def test_current_router_restart_preserves_business_operation():
    from pathlib import Path

    db_path = Path(__file__).parent / f".sqlite-sdk-compare-{__import__('os').getpid()}.db"
    try:
        first = ControlledRouter(
            __import__("app.storage.sqlite", fromlist=["SQLiteStore"]).SQLiteStore(str(db_path)),
            MockPaymentProvider(),
        )
        op = asyncio.run(
            first.submit(Request(request_id="compare-restart", raw_text="Please refund order #1002 for $800."))
        )
        assert op.status == OperationStatus.PENDING_APPROVAL

        second = ControlledRouter(
            __import__("app.storage.sqlite", fromlist=["SQLiteStore"]).SQLiteStore(str(db_path)),
            MockPaymentProvider(),
        )
        restored = second.store.get_operation(op.operation_id)
        assert restored.status == OperationStatus.PENDING_APPROVAL
    finally:
        db_path.unlink(missing_ok=True)


def test_router_replayed_approval_cannot_execute_second_effect():
    provider = MockPaymentProvider()
    router = ControlledRouter(InMemoryStore(), provider)
    op = asyncio.run(
        router.submit(
            Request(
                request_id="compare-replay",
                raw_text="Please refund order #1002 for $800.",
            )
        )
    )
    assert op.status == OperationStatus.PENDING_APPROVAL

    completed = router.approve(op.operation_id, True)
    assert completed.status == OperationStatus.COMPLETED
    assert provider.refund_calls == 1

    with pytest.raises(ValueError, match="not pending approval"):
        router.approve(op.operation_id, True)

    assert provider.refund_calls == 1


@pytest.mark.asyncio
async def test_sdk_replayed_approval_state_cannot_be_resumed_twice():
    effects = []
    agent = _scripted_refund_agent(effects)
    paused = await Runner.run(agent, "Refund order 1002 for $800.")
    state = paused.to_state()
    interruption = paused.interruptions[0]

    state.approve(interruption)
    resumed = await Runner.run(agent, state)
    assert effects == [("1002", 800)]
    assert resumed.final_output == "Refund completed."

    with pytest.raises(Exception):
        await Runner.run(agent, state)

    assert effects == [("1002", 800)]


class _ApprovalRaceStore(InMemoryStore):
    def __init__(self):
        super().__init__()
        from threading import Barrier
        self.approval_reads = Barrier(2)
        self._armed = False

    def arm_approval_race(self):
        self._armed = True

    def claim_approval(self, oid, approve):
        if self._armed:
            self.approval_reads.wait(timeout=5)
        return super().claim_approval(oid, approve)


def test_concurrent_approvals_are_single_use():
    from concurrent.futures import ThreadPoolExecutor

    provider = MockPaymentProvider()
    store = _ApprovalRaceStore()
    router = ControlledRouter(store, provider)
    op = asyncio.run(
        router.submit(
            Request(
                request_id="compare-concurrent-approval",
                raw_text="Please refund order #1002 for $800.",
            )
        )
    )
    assert op.status == OperationStatus.PENDING_APPROVAL
    store.arm_approval_race()

    with ThreadPoolExecutor(max_workers=2) as pool:
        futures = [
            pool.submit(router.approve, op.operation_id, True),
            pool.submit(router.approve, op.operation_id, True),
        ]
        outcomes = []
        for future in futures:
            try:
                outcomes.append(("ok", future.result()))
            except ValueError as exc:
                outcomes.append(("error", exc))

    assert [kind for kind, _ in outcomes].count("ok") == 1
    assert [kind for kind, _ in outcomes].count("error") == 1
    assert provider.refund_calls == 1


def test_sqlite_concurrent_approvals_allow_only_one_claim():
    from concurrent.futures import ThreadPoolExecutor
    from pathlib import Path
    import os

    from app.storage.sqlite import SQLiteStore

    db_path = Path(__file__).parent / f".sqlite-concurrent-approval-{os.getpid()}.db"
    try:
        provider = MockPaymentProvider()
        first = ControlledRouter(SQLiteStore(str(db_path)), provider)
        op = asyncio.run(
            first.submit(
                Request(
                    request_id="compare-sqlite-concurrent",
                    raw_text="Please refund order #1002 for $800.",
                )
            )
        )
        assert op.status == OperationStatus.PENDING_APPROVAL

        second = ControlledRouter(SQLiteStore(str(db_path)), provider)
        with ThreadPoolExecutor(max_workers=2) as pool:
            futures = [
                pool.submit(first.approve, op.operation_id, True),
                pool.submit(second.approve, op.operation_id, True),
            ]
            outcomes = []
            for future in futures:
                try:
                    outcomes.append(("ok", future.result()))
                except ValueError as exc:
                    outcomes.append(("error", exc))

        assert [kind for kind, _ in outcomes].count("ok") == 1
        assert [kind for kind, _ in outcomes].count("error") == 1
        assert provider.refund_calls == 1
        restored = first.store.get_operation(op.operation_id)
        assert restored.status == OperationStatus.COMPLETED
    finally:
        db_path.unlink(missing_ok=True)


def test_concurrent_approve_and_reject_have_one_authoritative_decision():
    from concurrent.futures import ThreadPoolExecutor

    provider = MockPaymentProvider()
    store = _ApprovalRaceStore()
    router = ControlledRouter(store, provider)
    op = asyncio.run(
        router.submit(
            Request(
                request_id="compare-concurrent-conflict",
                raw_text="Please refund order #1002 for $800.",
            )
        )
    )
    assert op.status == OperationStatus.PENDING_APPROVAL
    store.arm_approval_race()

    with ThreadPoolExecutor(max_workers=2) as pool:
        futures = [
            pool.submit(router.approve, op.operation_id, True),
            pool.submit(router.approve, op.operation_id, False),
        ]
        outcomes = []
        for future in futures:
            try:
                outcomes.append(("ok", future.result()))
            except ValueError as exc:
                outcomes.append(("error", exc))

    assert [kind for kind, _ in outcomes].count("ok") == 1
    assert [kind for kind, _ in outcomes].count("error") == 1
    restored = store.get_operation(op.operation_id)
    assert restored.status in {OperationStatus.COMPLETED, OperationStatus.REJECTED}
    assert provider.refund_calls in {0, 1}
    if restored.status == OperationStatus.COMPLETED:
        assert provider.refund_calls == 1
    else:
        assert provider.refund_calls == 0


@pytest.mark.asyncio
async def test_sdk_copied_run_states_do_not_provide_shared_approval_claim():
    effects = []
    agent = _scripted_refund_agent(effects)
    paused = await Runner.run(agent, "Refund order 1002 for $800.")
    assert len(paused.interruptions) == 1

    state_a = paused.to_state()
    state_b = paused.to_state()
    state_a.approve(paused.interruptions[0])
    state_b.approve(paused.interruptions[0])

    await Runner.run(agent, state_a)
    await Runner.run(agent, state_b)

    assert effects == [("1002", 800), ("1002", 800)]
