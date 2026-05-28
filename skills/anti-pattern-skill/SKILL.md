---
name: anti-pattern-skill
description: Deep review skill for identifying software, testing, delivery, and project anti-patterns that create more problems than they solve. Use when Codex needs to review a repository, subsystem, change set, architecture, testing strategy, implementation plan, or project approach for spaghetti code, lava flow, accidental complexity, god objects, hard-coded behavior, premature optimization, reinvention, copy-paste programming, or testing anti-patterns, and produce a structured review report plus a severity-ranked remediation backlog.
---

# Anti-Pattern Review

## Overview

Use this skill to review code, tests, and delivery approaches for anti-patterns: approaches that appear to solve a problem locally but make the system harder to change, understand, or trust over time.

Read [references/anti-patterns-checklist.md](references/anti-patterns-checklist.md) before reviewing so the anti-pattern definitions, review prompts, and correction directions stay consistent.

This skill complements `bad-smells-skill`. Use `bad-smells-skill` for refactoring-smell code review. Use this skill when the review needs a broader lens across code structure, testing strategy, delivery choices, and project-level habits.

## Review Workflow

1. Map the review scope before judging it.
2. Identify the main execution paths, ownership boundaries, configuration surface, test layout, and active change hotspots.
3. Choose the strongest review lens for the situation: programming anti-patterns, methodology anti-patterns, testing anti-patterns, or a mix.
4. Generate anti-pattern hypotheses from the checklist, then verify each one against repository or project evidence.
5. Report only findings that are specific enough to support a corrective action.

Do not try to label every imperfection as an anti-pattern. Anti-patterns are recurring harmful approaches, not isolated rough edges.

## Evidence Standard

Treat each finding as a claim that needs proof.

For every reported anti-pattern:
- cite the file paths, tests, documents, or project artifacts that support it
- explain the local behavior or structure that makes it look like a solution
- explain the broader cost it introduces over time
- distinguish observed facts from inference
- recommend a correction direction that reduces the harm incrementally

Prefer findings backed by one of these evidence patterns:
- repeated code or structure that spread from one local shortcut
- dead or half-abandoned code paths left in place without ownership
- classes, modules, or services absorbing too many responsibilities
- custom implementations created where a stable existing approach already exists
- tests coupled to internals or missing edge-case coverage in a risky area
- delivery or design choices justified by theoretical needs rather than observed requirements

Avoid weak findings based only on style preferences, framework taste, or single isolated lines.

## Review Priorities

Prioritize anti-patterns that most strongly degrade changeability, reliability, or team velocity:

1. Accidental Complexity
2. Spaghetti Code
3. God Object
4. Lava Flow
5. Copy-and-Paste Programming
6. Premature Optimization
7. Wrong Tests
8. Testing Internal Implementation
9. Happy Path Only Testing
10. Hard Coding
11. Reinventing the Wheel
12. Magic Numbers

If the repository has a different dominant risk profile, say so and adjust the order explicitly.

## How to Inspect a Codebase or Project

Start with structure:
- inspect top-level directories and entrypoints
- locate main services, jobs, handlers, controllers, and test suites
- identify configuration sources, feature flags, and environment assumptions
- check whether architecture docs, ADRs, plans, or comments match the current code

Then inspect for anti-pattern pressure:
- large files, large classes, deep nesting, or tangled control flow
- dead code, stale abstractions, or branches that no longer participate in execution
- literals, credentials, thresholds, or policy values embedded directly in code
- repeated custom implementations of solved problems
- performance-driven code with unclear measurement or need
- tests that break when internals move but behavior stays the same
- suites that cover only the expected path while ignoring failure modes and boundaries

When reviewing a plan or proposal rather than a codebase, inspect the intended abstractions, dependency choices, testing strategy, and rollout logic with the same lens. Anti-patterns can exist in the approach before they land in code.

## Reporting Rules

Lead with findings, not narration.

For each finding, include:
- title
- anti-pattern name
- category: `programming`, `methodology`, or `testing`
- severity: `high`, `medium`, or `low`
- confidence
- evidence
- impact
- recommended correction direction

Use `high` when the anti-pattern materially harms changeability, correctness risk, delivery confidence, or architectural clarity. Use `medium` for clear maintainability or testing debt with bounded blast radius. Use `low` for real but secondary issues.

Confidence should reflect the amount of evidence available:
- `high`: direct evidence from multiple locations or strong structural proof
- `medium`: clear local evidence with limited repository coverage
- `low`: plausible concern but incomplete evidence; prefer omitting these unless the user asked for speculative leads

## Required Output

Always produce two sections.

### 1. Structured Review Report

List findings ordered by severity, then by confidence and likely impact. Keep each finding crisp and evidence-based.

Use this shape:

```md
## Findings

### 1. Short finding title
- Anti-pattern: Premature Optimization
- Category: methodology
- Severity: high
- Confidence: medium
- Evidence: `src/cache.ts` and `docs/design.md` introduce a multi-layer cache with no measured bottleneck and no fallback invalidation strategy.
- Impact: The team now has more invalidation paths to maintain than proven latency needs to justify, increasing complexity and bug risk.
- Recommended correction: Remove speculative layers, keep one measured optimization path, and add benchmarks before further tuning.
```

### 2. Severity-Ranked Remediation Backlog

Translate the findings into an execution-ordered action list.

For each backlog item, include:
- priority
- target area
- goal
- recommended first step
- expected payoff
- risk notes

Prefer low-risk, high-leverage starting moves such as deleting dead code, extracting reusable behavior, moving configuration out of code, simplifying overbuilt abstractions, or rebalancing tests toward observable behavior.

## What Not to Do

Do not:
- stretch the term anti-pattern to cover ordinary code cleanup
- report a finding without naming the evidence that supports it
- recommend a rewrite when an incremental correction is possible
- assume a repository-wide problem from one isolated snippet
- confuse deliberate trade-offs with anti-patterns unless the broader harm is visible

If you do not find high-confidence anti-patterns, say so plainly and note the review scope you covered.

## Review Posture

Be rigorous, practical, and a little skeptical of solutions that look clever but age badly. The goal is not to moralize about code. The goal is to identify recurring harmful approaches, explain why they cost more than they save, and turn that diagnosis into a usable remediation backlog.
