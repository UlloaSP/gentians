# Alzheimer's drug design — amine

Learn the amine-property comparison between two compounds.

**Source:** https://huggingface.co/datasets/andrewcropper/ilp-datasets/resolve/33e166058404fd5eec3ec0f5080df9befbe884a8/alzheimer/amine/train/ (MIT license).

**Target:** `great_ne(A,B)` compares two compounds. The background describes alkyl counts, ring and R-group substituents, and physicochemical properties such as polarity, donor/acceptor values, flexibility, and size.

## Data and language

`bk.lp` contains 628 background statements. `exs.lp` contains 274 positive and 274 negative examples.
`bias.lp` declares 1 head mode and 31 body modes. Limits: `#maxv(6)`, `#maxbl(5)`, `#maxhl(1)`, `#maxpl(3)`.

The facts and examples come from the linked Popper task. Its predicate types were translated to directed Gentians modes; the recalls and structural limits are Gentians search bounds, not source declarations.
