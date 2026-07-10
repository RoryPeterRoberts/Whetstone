# The Dynamic Teacher — design

The north-star for the teaching tool. Per-lesson output rules live in `TEACHING_METHOD.md`; this is the product.

## The goal (the spine)
Teach the learner to **harness LLMs for utility** — not to study the field. Like teaching an 1800s mind to wire a circuit and run a motor, not to derive Maxwell's equations. The deep theory (transformer maths, attention, RLHF) is the Maxwell layer: conceptual, and only when curiosity leads there.

**The question on every concept:** *what do you need to know to be useful?*
- **Spine** — needed to harness it → the road.
- **Adventure** — deeper theory → optional, conceptual, curiosity-only, flagged as a detour.

This sits **above** the threshold and the gate. If a concept doesn't help them harness LLMs, it's an adventure, not the road.

**Command altitude.** The learner sits in front of a coding model (Claude Code / KERN) and never writes code. Everything is taught at that altitude: the capability, when to reach for it, the plain-English *direction* to give the agent, and the *tell* to judge it — never the implementation. Code is binary to them; their agent writes it. (The "make it solid" step is direction + tell, not a code block.)

## Driven by curiosity, oriented by utility
The learner leads; they can question or detour anything. The map always shows the **road to useful**, so adventures are enjoyed, never lost in. The teacher names a detour honestly ("fun, not needed to harness it") to protect their time.

## Dynamic, not fixed
A fixed interface lets them question nothing. So the rich scaffolding — gate, analogy, the shape, framebreak, validation, the ride — is **generated around what they ask**, live (Codex). Everything is questionable: any word / claim / analogy → simplify, expand, challenge, validate, or branch, on the spot. Rich *because* it's dynamic.

## Every concept (from TEACHING_METHOD.md)
Analogy <30w → practice <100w, plain, ceiling-not-target. The learner derives; the teacher sharpens. Depth opt-in.

## The teacher's characteristics (research × learner)
- **They do the work; the teacher sharpens** — the biggest research lever (expert tutors tell least; the self-explanation effect) is their native mode.
- **Mastery loop** — don't advance until it's solid; "check understanding" = they explain or predict it back, at their speed (Bloom's 2-sigma).
- **Adapts** — reads their profile (known / asked), starts at their level, pitches at their edge (Vygotsky's ZPD).
- **Motivation is the throttle** — INCUP + curiosity; challenge at the edge, speed, their control never railroaded (Lepper).
- **Diagnoses the exact misconception** — on their own analogies, pinpoint the imprecise bit (cup→mould), not "you're wrong".
- **Retention + transfer** — transfer *is* framebreak; retention = spaced return to banked concepts.
- **Trust by evidence** — external verified links, honest sharpening, never the teacher vouching for itself.

## The macro (the ride), reframed
Destination = **the learner can harness LLMs for their real work, owned, off the paid frontier.** The spine is the road; adventures are scenic detours; progress = harnessing capability gained, not concepts memorised.

## The engine
Codex (bootstrap) generates every affordance live per the method; a local model later (the autonomy arc). The learner profile + banked concepts persist and adapt.
