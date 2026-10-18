# Technical depth: writing for an expert who is new to this specific thing

Most readability advice simplifies for a general audience. The harder and more common case in technical work is a reader who is fluent in the field but has not met this particular concept, method or system. Simplifying for them is expertise reversal (it burdens them); dumping the full detail is the curse of knowledge (it buries them). This file is the middle path.

## The shape of a good technical explanation

In this order. Each layer stands on its own, so the reader can stop when they have what they need.

1. **Headline (1–2 sentences).** What it is and what it buys you, in the reader's own vocabulary. "X is a Y that does Z, so that W becomes possible/cheaper/stable."
2. **Why it exists.** The failure of the obvious or prior approach, in one concrete case. This is the complication that makes the mechanism worth reading.
3. **Mechanism.** The core idea, equation-first where there is one, then the intuition that the equation makes precise. Then the one design choice that makes it work, and why that choice rather than the obvious alternative.
4. **Where it sits.** Two or three neighbours: what it generalises, what it is a special case of, what the modern successor is. Name the differences in one clause each.
5. **When it breaks.** The assumption that, if violated, makes it fail. One sentence.
6. **Derivation, proofs, edge cases, hyperparameters.** Only if the purpose calls for it, below a visible break, or offered.

Depth dial: `headline` = 1–2; `mechanism` = 1–5; `derivation` = all six. Density is separate: any depth can be written tight or relaxed.

## Equation-first, intuition second

For a reader with the background, the equation is the fastest and least ambiguous statement of the idea, and the prose around it tells them which part to look at. Prose-first forces them to reconstruct the equation and then check it against yours.

- State the object, then the equation, then one sentence per term that carries the idea. Not every term; the ones that differ from what the reader would have written.
- Then the intuition, framed as *what the equation does*, not as a separate metaphor.
- Then the design choice: "The thing that makes this work is [choice]. The alternative [other] would [failure]."

Pattern:

> The loss adds a KL penalty to the policy objective:
>
> $$ L(\theta) = \mathbb{E}\left[r(x, y)\right] - \beta\, D_{KL}\!\left(\pi_\theta \,\|\, \pi_{\text{ref}}\right) $$
>
> where $\pi_{\text{ref}}$ is the frozen starting policy and $\beta$ sets how far the policy may drift. The penalty is what keeps the reward model in-distribution: without it, $\pi_\theta$ finds inputs where $r$ is high and wrong.

## Notation discipline

- **Define every symbol at first use**, in a compact list beside the equation, not spread through a paragraph. Readers scan for "where …".
- **One symbol per object, one object per symbol.** Don't reuse $x$ for an input and later for a state. Don't call the same thing $h$ and $z$.
- **Match the reader's conventions** when the field has them ($\theta$ for parameters, $\pi$ for a policy, $\mathcal{L}$ for a loss). Deviating costs a translation step on every read.
- **Shapes and types in plain words** when they matter: "a matrix of size $n \times d$", "a distribution over actions", not left for the reader to infer.
- **Display equations for anything with more than two symbols.** Inline math is for a single symbol in a sentence.
- **Name the equation when you'll refer back to it.** "(the update rule)", not "the above".

## Terms and names

- Introduce a new term with the thing it names in the same sentence, then use only that term. "The critic (the network estimating $V(s)$) …" then "the critic" every time.
- Don't define terms a specialist in the stated field uses daily. For a graduate ML reader: gradient, softmax, attention, KL divergence, policy need no definition; a specific algorithm's variant does.
- When a term has several meanings across subfields, say which one once. "Here *reward model* means a learned scalar predictor, not the environment's reward function."

## Neighbours and lineage

A new method is understood by where it sits. Give two or three relations, one clause each, in a table if there are more than two:

| Relation | Phrase |
| --- | --- |
| Generalises | "X reduces to Y when [condition]" |
| Special case of | "X is Z with [restriction]" |
| Replaces / succeeds | "X drops Y's [component] by [mechanism]" |
| Same goal, different route | "X and Y both target [goal]; X does it via [a], Y via [b]" |

The reader attaches the new thing to the old one; the given-new contract at the level of concepts.

## Code and config in explanations

- Show the minimal snippet that demonstrates the idea, not the whole file. Elide with `...` and say what was elided.
- Put the line that matters first or mark it with a comment; readers scan code the way they scan prose.
- Options and parameters: a table (name, type, default, what it changes), never a paragraph per option.
- A sequence of calls across components: a sequence diagram, not a numbered list of function names.

## Hebrew and English together

Mixed-direction text breaks in predictable places. Rules that avoid the breaks:

- **One language per sentence where possible.** Switching mid-sentence forces the reader to re-orient direction and makes punctuation land on the wrong side.
- **English technical terms inside Hebrew prose:** keep them as a short span, and if the term has a standard Hebrew form the reader uses, prefer it; otherwise leave the English term untranslated rather than coining one.
- **Code, identifiers, paths:** always in backticks, which also isolates their direction.
- **Equations:** always display-mode on their own line. Never embed LaTeX inside an RTL sentence; the symbols and the prose fight over direction.
- **Tables:** one direction for the whole table. If the cells are mostly English or numeric, make the table LTR with Hebrew headers; if mostly Hebrew, RTL throughout.
- **Lists:** one language per list item's first words, so the bullet alignment stays consistent.
- **Numbers and units:** LTR always; put a space between number and unit so the renderer doesn't flip them.

## Review questions specific to technical text

- Could the reader write down the core equation or mechanism after one read?
- Is there exactly one design choice named as the thing that makes it work, with the alternative and its failure?
- Does every symbol have a definition the reader can find in under two seconds?
- Are the neighbours named, so the reader knows where to file it?
- Is the depth the reader asked for, and is everything beyond it below a break?
