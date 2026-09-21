# MVP

REQUEST → AGENT INTERPRETATION → DETERMINISTIC POLICY → OPERATION → EFFECT → VERIFICATION → EVIDENCE.

The OpenAI Agents SDK is the agent layer; the product does not implement a replacement runtime. The model interprets the request. Deterministic Python code owns policy decisions, including the invariant that a refund cannot exceed the payment amount. The external refund is controlled by deterministic policy and, above the configured threshold, a persisted human approval state.

States:
RECEIVED → ANALYZING → VALIDATING → DECIDING
safe: DECIDING → EXECUTING → VERIFYING → COMPLETED
approval: DECIDING → PENDING_APPROVAL → APPROVED → EXECUTING → VERIFYING → COMPLETED
rejection: PENDING_APPROVAL → REJECTED
ambiguous provider result: EXECUTING → UNKNOWN → RECONCILING → COMPLETED / UNKNOWN

Evidence types: REQUEST, ANALYSIS, POLICY_DECISION, APPROVAL, EXTERNAL_RESULT, VERIFICATION, RECONCILIATION.

Acceptance target:
1. small eligible refund executes;
2. large eligible refund pauses;
3. refund above the payment amount is denied;
4. rejection produces zero external effects;
5. approval executes and verifies;
6. pending approval survives a router restart;
7. timeout-after-effect becomes UNKNOWN;
8. reconciliation can confirm the effect.

Architectural checkpoint:
- The current MVP intentionally does not give the Agent an effect tool.
- The next architecture experiment is to compare application-level approval against Agents SDK tool-level approval, without assuming that agent-owned effect capability is required.


## Architecture experiment: Agents SDK tool-level approval

The SDK was tested separately from the application router in `tests/test_agents_sdk_hitl.py`.

Observed contract:
- a `function_tool(needs_approval=True)` pauses the run before the function executes;
- the pending call is exposed through `RunResult.interruptions`;
- `RunState` can carry the paused run;
- `state.approve(...)` followed by `Runner.run(agent, state)` resumes the run and permits the tool effect;
- `state.reject(...)` resumes without executing the tool effect.

This proves that the Agents SDK can provide the immediate Agent → approval → tool execution boundary. It does not by itself replace the application's Operation record, business authorization policy, external-effect verification, reconciliation, or business evidence model.

The SDK documentation also states that serialized RunState is not authentication or authorization. The application must authenticate the reviewer, authorize the reviewer against server-owned pending work, validate the decision against that stored work, and coordinate consumption so concurrent or replayed approvals cannot resume the same snapshot twice.

Current decision: keep Operation as the application's business control/evidence boundary while the SDK HITL experiment remains isolated. Do not replace the application boundary with SDK HITL until durability, authorization, replay, and evidence requirements are demonstrated.

External verification date: 2026-09-21. The current Agents SDK documentation describes RunState as the durable HITL pause/resume boundary. Current SDK issue tracking also contains active/recent reports concerning durable Session behavior around resumed approval flows, so the SDK is not being treated as an automatically sufficient durable business transaction boundary.
