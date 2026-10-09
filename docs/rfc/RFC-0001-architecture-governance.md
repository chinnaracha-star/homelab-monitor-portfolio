# RFC-0001 — Architecture governance

**Status:** Accepted  
**Sprint:** 13.1  
**Date:** 2026-09-24

## Purpose

Phase 12 froze the running contracts: existing REST shapes, agent protocol `0.1.0`, JWT with roles `admin` | `operator` | `viewer`, SQLite as the system of record, and in-process plugins. Phase 13 may extend the platform only through a written RFC. An RFC records the decision before code changes those contracts.

Sprint 13.1 creates the process. It does not change runtime behavior.

## Lifecycle

Every future architecture change follows these states, in order. A later sprint may skip none of them.

1. **Proposal.** An author writes `docs/rfc/RFC-NNNN-short-title.md` with the problem, the contract that would change, and what must stay compatible.
2. **Discussion.** Reviewers comment on compatibility with REST, the agent protocol, SQLite, authentication, RBAC, plugins, the dashboard, Telegram, and Photo Monitor. The status line stays `Discussion`.
3. **Accepted.** The change is approved. Implementation is allowed only inside the scope written in the RFC. Status becomes `Accepted`.
4. **Implemented.** The accepted scope is in the tree. The RFC links the sprint or commit and stays as the record. Status becomes `Implemented`.
5. **Deprecated.** A newer accepted RFC replaces the decision. The old RFC status becomes `Deprecated` and points at the replacement. Deprecated text is not deleted.

## Required contents

- Status, sprint, and date
- Problem and non-goals
- Contracts touched and contracts explicitly preserved
- Rollout and how to tell the change failed

## Rule

A change to REST compatibility, agent protocol `0.1.0`, the SQLite schema, JWT, RBAC, plugin loading, dashboard behavior, Telegram delivery, or Photo Monitor behavior requires an accepted RFC before implementation. Documentation-only work, bugfixes that restore the current contract, and additive fields already allowed by an accepted RFC do not open a new RFC.

This document is RFC-0001 and is **Accepted** as the governance process for Phase 13.
