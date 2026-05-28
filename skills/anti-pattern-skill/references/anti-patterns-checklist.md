# Software Anti-Patterns Checklist

Use this checklist as a thinking aid, not a scoring sheet. Report only anti-patterns backed by repository or project evidence.

## Definition

Andrew Koenig described anti-patterns this way in 1995:

> An antipattern is just like a pattern, except that instead of a solution it gives something that looks superficially like a solution, but isn't one.

Use that definition literally while reviewing: focus on approaches that look helpful locally but create broader or longer-term harm.

## Common Consequences

Anti-patterns commonly lead to:
- inefficient or ineffective problem solving
- higher complexity and maintenance cost
- lower readability and understandability
- lower team productivity and confidence

## 1. Spaghetti Code

Review prompts:
- Is the code poorly structured or hard to summarize?
- Does it lack modularity, separation of concerns, or clear ownership?
- Would modifying one behavior require tracing a tangled control flow first?

Correction directions:
- Split large blocks into smaller reusable units
- Keep methods focused on one job
- Extract clearer boundaries between concerns

## 2. Lava Flow

Review prompts:
- Is unused, stale, or abandoned code still present in the codebase?
- Is it hard to tell why a module, branch, or flag still exists?
- Are dead paths being preserved "just in case" without ownership?

Correction directions:
- Remove unused code as soon as confidence allows
- Verify reachability with searches, tests, and runtime entrypoints
- Use regular refactoring to keep obsolete code from accumulating

## 3. Accidental Complexity

Review prompts:
- Is the solution significantly more complicated than the problem requires?
- Has the design introduced extra layers, abstractions, or states without clear payoff?
- Does the implementation violate KISS in the name of flexibility or cleverness?

Correction directions:
- Simplify the design to the minimum that meets current requirements
- Remove speculative abstractions and unnecessary indirection
- Prefer understandable flows over clever ones

## 4. God Object

Review prompts:
- Does one class, service, or module try to do too many things?
- Are unrelated responsibilities converging in one place?
- Does change in many areas of the domain repeatedly land in the same object?

Correction directions:
- Split the object into smaller units with focused responsibilities
- Reassign behavior to better ownership boundaries
- Restore single-responsibility-oriented structure

## 5. Hard Coding

Review prompts:
- Are policy values, endpoints, thresholds, credentials, or environment assumptions embedded directly in source code?
- Does changing behavior require source edits rather than configuration updates?
- Are the same values repeated across files instead of being centrally managed?

Correction directions:
- Move configuration to config files, environment variables, or data stores
- Centralize shared constants and policy values
- Use static analysis where helpful to catch hard-coded values

## 6. Magic Numbers

Review prompts:
- Are numeric literals used without meaningful names or explanation?
- Would a maintainer struggle to know what a value represents?
- Are domain thresholds or units encoded as bare numbers?

Correction directions:
- Replace literals with named constants or value objects
- Document domain meaning where the name alone is insufficient
- Group related constants by domain concept

## 7. Premature Optimization

Review prompts:
- Has performance complexity been introduced before confirming the need?
- Are caches, concurrency, pooling, or indexing layers justified by measurement?
- Has performance tuning reduced readability or maintainability without proven benefit?

Correction directions:
- Optimize only where measured bottlenecks exist
- Remove speculative performance machinery
- Add benchmarks or production evidence before further tuning

## 8. Reinventing the Wheel

Review prompts:
- Has the team built a custom solution where a stable existing one would suffice?
- Is the custom implementation increasing time, cost, or correctness risk?
- Would an established library, framework feature, or internal platform solve the problem more safely?

Correction directions:
- Prefer established solutions unless strong constraints justify custom work
- Record the reason when not using an existing solution
- Replace fragile homegrown implementations selectively

## 9. Copy-and-Paste Programming

Review prompts:
- Has code been duplicated instead of reused through abstraction?
- Do multiple locations share the same logic with only minor edits?
- Would bug fixes require repeating the same edit in several places?

Correction directions:
- Extract shared behavior into reusable functions, classes, or modules
- Refactor repeated logic before it drifts further
- Keep abstractions honest and small

## 10. Wrong Tests

Review prompts:
- Is the chosen test type mismatched to the behavior being verified?
- Are slow end-to-end tests covering logic that unit tests should own, or vice versa?
- Does the current test mix create poor coverage or brittle feedback?

Correction directions:
- Rebalance the suite toward the appropriate test types
- Match test scope to the behavior and risk under test
- Remove redundant tests that add cost without confidence

## 11. Testing Internal Implementation

Review prompts:
- Are tests coupled to private methods, internal state, call order, or incidental structure?
- Do tests fail when internals change even though observable behavior stays correct?
- Is mocking or spying standing in for meaningful behavior verification?

Correction directions:
- Assert observable behavior and external contracts
- Reduce coupling to private implementation details
- Keep test doubles focused on boundaries that matter

## 12. Happy Path Only Testing

Review prompts:
- Do tests cover only the expected case and skip failures, boundaries, and invalid input?
- Are error handling and recovery paths left largely untested?
- Would a surprising input or environment state likely escape detection?

Correction directions:
- Add edge cases, failure paths, and boundary-condition coverage
- Exercise error handling intentionally
- Review risky flows for missing negative tests

## How to Recognize Anti-Patterns Early

Look for these warning signs:
- solutions that are hard to explain simply
- changes that require edits across too many places
- code or tests that no one wants to touch
- layers or abstractions justified by hypothetical future needs
- custom infrastructure built before understanding whether the problem is common or stable

Keep an open mind and question your own assumptions. Feedback from others is valuable because anti-patterns often feel reasonable from the inside.

## How to Avoid Anti-Patterns

Use these habits while designing and reviewing:
- step back and consider the larger context before locking onto a solution
- prefer proven patterns and established best practices
- break large problems into smaller, clearer pieces
- ask for feedback early when trade-offs are uncertain
- keep reviewing and simplifying as understanding improves
- do not be afraid to delete or restart a poor approach when incremental repair is no longer worth it
