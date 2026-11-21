# Design

## Where the files live

Keep `cardtool.py` and the `.card.txt` source; copy them into the repo from the handoff zip. 78 entries is too many to hand-edit in raw JSON, and cardtool already builds and lints. (v2's source-of-truth discipline was correct; only its content was timid.)

## Vocabulary

Put the crude word in the entry body next to the anatomy, and add one sample sentence. Reason: prompt proximity — the model copies what sits closest to the instruction. A separate style entry alone gets ignored once kink entries flood the context; that is why the samples ride inside each entry.

The `Explicit vocabulary` entry sits at depth 1, order 170 — above `Explicitness - maximum` at 160, so ordering pins vocabulary last. It is the fallback for uncovered kinks, so the book degrades to good instead of silent.

## Coverage

Add all banned categories over cutting: the book is global, so a category that no current character uses costs almost nothing (it never fires) and is worth having the day a new card wants it. Watersports and scat stay separate entries because their keys would otherwise collide on "piss" and "mess".

## Keys

One shared secondary regex, defined once in the source meta, copied byte-identically. Reason: v2 pasted it 18 times and one typo would have been invisible. The four new everyday-word entries (`kiss`, `massage`, `food`, `camera`) all take it.

## Tests

Port the scratch checks into `tools/test_activation.py` with three sections: positives, false-positive corpus, recursion replay. Reason: v2's checks existed once and were lost, so any later key edit was unverified. The corpus grows from 15 to 60 lines.

Budget gate is inside the same tester rather than a separate script, so it cannot be skipped by habit.

## Antislop

Curated list, no benchmark. Reason: the phrase-ban field is the fastest quality win available and a measured pass is a separate afternoon. Keep it a paste-ready file, because that is the only shape SillyTavern accepts.

## Risk

16K context. The whole book will approach 16k tokens, so entry length stays bounded at 120–260 and no entry is constant. If the gate trips, cut samples from the least-used entries first. SillyTavern's 25% budget still caps what loads.

## Not doing

No sampler changes, no DRY, no character-card edits, no ST/KoboldCpp source patches, no new dependencies.
