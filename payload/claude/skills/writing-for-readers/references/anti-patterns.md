# Anti-pattern catalogue

Use this as the review pass. Each row names the failure, what it looks like on the page, and the mechanism it breaks, so you can judge borderline cases rather than pattern-match. Scan in this order: structure first (a buried point can't be fixed by word choice), then selection, then visuals, then sentences, then trust.

## Structure

| Anti-pattern | Looks like | Why it fails |
| --- | --- | --- |
| Buried lede | Background, method, caveats, then the answer in paragraph four | Details arrive before the frame they attach to (Bransford & Johnson); the reader stores them loosely and the point competes with them for memory |
| Flat emphasis | Ten bullets of equal weight, no ranking | Framing by omission: what comes first and what is repeated tells the reader what matters (Entman). Ten items also exceeds the 3–5 chunks a reader can hold (Cowan) |
| Topic headings | "Overview", "Analysis", "Considerations", "Latency" | Scanners read headings and first words (NN/g F-pattern). A topic heading tells them where they are, not what was found |
| Selective signalling | Bold on some key points, not others; headings on some sections only | Signals direct attention. Unsignalled content is recalled worse than in a text with no signals at all (Lorch & Lorch 1996) |
| Decorative structure | Headings and bullets on a three-paragraph answer | Signals only help when the structure is complex; otherwise they are extraneous load and read as padding |
| Recap ending | "In summary..." restating the same points | Redundancy effect (Sweller): processing repeated content costs memory and adds nothing. End on the next step or the one caveat that matters |
| Context after content | A section that uses a term, then defines it; a setup given at the end | Same mechanism as the buried lede at section scale. Pre-training principle (Mayer): names before the explanation that uses them |

## Density and selection

| Anti-pattern | Looks like | Why it fails |
| --- | --- | --- |
| Exhaustiveness | Every edge case, option and caveat for a narrow question | Violates Grice's quantity maxim (as informative as required, and **not more**); extraneous load. Readers assume every sentence is there for a reason and search for significance that isn't there |
| Caveat cloud | "It depends", "generally", "in many cases" on every claim | Hides which uncertainty actually matters; each hedge occupies the sentence's stress position |
| Detail before point | Parameters, flags, sub-cases before the reader knows why they matter | Fills the four slots before the frame arrives |
| Over-explaining to experts | Defining terms the reader uses daily; spelling out every logical link | Expertise reversal (Sweller et al. 2003): guidance that helps novices becomes load for experts. High-knowledge readers learn more from sparser text (McNamara & Kintsch) |
| Under-explaining to novices | Undefined symbols, skipped steps, implied links | The reader can't build a situation model from the textbase; they must infer what the text should have stated |
| Tangent | "It's also worth noting...", "As an aside..." | Relation maxim. If it were worth noting it would be in the ranked support; if not, it is noise |
| Length as thoroughness | A long answer offered as proof of care | Writer's virtue mistaken for reader's benefit. LLM judges prefer length more than humans do (Saito et al. 2023), so the habit is trained in and must be trained out |

## Visuals

| Anti-pattern | Looks like | Why it fails |
| --- | --- | --- |
| Shape told as prose | A process with branches, or a system of parts, described in paragraphs | Prose is sequential; the reader must search and hold cross-references. A diagram puts everything needed for one inference in one place (Larkin & Simon) |
| Picture plus re-description | A diagram followed by text narrating every box | Redundancy effect (Sweller; Mayer's coherence principle) |
| Decoration | Icons, gradients, images that don't carry data | Coherence principle: extraneous material hurts learning (Mayer); non-data ink (Tufte) |
| Separated labels | A legend or key far from what it explains; explanation in a paragraph below | Split attention; violates spatial contiguity (Mayer) |
| Wrong encoding | Pie or bubble chart to compare values; 3D anything | Position on a common scale is judged most accurately, then length, then angle, then area (Cleveland & McGill) |
| Topic title on a chart or diagram | "Revenue by quarter", "System architecture" | The reader must find the finding. "Revenue fell 12% in Q3" gives it. A finding title is the one annotation always worth its ink |
| Unearned visual | A diagram for two boxes and one arrow; a table with one row | The visual costs more to parse than the sentence it replaces. Use the sentence |

## Sentences and words

| Anti-pattern | Looks like | Why it fails |
| --- | --- | --- |
| New before given | A sentence opening with an unfamiliar term, then linking it back | Breaks the given-new contract (Haviland & Clark): the reader searches memory for a hook, fails, and restructures |
| Weak ending | Sentences ending in qualifiers, citations or parentheticals | Wastes the stress position, where readers place emphasis (Gopen & Swan) |
| Subject–verb gap | A 20-word clause between subject and verb | The reader holds an incomplete proposition in working memory until the verb arrives |
| Synonym drift | "model", "network", "policy" for the same object | The reader must check whether a new entity appeared. One name per concept |
| Needless complexity | "Utilise", "leverage", "facilitate", "methodology" for "method" | Lowers the perceived intelligence of the writer (Oppenheimer 2006); slower to process |
| Nominalisation and passive | "An optimisation was performed", "the decision was made" | Hides actor and action (Orwell; AR 25-50). Who did what? |
| Stock phrases | "It's worth noting", "delve", "in today's landscape", "a testament to" | Stale phrasing that readers learn to skip, and then they skip what follows it |
| Many ideas per sentence | Three clauses joined by semicolons and "while" | Writers produce text at the density of their own thinking; one idea per sentence lets the reader unpack at reading speed |

## Trust

| Anti-pattern | Looks like | Why it fails |
| --- | --- | --- |
| Fluency without accuracy | A polished, confident answer that is wrong | Easy-to-process text is judged more true (Reber & Schwarz). Clarity amplifies errors; it raises the obligation to be right |
| Story without the claim | A compelling example with the conclusion left implicit | Narrative transportation reduces scrutiny (Green & Brock). State the claim plainly next to the story |
| Uniform confidence | Same tone for a measured fact and a guess | Quality maxim (Grice). Mark the one or two places where the evidence is thin; everywhere else, be direct |

## Quick scan, in order

1. First sentence: is it the answer?
2. Headings and bold: findings, applied evenly, only where structure is complex?
3. Anything with a shape still in prose? Any visual that merely decorates or is re-described?
4. Anything the reader won't use? Any caveat that wouldn't change their decision?
5. Sentence openings: known → new? Endings: on the point?
6. Where is the evidence thin, and is that the only place the text hedges?
