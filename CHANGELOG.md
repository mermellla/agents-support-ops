# Changelog

## 0.2.0 - 2026-07-16

- Added replay schema 1.1 with typed execution, tool-result, model-output, prompt, usage, cost, and integrity provenance.
- Preserved schema 1.0 loading and deprecated the original untyped model-output fields.
- Added redacted replay persistence with canonical integrity verification.
- Covered recorded investigation output in replay integrity and redacted sensitive mapping keys.
- Restricted canonical exclusions to modeled runtime timestamps and the top-level integrity record.
- Prevented replay-store path traversal with portable ID validation and resolved containment checks.
- Required field-specific evidence citations for every factual escalation narrative field.
- Added Python 3.11-3.13 clean-install tests of immutable wheel and sdist release artifacts before TestPyPI publication.
- Added Python and OpenAI Agents SDK compatibility documentation and trusted-publishing automation.

## 0.1.1 - 2026-07-16

- Narrowed circuit status to a typed literal so downstream strict typechecking succeeds.

## 0.1.0 - 2026-07-16

- Added versioned audit, replay, evidence, approval, and escalation models.
- Added recursive secret and PII redaction with append-only JSONL export.
- Added tool retry budgets, failure injection, and circuit breaking.
- Added an OpenAI Agents SDK-compatible trace processor.
