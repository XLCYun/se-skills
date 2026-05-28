---
name: bad-smells-skill
description: Deep code review skill for identifying design problems and maintainability risks through the refactoring bad-smells lens. Use when Codex needs to review a repository, subsystem, or change set for poor design, hidden coupling, duplication, oversized functions or classes, speculative abstractions, data clumps, message chains, or other refactoring smells, and produce a structured review report plus a severity-ranked remediation backlog.
---

# Bad Smell Review

## Overview

Use this skill to perform a deep code review centered on design quality rather than style nitpicks. Favor high-confidence findings with concrete evidence. Produce a structured review report and a severity-ranked remediation backlog.

Read [references/bad-smells-checklist.md](references/bad-smells-checklist.md) before reviewing code so the smell definitions, review prompts, and refactoring directions stay consistent.

## Review Workflow

1. Map the repository before judging it.
2. Identify the core execution paths, ownership boundaries, and shared abstractions.
3. Focus on the modules most likely to concentrate design risk: core domain logic, orchestration layers, widely imported utilities, large classes, large files, and hotspots tied to recent changes.
4. Generate smell hypotheses from the checklist, then verify each one against code evidence.
5. Report only findings that have enough evidence to survive pushback from a skeptical maintainer.

Do not try to review every file line by line unless the repository is tiny. Sample broadly, then dive deeply where signals are strongest.

## Evidence Standard

Treat each finding as a claim that must be supported.

For every reported smell:
- Cite the file paths and the most relevant functions, methods, classes, or fields.
- Explain what behavior or structure triggered the smell.
- Distinguish observed facts from inference.
- State why this is a design or maintainability problem, not just a stylistic preference.
- Recommend refactoring directions that match the smell.

Prefer findings with one of these evidence patterns:
- repeated structure across two or more places
- a class or file combining unrelated responsibilities
- a function whose control flow or dependencies obscure intent
- cross-module coupling that makes change ripple outward
- data passed around in clumps or represented with weak primitives

Avoid low-value findings based only on naming taste, framework preference, or local formatting.

## Review Priorities

Prioritize the smells that usually create the most leverage when fixed:

1. Divergent Change
2. Shotgun Surgery
3. Feature Envy
4. Large Class
5. Long Function
6. Duplicated Code
7. Data Clumps
8. Primitive Obsession
9. Message Chains
10. Mutable or Global Data

If the repository has a different dominant risk profile, say so and adjust the order explicitly.

## How to Inspect a Codebase

Start with structure:
- inspect top-level directories
- locate main entrypoints, services, jobs, handlers, or controllers
- identify shared libraries, model types, and cross-cutting helpers

Then inspect for design pressure:
- unusually large files, classes, or functions
- many parameters or repeated parameter groups
- modules with broad import fan-in or fan-out
- repeated switch or if-else trees over the same type code
- pass-through wrappers with little original behavior
- long object navigation chains
- comments that explain confusing code instead of intent

When reviewing a change set rather than a whole repo, still examine surrounding collaborators so you can judge whether the local diff exposes a deeper smell.

## Reporting Rules

Lead with findings, not narration.

For each finding, include:
- title
- smell name
- severity: `high`, `medium`, or `low`
- evidence
- impact
- recommended refactoring direction
- confidence

Use `high` when the smell materially harms changeability, correctness risk, or architectural clarity. Use `medium` for clear maintainability debt with limited blast radius. Use `low` for real but secondary cleanup.

Confidence should reflect the amount of evidence available:
- `high`: direct evidence from multiple locations or strong structural proof
- `medium`: clear local evidence with limited repository coverage
- `low`: plausible smell but incomplete evidence; prefer omitting these unless the user asked for speculative leads

## Required Output

Always produce two sections.

### 1. Structured Review Report

List findings ordered by severity, then by confidence and likely impact. Keep each finding crisp and evidence-based.

Use this shape:

```md
## Findings

### 1. Short finding title
- Smell: Large Class
- Severity: high
- Confidence: high
- Evidence: `path/to/file.ts` contains ...
- Impact: Changes to pricing rules, validation, and persistence all converge here, so unrelated edits collide.
- Refactoring direction: Extract Class, Move Method, Split Phase
```

### 2. Severity-Ranked Remediation Backlog

Translate the findings into an action list. Group by execution order, not by smell name.

For each backlog item, include:
- priority
- target area
- goal
- recommended first refactor step
- expected payoff
- risk notes

Prefer low-risk, high-leverage starting moves such as extracting pure functions, introducing parameter objects, or moving behavior closer to the data it envies.

## What Not to Do

Do not:
- turn lint issues into fake bad-smell findings
- report a smell without naming the evidence that supports it
- recommend broad rewrites when incremental refactoring would work
- assume a smell exists repo-wide from one isolated snippet
- confuse framework ceremony with speculative generality unless the abstraction is truly unused or unjustified

If you do not find high-confidence smells, say so plainly and note the review scope you covered.

## Review Posture

Be rigorous, a little suspicious, and very specific. The goal is not to prove the code is ugly. The goal is to identify the design weaknesses most likely to slow future work or cause hidden defects, then turn them into a practical remediation backlog.
