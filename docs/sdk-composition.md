# SDK composition decision

The current OpenAI Agents SDK already owns execution and orchestration primitives:

- Tools can declare `needs_approval`; interrupted results serialize through `RunState` and resume after an approval decision.
- Runner calls emit traces for generations, handoffs, tools, and guardrails.
- Custom trace processors can export those events to another destination.
- Sessions persist conversation history, including interrupted workflows.
- Retry configuration belongs close to model and SDK execution.

`agents-support-ops` stays outside those responsibilities. It normalizes events into support terminology, applies redaction before persistence, controls unreliable external tools, records deterministic replay inputs, and produces an engineering escalation. This keeps the integration replaceable and the upstream SDK fork small.

## Upstreamable example

An upstream documentation example should demonstrate:

1. A support tool declared with `needs_approval=True`.
2. A run pausing with an interruption.
3. Serialization of the `RunState` without secrets.
4. Approval or rejection with a clear rejection message.
5. Resumption using the same session.
6. A custom trace processor exporting a redacted audit record.

No SDK core behavior needs to change for this example.
