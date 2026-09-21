# MVP

REQUEST → AGENT INTERPRETATION → DETERMINISTIC POLICY → OPERATION → EFFECT → VERIFICATION → EVIDENCE.

The OpenAI Agents SDK is the agent layer; the product does not implement a replacement runtime. The external refund is controlled by deterministic policy and, above the configured threshold, a persisted human approval state.

States:
RECEIVED → ANALYZING → VALIDATING → DECIDING
safe: DECIDING → EXECUTING → VERIFYING → COMPLETED
approval: DECIDING → PENDING_APPROVAL → APPROVED → EXECUTING
rejection: PENDING_APPROVAL → REJECTED
ambiguous provider result: EXECUTING → UNKNOWN → RECONCILING → COMPLETED / UNKNOWN

Evidence types: REQUEST, ANALYSIS, POLICY_DECISION, APPROVAL, EXTERNAL_RESULT, VERIFICATION, RECONCILIATION.

Acceptance target:
1. small eligible refund executes;
2. large refund pauses;
3. rejection produces zero external effects;
4. approval executes;
5. timeout-after-effect becomes UNKNOWN;
6. reconciliation can confirm the effect.
