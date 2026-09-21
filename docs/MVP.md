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
