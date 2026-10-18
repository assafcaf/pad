---
name: writing-for-readers
description: Shapes any prose a human will read so the point lands first, the text fits a reader's working memory, and anything with a shape (process, system, comparison, trend, hierarchy, formula) is shown as a diagram, table or equation instead of narrated. Use this whenever the deliverable is text for a person to understand — a document, a README, a report or summary of the session's work written in the chat, an explanation, an answer longer than a paragraph, analysis, review, proposal, PR body, email, slide text, or a rewrite of someone else's draft — even when nobody asks for "clear" or "readable". Also use it to review or edit existing text for readability. Not for code, one-line facts, or casual chat.
---

# Writing for readers

Correct text is not the same as understandable text. A reader holds about four chunks in working memory, attaches each new fact to something they already know, and scans before reading. Text that ignores this — details before the point, equal weight on everything, shapes told as paragraphs — is correct and still hard to follow. This skill is the delivery layer: run it over whatever you were going to say.

Work in this order. Wording comes last because no sentence polish fixes a buried point.

## 1. Fix the reader and the point before writing

Answer three questions, silently or in one line if the request is ambiguous:

- **Who reads, and what do they already hold?** Novice, adjacent expert, or specialist. There is no universally clear text: what helps a novice (defined terms, explicit links) is extraneous load for an expert, and what helps an expert (sparse, dense) breaks for a novice. If the request doesn't say and a wrong guess would cost a rewrite, ask once.
- **What is the one thing they must leave with?** Write it as a single sentence. If you can't, you haven't found it yet. This sentence is not a summary (everything at lower resolution); it is the bottom line (the thing to act on or remember).
- **What will they do with it?** Decide, act, or understand. That sets the depth.

Default reader when unstated and the topic is technical: someone fluent in the field but new to this specific concept. See `references/technical-depth.md` for how to write at that level.

## 2. Structure: point first, then support ranked

- **First sentence = the answer, decision or claim.** If the reader stops there, they still got it. Background, method and caveats come after, because a frame given late arrives after the details have already been read with nowhere to attach.
- **Rank the support.** 3 to 5 points under the bottom line, in decreasing importance, each answering the question the line above raises. Ten equal bullets frame nothing; the reader can't tell what to keep.
- **Headings state findings, not topics.** "Retries cause the latency spike", not "Latency analysis". Readers scan the first words of headings and lines; make those words carry the message.
- **Context before content.** Any term, name or setup the reader needs to parse a section goes before that section, not inside it.
- **Signal evenly, or not at all.** Bold on half the key points makes the other half recalled worse than with no bold. Headings help only when the structure is complex; a three-paragraph answer gets none.
- **No recap ending.** "In summary..." restating the points costs memory and teaches nothing. End on the next step or the single caveat that matters.

## 3. Form: show the shape, don't narrate it

Before writing a section, ask whether its content has a shape. Prose is read one word at a time; a picture or table is read in parallel, and position does the work that labels and cross-references otherwise force the reader to do.

| If the content is... | Show it as | Not as |
| --- | --- | --- |
| A process with branches, loops, hand-offs | Flowchart or sequence diagram | Numbered paragraphs |
| A system: parts and what calls what | Architecture / block diagram | A list of components |
| A hierarchy or decomposition | Tree | Bullets nested more than 2 deep |
| Several options judged on several criteria | Table, criteria as columns | A paragraph per option |
| A quantity over time or across items | Line or bar chart | A list of numbers |
| A formula | Display equation, each symbol defined beside it | Inline prose math |
| One fact, two or three numbers, a yes/no | A sentence | Any visual |

A visual must earn its place: it says something the prose can't, carries a title that states the finding, and keeps labels next to what they label. Then the prose does not re-describe it box by box. Mechanics, encoding choices and the "is it earned" test are in `references/visuals.md`.

**Concrete before abstract.** Open with a worked case, number or example, then name the general rule. Abstraction is the writer's shortcut, not the reader's.

## 4. Selection: say exactly as much as needed

Extra true detail is not neutral; it competes for the same four slots. Excess is a failure of the same kind as omission.

- Remove anything the reader won't use for the purpose fixed in step 1. Optional depth goes below the main answer, or is offered in one line.
- Keep only caveats that would change the reader's decision. State each once, plainly, where it applies. A hedge on every sentence hides the one uncertainty that matters.
- No tangents ("it's also worth noting"). If it were worth noting, it would be in the ranked support.
- Match depth to expertise: don't define terms a specialist uses daily; don't skip steps a novice can't infer.

**Depth and density are separate dials.** The user may set either explicitly (`depth=headline|mechanism|derivation`, `density=tight|normal`); otherwise infer from the request. Depth is how far down you go (claim → mechanism → derivation); density is how many words you spend per idea. A derivation can be tight; a headline can be relaxed.

## 5. Sentences: feed the reader's model in order

- **Old before new.** Start each sentence with something the reader already holds (often the term the previous sentence ended on); end it with the new thing. Readers put emphasis on the end of a sentence, so a sentence that ends on a qualifier or citation wastes its strongest position.
- **One idea per sentence, one claim per paragraph.** Keep subject and verb close.
- **One name per concept.** Switching between "the model", "the network" and "the policy" makes the reader check whether a new thing appeared.
- **Plain words.** Short familiar words read as smarter, not dumber; needlessly long synonyms lower the reader's estimate of the writer. Jargon only when the reader shares it and it carries meaning. Active voice with a named actor.
- **Links explicit for novices, trimmed for experts.** "because", "so", "which means" help a reader who can't supply them; for an expert, filling the gap is what makes them think.
- **No stock phrases** ("delve", "it's worth noting", "in today's landscape"). Readers learn to skip them, and then skip what follows.

Hebrew and English mixed: keep each sentence in one language where possible; put English technical terms and code in their own inline spans; display equations on their own line, never inside RTL prose; tables in a single direction. See `references/technical-depth.md`.

## 6. Review as a demanding outsider

Before sending, read only the first line and the headings. Do they carry the message? Then run the anti-pattern scan in `references/anti-patterns.md` on anything longer than a few paragraphs: it names each failure, what it looks like, and the mechanism it breaks. For high-stakes text, have a fresh reviewer (a subagent that has not seen the draft) do this pass, so the writer isn't grading itself.

Clarity amplifies: easy-to-read text is judged more true, right or wrong. Be confident only where the evidence supports it, and say so once where it doesn't.

## When this skill should back off

- Code, config, commands: readability of code is a different discipline.
- A one-line fact or a yes/no: the sentence is the form.
- Casual conversation: structure there reads as cold.
- The user asked for exhaustive coverage (a spec, a legal review, a checklist): keep point-first and shape rules, drop the selection rules.

## References

- `references/anti-patterns.md` — 26 named failures with the mechanism each breaks; use as the review checklist.
- `references/visuals.md` — when a picture is earned, which form for which shape, encoding and labelling rules, Mermaid/table/equation mechanics.
- `references/technical-depth.md` — writing for an expert reader new to a specific concept: notation discipline, equation-first, "why this design choice", neighbours; Hebrew/English/LaTeX mixing.
- `references/evidence.md` — the research behind every rule here (cognitive load, given-new, BLUF, Mayer, Grice, fluency), with sources. Read when you need to judge an edge case rather than apply a rule.
