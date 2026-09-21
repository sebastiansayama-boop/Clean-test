import pytest

from agents import Agent, Runner, function_tool
from agents.testing import ModelStep, ScriptedModel, assistant_message, function_call


@pytest.mark.asyncio
async def test_sdk_tool_approval_pauses_before_effect_and_resumes():
    effects = []

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
                        call_id="refund-1",
                    )
                ]
            ),
            ModelStep(output=[assistant_message("Refund completed.")]),
        ]
    )
    agent = Agent(
        name="SDK HITL experiment",
        instructions="When asked to refund, call issue_refund with the requested order and amount.",
        model=model,
        tools=[issue_refund],
    )

    paused = await Runner.run(agent, "Refund order 1002 for $800.")
    assert len(paused.interruptions) == 1
    assert effects == []
    assert paused.interruptions[0].name == "issue_refund"

    state = paused.to_state()
    state.approve(paused.interruptions[0])
    resumed = await Runner.run(agent, state)

    assert effects == [("1002", 800)]
    assert resumed.final_output == "Refund completed."


@pytest.mark.asyncio
async def test_sdk_tool_approval_rejection_prevents_effect():
    effects = []

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
                        call_id="refund-2",
                    )
                ]
            ),
            ModelStep(output=[assistant_message("Refund was not completed.")]),
        ]
    )
    agent = Agent(
        name="SDK HITL rejection experiment",
        instructions="When asked to refund, call issue_refund with the requested order and amount.",
        model=model,
        tools=[issue_refund],
    )

    paused = await Runner.run(agent, "Refund order 1002 for $800.")
    assert len(paused.interruptions) == 1
    assert effects == []

    state = paused.to_state()
    state.reject(paused.interruptions[0])
    resumed = await Runner.run(agent, state)

    assert effects == []
    assert "not completed" in resumed.final_output.lower()
