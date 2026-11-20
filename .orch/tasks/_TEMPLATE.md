# Task: <one line, imperative>

## Goal

One paragraph. What must be true when this is done. Written so it can be checked,
not interpreted.

## Context

- Read `PLAN.md` section "<name>" before starting.
- Relevant files: `path/one.py`, `path/two.py`
- Facts you can rely on without re-deriving:
  - <fact> (already verified by the orchestrator)
  - <fact>

## Do

1. <concrete step>
2. <concrete step>

## Definition of done

A command that exits 0, stated literally. Example:

```
python3 validate_gate.py
```

...printing `GATE GREEN` with 159 items matched on both sides.

## Constraints

- Do not touch: `<files outside scope>`
- Stdlib only / deps allowed: `<list>`
- Follow the structure in PLAN.md's Architecture section; do not invent new top-level dirs.

## Report back

Call `finish` with:
- `verification`: the exact command you ran and its real output (paste it)
- `files_changed`: every file you created or edited
- `open_questions`: anything you assumed, worked around, or noticed but left alone
