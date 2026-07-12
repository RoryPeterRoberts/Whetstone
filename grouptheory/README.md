# Whetstone-GT — a runnable group-theory slice

A working proof that the Whetstone **kernel is domain-independent**. This adapter reuses
the exact software-engineering kernel (`whetstone/events.py`, `transfer.py`, `metrics.py`
and the JSON schemas) and adds a group-theory front end whose *executable tell* is a
**bounded counterexample search over small finite groups** (via `sympy`, pure Python — no
GAP/Sage/Lean required).

It is the concrete companion to the concept paper *Whetstone for Group Theory*.

## What it demonstrates

One directing principle:

> A bounded computational check over small cases is **support, not a theorem**. Identify the
> load-bearing hypothesis and confirm it by **weakening it and searching for a counterexample.**

- **Problem 1 (taught):** "groups of order p² are abelian." The bounded search finds no
  counterexample over the complete order-4/9/25 families → *support only*. Weakening p² → p³
  surfaces **D4** (order 8, non-abelian) → the hypothesis is proven load-bearing → the tell
  **discriminates**.
- **Problem 2 (transfer):** "groups of order pq with p ∤ (q−1) are cyclic." The same principle
  is reused; the tell discriminates (support over C15; weakening surfaces **S3**). The kernel
  records `transferred` — cross-context, both legs present.

"No counterexample in the bounded family" is **never** promoted to a theorem. The strong
claim is transfer of the *directing principle*, verified by a discriminating search — the
same discipline as the code slice, where a passing test is not a discriminating test.

## Run it

```
python3 grouptheory/demo.py          # end-to-end worked example + kernel metrics
python3 -m pytest grouptheory -q     # the maths + the discrimination protocol + transfer
```

## Files

| File | Role |
|------|------|
| `_kernel.py` | bridges to the shared Whetstone kernel (`whetstone/`) — reuse, not re-implementation |
| `search.py` | the executable tell: bounded counterexample search + the discrimination protocol |
| `slice.py` | the four worked claims, the intervention card, and the lifecycle on the kernel ledger |
| `demo.py` | runnable end-to-end demo |
| `test_grouptheory.py` | tests: sympy-checked maths, discrimination, cross-problem transfer |

## Honest boundary

This is a **runnable demonstration**, not the deployed research system. It reuses the
kernel and a real executable tell on *schematic* classical claims. The actual research
pilot (concept paper §11) needs the lecturer's own live problem, corpus and notation, and —
for research-grade tells — connectors to GAP / Sage / LMFDB / Lean. What this proves is that
the architecture transfers to mathematics and that the tell can be made genuinely executable
in the small. It does **not** claim to certify that any research theorem is new or true.
