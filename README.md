# agents-support-ops

A typed companion library for the OpenAI Agents SDK that turns traces, tool outcomes, approvals, and costs into support-engineering artifacts.

It composes the SDK's native human-in-the-loop, `RunState`, retries, tracing processors, and sessions. It does not fork or replace those primitives.

## What it adds

- Redacted JSONL audit trails.
- Tool retry budgets and circuit breakers.
- Deliberate failure injection for regression tests.
- Versioned replay bundles with canonical digests.
- Evidence-linked escalation packages in JSON and Markdown.
- A synchronous trace processor compatible with the Agents SDK processor interface.

```python
from agents_support_ops import AuditLog, Redactor, SupportTraceProcessor

audit = AuditLog("audit.jsonl", redactor=Redactor())
processor = SupportTraceProcessor(audit)
# agents.add_trace_processor(processor)
```

See [`docs/sdk-composition.md`](docs/sdk-composition.md) for the integration boundary.
