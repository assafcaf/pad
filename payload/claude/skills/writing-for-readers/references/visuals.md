# Visuals: when a picture is earned, and how to make one that works

## Why a picture can beat prose

Prose is read one word at a time; a diagram is indexed by location (Larkin & Simon 1987). A good diagram:

- puts everything needed for one inference in one place, so the reader doesn't search for it;
- binds facts to an element by position instead of by matching labels;
- lets perception do work that text forces the reader to compute (which path is longer, which node has more edges, which value is largest).

Pictures and concrete words are also stored in two memory codes, verbal and visual (Paivio), so they are recalled better than abstract prose.

None of this is free. A diagram that is not built to exploit those properties costs more to parse than the sentence it replaces.

## The "is it earned" test

Make the visual only if all three hold:

1. **The content has a shape.** Branching, calling, nesting, comparing on several axes, changing over time, or a formula. Linear narrative, one fact, two numbers, a yes/no: those are sentences.
2. **It says something the prose can't say as well.** The reader will *see* a bottleneck, a loop, a gap, a crossover, a dominant column, rather than compute it.
3. **It can carry a finding in its title.** If you can't write a title like "Retries double the tail latency" or "Option B wins on every criterion but cost", the visual has no point yet.

If the shape is small (two boxes, one arrow; a table with one row), use the sentence.

## Which form for which shape

| Shape | Form | Notes |
| --- | --- | --- |
| Steps with branches, loops, hand-offs | Flowchart | One decision per diamond. Label edges with the condition, not "yes/no" alone |
| Interactions between parties over time | Sequence diagram | Participants across the top; time runs down. Good for protocols, agent hand-offs, request lifecycles |
| States and transitions | State diagram | Only when there are ≥4 states or non-obvious transitions |
| Parts and what calls, owns or depends on what | Block / architecture diagram | Group by layer or boundary; arrows carry one meaning (data flow *or* dependency, not both unlabelled) |
| Hierarchy, decomposition, taxonomy | Tree | Replace any bullet list nested more than two levels deep |
| Entities and relations with cardinality | ER diagram | For schemas; otherwise a table is usually enough |
| Options × criteria | Table | Criteria as columns, options as rows. Put the deciding criterion first. Mark the winner per column |
| Quantity over time | Line chart | One series per line, ≤5 series, label at the line end rather than in a legend |
| Quantity across categories | Bar or dot chart | Sorted by value unless the categories have a natural order |
| Part of a whole | Stacked bar, or just the numbers | Not a pie: angle is judged poorly |
| Two quantities per item | Scatter | Annotate the outliers; they are usually the finding |
| Formula | Display equation | Each symbol defined in a short list beside or below it. Boxed if it is the result |
| Ordered events with dates | Timeline | Horizontal; only the events that matter |

## Encoding, in order of accuracy

People judge quantities most accurately from (Cleveland & McGill 1984):

1. position on a common scale (dot plot, bar chart baseline)
2. position on non-aligned scales (small multiples)
3. length (bars without a common baseline)
4. angle and slope (pie, line slope)
5. area (bubbles, treemaps)
6. colour saturation and volume

So: bars and dots for comparing values; lines for trends; colour for categories only, never for magnitude unless the comparison is coarse.

## Rules for the visual itself

From Mayer's multimedia principles and Tufte, the ones that apply to written answers:

- **Finding as title.** "Revenue fell 12% in Q3", not "Revenue by quarter".
- **Labels next to the thing** (spatial contiguity). No legend if direct labels fit. No explanation paragraph that the reader must map back onto the picture.
- **Remove what doesn't carry data** (coherence; data-ink). Gridlines light or gone, no 3D, no icons, no gradients. Decoration can aid memorability (Borkin; Bateman) but for explaining rather than persuading, lean minimal.
- **One idea per visual.** If it needs two titles, it is two visuals.
- **Segment.** A complex system is three small diagrams at increasing depth, not one dense one.
- **Names before the picture** (pre-training). Introduce the entities in a sentence before the diagram that arranges them, when the reader hasn't met them.
- **Don't re-describe.** After the visual, prose adds what the visual can't: the implication, the exception, the next step. It does not walk through the boxes.

## Mechanics by medium

**Markdown / chat**

- Tables: Markdown tables. Keep to ≤6 columns; beyond that, transpose or split.
- Diagrams: Mermaid (`flowchart`, `sequenceDiagram`, `stateDiagram-v2`, `classDiagram`, `erDiagram`, `gantt`). Keep node labels under ~6 words; put detail in the prose. Direction `LR` for processes, `TB` for hierarchies.
- Equations: `$$ ... $$` display blocks; `$...$` inline only for a single symbol. Define symbols in a compact list, not a sentence.
- Charts: an inline chart tool if one exists; otherwise a sorted table of the numbers with the finding stated above it.

**Documents, artifacts, slides**

- Same rules; prefer native tables and SVG/Mermaid over screenshots so the reader can select and the text stays searchable.
- Place the visual immediately after the sentence that motivates it, never on the next page or at the end.

**Code-adjacent docs (README, design doc)**

- Architecture: one block diagram at the top, then one per subsystem where needed.
- Data flow and request lifecycle: sequence diagram.
- Config or API options: table (option, type, default, effect), not prose per option.

## Checklist before shipping a visual

- [ ] Title states the finding.
- [ ] A reader can name the point in five seconds.
- [ ] Every label is adjacent to its element; no legend hunting.
- [ ] Nothing on it fails to carry data.
- [ ] The prose after it does not narrate it.
- [ ] Encoding matches the judgement asked (position for compare, line for trend).
