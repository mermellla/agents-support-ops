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

## Installation

Install the model-neutral operational primitives:

```bash
pip install agents-support-ops
```

Install the optional OpenAI Agents SDK integration:

```bash
pip install "agents-support-ops[openai]"
```

```python
from agents_support_ops import AuditLog, Redactor, SupportTraceProcessor

audit = AuditLog("audit.jsonl", redactor=Redactor())
processor = SupportTraceProcessor(audit)
# agents.add_trace_processor(processor)
```

See [`docs/sdk-composition.md`](docs/sdk-composition.md) for the integration boundary.
Maintainers should follow [`docs/releasing.md`](docs/releasing.md) for the OIDC-based
TestPyPI and PyPI release process.

## Compatibility

| Capability | Supported versions |
| --- | --- |
| Core package | Python 3.11, 3.12, and 3.13; no agent SDK required |
| OpenAI integration | `openai-agents>=0.6,<1` |
| AI Escalation Lab live adapter | `openai-agents>=0.18.2,<1` |

Replay schema `1.1` records typed run, tool, model, prompt, token, cost, and integrity
provenance. Schema `1.0` bundles remain readable for backward compatibility.
Canonical replay digests exclude only the bundle integrity record and the modeled
runtime timestamps (`created_at`, evidence observation times, approval decision
times, and model generation time). Metadata-like keys in ticket, tool, model, and
recorded output payloads remain integrity-covered. `ReplayStore` accepts only
portable replay IDs and verifies that resolved paths stay inside its configured root.

Escalation packages require field-specific evidence citations in
`narrative_evidence` for `summary`, `impact`, `reproduction_steps`,
`suspected_component`, and `recommended_next_action`. Each field must cite at least
one evidence ID present in the package. JSON exports retain this mapping and Markdown
exports display the citations beside each narrative field.
