# OpenHands enforcement adapter

This integration is technical harness wiring only and defines keine normative Governance.
The sole normative source remains the installed Agent Governance release referenced by the managed consumer projection.

The adapter never edits GOVENANCE.md, the manifest, modules, or the immutable release directory.

It uses official synchronous OpenHands command hooks only:

- UserPromptSubmit: validate the existing Agent Governance installation and inject the operational task-tracker requirement.
- PreToolUse: fail closed if Governance validation fails; require exactly one active in_progress subtask before substantive actions; validate plan transitions.
- PostToolUse: persist successful plan revisions, substantive changes, and verification evidence.
- Stop: block completion while tasks remain open, after an unverified change, or until the plan is refreshed after the final verification.

The enforced OpenHands harness cycle is:

task_tracker update -> execute current subtask -> relevant verification -> task_tracker update -> next subtask

OpenHands' own risk confirmation remains responsible for high-risk confirmation. This adapter does not copy or replace the Governance policy.
