# Refactoring Bad Smells Checklist

Use this checklist as a thinking aid, not a scoring sheet. Report only smells backed by repository evidence.

## 1. Mysterious Name

Review prompts:
- Are variables, functions, classes, and fields self-explanatory?
- Are there single-letter names, opaque abbreviations, pinyin shorthands, or overloaded terms that hide intent?

Refactoring directions:
- Change Function Declaration
- Rename Variable
- Rename Field

## 2. Duplicated Code

Review prompts:
- Do two or more areas share nearly identical control flow, branching, or transformation logic?
- Would extracting shared behavior reduce duplication without injecting dangerous hidden coupling into critical modules?

Refactoring directions:
- Extract Function
- Slide Statements
- Pull Up Method

## 3. Long Function

Review prompts:
- Does the function have one job?
- Does it contain deep branching, nested loops, or multiple non-core responsibilities?
- Is the control flow hard to summarize in one sentence?

Refactoring directions:
- Extract Function
- Replace Temp with Query
- Introduce Parameter Object
- Preserve Whole Object
- Decompose Conditional
- Replace Conditional with Polymorphism
- Split Loop

## 4. Long Parameter List

Review prompts:
- Does the function take more information than a caller can comfortably reason about?
- Do several parameters always travel together?
- Are flag arguments being used to switch behavior?

Refactoring directions:
- Replace Parameter with Query
- Preserve Whole Object
- Introduce Parameter Object
- Remove Flag Argument
- Combine Functions into Class

## 5. Global Data

Review prompts:
- Is state globally reachable and mutable from many places?
- Are public static variables or singleton state used as shared scratch space?

Refactoring directions:
- Encapsulate Variable

## 6. Mutable Data

Review prompts:
- Is state exposed with more write access than necessary?
- Do multiple side-effecting paths mutate the same data?
- Is it hard to know where a value changed?

Refactoring directions:
- Encapsulate Variable
- Split Variable
- Slide Statements
- Extract Function
- Separate Query from Modifier
- Remove Setting Method
- Replace Temp with Query
- Combine Functions into Class

## 7. Divergent Change

Review prompts:
- Does one module change for many unrelated reasons?
- Do domain rules, formatting, persistence, and transport concerns accumulate in the same place?

Refactoring directions:
- Split Phase
- Move Method
- Extract Function
- Extract Class

## 8. Shotgun Surgery

Review prompts:
- Does one feature or policy change require small edits in many files?
- Is behavior spread thinly across modules with weak cohesion?

Refactoring directions:
- Move Method
- Move Field
- Combine Functions into Class
- Combine Functions into Transform
- Split Phase
- Inline Function
- Inline Class

## 9. Feature Envy

Review prompts:
- Does a function interact more with another object or module than with its own home?
- Is it mostly reading foreign data and applying logic from afar?

Refactoring directions:
- Move Method
- Extract Function

## 10. Data Clumps

Review prompts:
- Do the same 3-4 fields or parameters appear together repeatedly?
- Do they represent a stable concept that deserves its own object?

Refactoring directions:
- Extract Class
- Introduce Parameter Object
- Preserve Whole Object

## 11. Primitive Obsession

Review prompts:
- Are strings, numbers, or booleans carrying domain concepts such as money, phone numbers, states, or units?
- Are domain invariants enforced only by convention?

Refactoring directions:
- Replace Primitive with Object
- Replace Type Code with Subclasses
- Replace Conditional with Polymorphism

## 12. Repeated Switches

Review prompts:
- Are there multiple switch statements or repeated if-else chains over the same type code or state?
- Does adding one variant require editing many branches?

Refactoring directions:
- Replace Conditional with Polymorphism

## 13. Loops

Review prompts:
- Are imperative loops obscuring collection transforms that would be clearer as a pipeline?
- Would a declarative collection API improve readability without harming clarity or performance requirements?

Refactoring directions:
- Replace Loop with Pipeline

## 14. Lazy Element

Review prompts:
- Does a class, function, or abstraction do too little to justify its existence?
- Is it left behind by earlier refactoring or over-design?

Refactoring directions:
- Inline Function
- Inline Class
- Collapse Hierarchy

## 15. Speculative Generality

Review prompts:
- Is an abstraction present for a future requirement that has not arrived?
- Are hooks, extension points, or inheritance layers unused or unjustified?

Refactoring directions:
- Collapse Hierarchy
- Inline Function
- Inline Class
- Change Function Declaration
- Remove Dead Code

## 16. Temporary Field

Review prompts:
- Are some fields meaningful only for a narrow algorithm or one call path?
- Do they stay null or irrelevant most of the time?

Refactoring directions:
- Extract Class
- Extract Function
- Introduce Special Case

## 17. Message Chains

Review prompts:
- Are there long object navigation chains like `a.b().c().d()`?
- Does the caller know too much about collaborator internals?

Refactoring directions:
- Hide Delegate
- Extract Function
- Move Method

## 18. Middle Man

Review prompts:
- Does a class mainly forward calls elsewhere with little original behavior?
- Is delegation adding ceremony without insulating useful complexity?

Refactoring directions:
- Remove Middle Man
- Inline Function

## 19. Insider Trading

Review prompts:
- Do two modules exchange private details too freely?
- Is the collaboration too intimate for the intended encapsulation boundary?

Refactoring directions:
- Move Method
- Hide Delegate
- Replace Subclass with Delegate
- Replace Superclass with Delegate

## 20. Large Class

Review prompts:
- Does one class own too many fields, methods, or responsibilities?
- Is it acting as an accumulation point for unrelated behavior?

Refactoring directions:
- Extract Superclass
- Replace Type Code with Subclasses
- Extract Class

## 21. Alternative Classes with Different Interfaces

Review prompts:
- Are there similar concepts implemented with incompatible method names or signatures?
- Could callers share a common interface if the APIs were aligned?

Refactoring directions:
- Change Function Declaration
- Move Method
- Extract Superclass

## 22. Data Class

Review prompts:
- Is a class mostly fields plus getters and setters?
- Does behavior that belongs with the data live elsewhere?

Refactoring directions:
- Encapsulate Record
- Remove Setting Method
- Move Method
- Extract Function
- Split Phase

## 23. Refused Bequest

Review prompts:
- Does a subclass inherit behavior or fields it does not truly want?
- Does the inheritance relationship violate substitutability?

Refactoring directions:
- Replace Subclass with Delegate
- Replace Superclass with Delegate

## 24. Comments

Review prompts:
- Are long comments compensating for confusing code?
- Is the comment explaining how tangled code works rather than why it exists?

Refactoring directions:
- Extract Function
- Change Function Declaration
- Introduce Assertion

## Triage Guidance

When many smells are present, prefer reporting the ones that:
- distort change boundaries
- force many-file edits
- hide domain logic behind weak naming or oversized functions
- separate behavior from the data it belongs to
- create correctness risk through mutable shared state

Treat smells as related patterns. For example:
- `Large Class` often co-occurs with `Divergent Change`
- `Shotgun Surgery` often points back to weak cohesion
- `Data Clumps` and `Primitive Obsession` often suggest missing domain objects
- `Feature Envy` and `Message Chains` often reveal misplaced behavior
