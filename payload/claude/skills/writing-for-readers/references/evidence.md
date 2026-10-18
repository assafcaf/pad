# Evidence: what makes text understandable

The research behind every rule in SKILL.md, by discipline. Read this when a rule and a case disagree and you need the mechanism to decide, not to apply a rule you already have.

Contents: ten laws · why LLM answers are hard to follow · cognitive psychology (load, redundancy, expertise reversal, schemas) · psycholinguistics (given-new, stress position, cohesion) · structure (BLUF, pyramid, scanning, signals) · visualization (Larkin & Simon, dual coding, Mayer, Cleveland & McGill, Tufte) · rhetoric (ELM, framing, stickiness, transportation, analogy) · philosophy and plain language (Grice, Orwell, fluency) · anti-patterns · references.


## TL;DR: ten laws of understandable text

Text is understandable when it fits the reader's working memory, matches what they already know, and tells them the point before the details. Every discipline below converges on that. The ten laws:

1. **Point first.** State the answer, decision or claim in the first sentence. Details serve it; they never precede it.
2. **One idea per unit.** One idea per sentence, one claim per paragraph, one question per section.
3. **Write for the reader's knowledge, not yours.** Guidance that helps a novice burdens an expert, and vice versa. Decide who reads before writing.
4. **Old before new.** Open each sentence with something the reader already holds; end it with the new thing you want them to notice.
5. **Show the structure, don't narrate it.** Flows, hierarchies, comparisons and change over time are pictures or tables, not paragraphs.
6. **Cut what doesn't serve the point.** Extra true detail is not neutral: it competes for the same limited attention.
7. **Concrete before abstract.** An example, case or number first; the general principle after.
8. **Signal the map.** Headings that state findings, explicit transitions, and one visual emphasis per screen.
9. **Plain words.** Short familiar words read as smarter, not dumber. Jargon only when it carries meaning the reader shares.
10. **Say exactly as much as needed.** Not less (gaps the reader must fill) and not more (padding the reader must filter).



## Why good LLM answers are still hard to follow

The content is usually correct; the failure is in delivery. Three well-documented mechanisms explain the symptoms you described: too much text, details that bury the point, and no pictures.

**1. The curse of knowledge.** A writer who knows something cannot easily imagine not knowing it. The term comes from Camerer, Loewenstein and Weber (1989). Its classic demonstration is Elizabeth Newton's 1990 tapping study: people who tapped a familiar song's rhythm predicted listeners would name about half the songs, but listeners named only 2.5% ([source](https://tactics.convertize.com/definitions/curse-of-knowledge)). The tapper hears the melody; the listener hears knocking. An LLM is the extreme tapper: it has every detail active at once and no model of what you hold.

**2. Working memory is tiny.** Adults hold roughly 3 to 5 independent chunks at once, not Miller's famous 7 ([Cowan 2001](https://www.cambridge.org/core/journals/behavioral-and-brain-sciences/article/magical-number-4-in-shortterm-memory-a-reconsideration-of-mental-storage-capacity/44023F1147D4A1D44BDC0AD226838496)). Every caveat, parameter or side-branch introduced before the main claim occupies a slot. By the time the point arrives, there is no room left to hold it.

**3. Training rewards length.** LLM judges prefer longer answers more than humans do, even when quality is similar ([Saito et al. 2023](https://arxiv.org/abs/2310.10076v1)). Models tuned on such feedback learn that thoroughness scores well. Thoroughness is the writer's virtue; selection is the reader's.

The common root: **the text is organised around what the writer knows, not around what the reader needs next.** Every section below is a different discipline's answer to that one problem.

## Cognitive psychology: fit the text to a small, knowledge-dependent memory

Understanding happens in a working memory of about four chunks, and what counts as one chunk depends on what the reader already knows. Most writing advice follows from those two facts.

**Cognitive load theory (Sweller, 1980s onward).** Load comes in three kinds ([LITFL summary](https://litfl.com/cognitive-load-theory/)):

| Load | What causes it | What the writer does |
| --- | --- | --- |
| Intrinsic | How many elements of the idea interact | Manage it: sequence, build up in steps |
| Extraneous | How the idea is presented | Eliminate it: every word, layout choice or detour the reader must process but learns nothing from |
| Germane | Effort spent building understanding | Protect it: leave room for the reader to think |

The loads add up. Cutting extraneous load frees capacity for a hard idea.

**The redundancy effect.** Information the reader doesn't need is not harmless: processing it costs working memory. Sweller's example is a diagram accompanied by words that merely re-describe it; those words should be cut ([Teacher Magazine](https://www.teachermagazine.com.au/articles/cognitive-load-theory-teaching-strategies)).

**The expertise reversal effect.** Techniques that help novices can lose their benefit, or even hurt, for experienced readers ([Sweller, Ayres, Kalyuga & Chandler 2003](https://ro.uow.edu.au/articles/journal_contribution/The_expertise_reversal_effect/27724950/1)). In one study, experts learned better from a diagram alone and novices from a diagram plus text ([summary](https://brainscape.com/flashcards/technology-cognitive-load-3114180/packs/4933288)). Implication: there is no universally "clear" text. Clarity is a fit between text and reader, so the writer must decide who the reader is first.

**Schemas: context must come before content.** Bransford and Johnson (1972) gave people a passage that is opaque without its topic (it describes doing laundry without saying so). Supplying the context before the passage raised comprehension and recall; supplying the same context afterwards helped much less ([abstract](https://paperguide.ai/papers/06070657-76e0-4355-b53c-5dfe9979bf2f/)). A frame given at the end arrives too late: the details were already read without anywhere to attach.

**What this means in practice**

- Name the topic and the conclusion before the details: the frame is what makes details memorable.
- Hold at most 3 to 5 new items in play at once; group the rest under a label.
- Decide the reader's level explicitly. Explaining basics to an expert is extraneous load; skipping them for a novice breaks intrinsic load into pieces they can't assemble.

## Psycholinguistics: readers build a model, and sentences must feed it in order

Readers don't store sentences; they build a mental model of the situation and hook each new fact onto something already in it. Text is easy when every sentence offers a hook before it offers the new fact.

**Three levels of representation (Kintsch & van Dijk).** Comprehension produces a surface code (the words), a textbase (the propositions and how they link), and a situation model (the textbase merged with the reader's own knowledge) ([summary](https://aura-lab.siue.edu/theories/model-of-text-comprehension/)). Understanding means a good situation model. A text can be fully accurate at the textbase level and still leave no usable model, which is exactly what a correct but hard-to-follow LLM answer does.

**The given-new contract (Haviland & Clark 1974; Clark & Haviland 1977).** Listeners split each sentence into what they already know and what is new, find the known part in memory, and attach the new part to it ([summary](https://d.lib.msu.edu/etd/41917/FULL_TEXT/view)). When a sentence opens with something unfamiliar, the reader has to search, restructure, or guess. Each such moment is a small stall; many in a row read as "hard to follow".

**Topic and stress positions (Gopen & Swan 1990).** Readers expect the start of a sentence to give context and link back, and the end to deliver the emphasis. Put old information that links backward at the start and the new point you want noticed at the end ([source](https://www.win.tue.nl/~wstomv/quotes/science-of-scientific-writing.html)). Keep subject and verb close; a long gap between them interrupts the reader ([summary](https://sites.sandiego.edu/wp-cadw/2023/02/27/the-science-of-scientific-writing-by-george-gopen-and-judith-swan/)). Gopen and Swan treat misplaced stress positions as the main problem in professional scientific prose ([AcaWiki](https://acawiki.org/The_Science_of_Scientific_Writing)).

The same rule scales up: the first sentence of a paragraph is its topic position, the last its stress position. So is the first and last sentence of a whole answer.

**Cohesion helps novices and can bore experts.** McNamara and Kintsch manipulated how explicitly texts spelled out the links between ideas. Low-knowledge readers learned more from highly cohesive text; high-knowledge readers sometimes did better with sparser text, because filling the gaps made them think ([Frontiers summary](https://www.frontiersin.org/journals/education/articles/10.3389/feduc.2020.00026/epub)). This is the expertise-reversal effect again, at the sentence level.

**What this means in practice**

- Start each sentence with the term the previous sentence ended on.
- End each sentence, paragraph and answer on the thing you want remembered.
- Use one name per concept. Switching between synonyms ("the model", "the network", "the policy") makes the reader check whether they are new things.
- Make links explicit (because, so, but, which means) for readers new to the topic; trim them for experts.

## Structure: the military, consulting and journalism all landed on "answer first"

Three professions that write for busy, high-stakes readers independently converged on the same rule: put the conclusion at the top, then support it in decreasing order of importance.

| Tradition | Rule | What it adds |
| --- | --- | --- |
| US Army, AR 25-50 (BLUF) | Put the purpose, recommendation or conclusion in the first sentence or paragraph; use active voice ([overview](https://legalclarity.org/bottom-line-up-front-bluf-what-it-is-and-how-to-use-it/)) | The stated reason: ineffective writing fails to transmit a focused message quickly ([Wikipedia](<https://en.wikipedia.org/wiki/BLUF_(communication)>)) |
| McKinsey, Minto's Pyramid Principle | Answer at the top, 3 to 5 supporting arguments below it, evidence at the base ([summary](https://www.supernormal.com/blog/mckinsey-presentation-playbook)) | Each level answers the question the level above raises. Openings use Situation, Complication, Question, Answer (SCQA) |
| Journalism, inverted pyramid | Most important facts first, background last | A reader can stop at any paragraph and still have the most important part |

The bottom line is not a summary. A summary restates everything at lower resolution; a bottom line is the one thing the reader must take away or act on ([Strom](https://matthewstrom.com/writing/bluf)).

**Readers scan before they read.** In Nielsen Norman Group's tests, 79% of users scanned any new page and only 16% read word by word. They tend to read in an F-shape: across the top, across a little lower, then down the left edge, catching only the first words of each line. The practical rule is to start headings, paragraphs and bullets with the information-carrying words ([JHU guide](https://sites.krieger.jhu.edu/using-your-site/web-writing/)).

**Headings change what gets remembered.** Signals are devices that emphasise a text's structure without adding content: titles, headings, previews, summaries, typographic cues ([Lorch 1989](https://link.springer.com/doi/10.1007/BF01320135)). Lorch and Lorch found headings, overviews and summaries made no difference for simple texts but changed recall for complex ones. When only half the topics were signalled, the unsignalled half was recalled worse than in a text with no signals at all ([Lorch & Lorch 1996](https://scholars.uky.edu/es/publications/effects-of-organizational-signals-on-free-recall-of-expository-te/)). Signals direct attention, so they must be applied evenly, and only where structure is complex.

**What this means in practice**

- First line = the answer. If the reader stops there, they still got it.
- Headings that state the finding ("Retries cause the latency spike") beat headings that name the topic ("Latency analysis").
- Group supporting points under 3 to 5 headings; deeper detail goes below or into an appendix.
- Don't add headings to a three-paragraph answer; structure is a tool for complexity, not decoration.

## Visualization: when a picture beats prose, and when it doesn't

A picture wins when the content has a spatial or relational shape, because the eye reads layout in parallel while prose must be read one word at a time. A picture loses when it only decorates or repeats the text.

**Why diagrams work (Larkin & Simon 1987).** Prose is sequential; a diagram is indexed by location. A diagram groups everything needed for one inference in one place, so the reader doesn't search for it; it uses position to bind facts to an element instead of matching labels; and it lets perception do inferences that text forces you to compute ([summary](https://www.goodreads.com/author_blog_posts/20533703-diagrams-versus-words?tab=book)). The "sometimes" in their title matters: a diagram only helps if it is built to exploit those properties.

**Two memory codes (Paivio's dual coding).** Concrete words and pictures can be stored both verbally and as images, so they are recalled better than abstract words, which get only a verbal code ([summary](https://loterre.istex.fr/P66/en/page/-R0V3S7S8-W)). Recent work with people who lack mental imagery questions the mechanism but still finds the picture-superiority effect ([UChicago](https://knowledge.uchicago.edu/record/15350)): the effect is robust even if the explanation is debated.

**Mayer's multimedia principles** are the most-tested rules for combining words and visuals ([Notre Dame summary](https://twut.nd.edu:443/PDF/Principles-MultimediaLearning.pdf)). The ones that apply to written answers:

| Principle | Rule |
| --- | --- |
| Multimedia | Words plus pictures beat words alone |
| Coherence | Exclude extraneous words, pictures and decoration |
| Signaling | Add cues that highlight the essential material and its organisation |
| Spatial contiguity | Put labels and explanations next to what they describe, not in a separate legend or paragraph |
| Segmenting | Present complex material in reader-paced pieces, not one continuous stream |
| Pre-training | Introduce names and key concepts before the explanation that uses them |
| Personalization | Conversational style beats formal style |

**Choosing the encoding (Cleveland & McGill 1984).** People judge quantities most accurately from position on a common scale, then position on non-aligned scales, then length, then angle and slope, then area ([FlowingData](https://flowingdata.com/2010/03/20/graphical-perception-learn-the-fundamentals-first)). So a bar or dot chart beats a pie chart or bubble chart for comparing values.

**Decoration is a trade-off, not a free lunch.** Tufte argues every bit of ink that doesn't show data should go ([lecture notes](https://teaching.vda.univie.ac.at/vis/23s/LectureNotes/02_DesignPrinciples.pdf)). Borkin et al. (2013) found colour and recognisable objects made charts more memorable at a glance ([Harvard](https://vcg.seas.harvard.edu/publications/20130101-what-makes-a-visualization-memorable)), and Bateman et al. found embellishment can aid recall without hurting interpretation ([paper](https://vis.csail.mit.edu/classes/6.859/readings/pdfs/Bateman-UsefulJunk.pdf)). For explaining, not persuading, lean towards Tufte; a title that states the finding is the one annotation always worth its ink.

**Matching content shape to form**

| If the content is... | Use | Not |
| --- | --- | --- |
| A process with branches, loops or hand-offs | Flowchart or sequence diagram | Numbered paragraphs |
| A system: parts and what calls what | Architecture diagram | A list of components |
| A hierarchy or decomposition | Tree | Nested bullets more than 2 levels deep |
| Several options judged on several criteria | Table | Paragraph per option |
| A quantity over time or across items | Line or bar chart | A list of numbers |
| A formula | Display equation, every symbol defined beside it | Inline prose math |
| One fact, two or three numbers, a yes/no | A sentence | Any visual |

## Rhetoric, persuasion and political communication: what makes an idea land and stay

Persuasion research studies the same problem from the other end: not "was it understood?" but "did it get through attention, survive, and change something?" Its lessons transfer directly to explanation.

**Two routes into the mind (Petty & Cacioppo's Elaboration Likelihood Model).** When readers are motivated and able, they scrutinise the arguments (the central route); when either is missing, they fall back on surface cues like length, polish or confidence (the peripheral route) ([Springer chapter](https://www.springermedicine.com/chapter/10.1007/978-1-4612-4964-1_7)). Both motivation and ability are required for the central route ([Simply Psychology](https://www.simplypsychology.org/elaboration-likelihood-model.html)). Attitudes formed centrally last longer and resist counter-arguments better. For writing: a reader who can't follow the argument doesn't evaluate it, they judge it by its look. A long, confident wall of text invites exactly that shallow judgement.

**Framing is selection and salience (Entman 1993).** To frame is to choose some aspects of reality and make them more prominent, which steers the reader towards a particular problem definition, cause, judgement or remedy. Salience comes from placement, repetition, and association with familiar symbols ([excerpt](https://people.willamette.edu/~ccollins/framing/allenm/selectionandsalience.htm)). Every explanation frames, whether the writer intends it or not. What comes first, what is repeated and what is left out tells the reader what matters. An answer that gives ten points equal weight has framed nothing, and the reader can't tell what to keep.

**Stickiness (Heath & Heath, *Made to Stick*, 2007).** Ideas that survive share six traits: simple (one core message), unexpected (breaks a prediction, so attention switches on), concrete, credible, emotional, and told as stories ([summary](https://oa.mo.gov/leadership-library/15501)). Two of their points matter most here: abstraction is often an unintended side effect of expertise, and concrete details give memory more hooks ([Christian Science Monitor](https://csmonitor.com/2007/0123/p15s02-bogn.html)).

**Narrative transportation (Green & Brock 2000).** Readers absorbed in a story focus all their attention on it and update beliefs towards it, and while absorbed they are less aware of facts that contradict it ([Springer](https://link.springer.com/chapter/10.1007/978-3-031-63284-6_3)). For explanation, use the first half: a short worked case or scenario captures attention better than a list. Be careful with the second half: a story can carry a claim past the reader's scrutiny, which is a reason to state the claim plainly next to the story.

**Analogy and concreteness fading.** Gentner's structure-mapping theory holds that a good analogy transfers a system of relations from a familiar domain to a new one, not surface features; people prefer analogies that map connected relations ([summary](https://arxiv.org/pdf/2001.06668)). Fyfe and colleagues reviewed concrete versus abstract teaching and recommend starting concrete, then explicitly fading to the abstract form, so symbols stay grounded while the generalisable structure is extracted ([Fyfe et al. 2014](https://pc.cogs.indiana.edu/?p=885)).

**Aristotle's three appeals still describe the job.** Logos (the argument), ethos (why the reader should trust the source) and pathos (why the reader should care). Technical writing usually supplies only logos. One sentence on why this matters to the reader, and an honest note on how sure we are, cover the other two.

**What this means in practice**

- One core message per answer. If you can't say it in a sentence, you haven't found it yet.
- Open with a concrete case or example, then name the general principle.
- Use an analogy only when its relations map; say where it breaks.
- Weight what you emphasise. Equal emphasis on everything is no emphasis.
- Say why it matters to this reader before the mechanism.

## Philosophy and plain language: clarity as an obligation

Philosophers and lawmakers arrive at the same place as the psychologists, but frame clarity as a duty the writer owes the reader rather than a technique.

**Grice's cooperative principle (1975).** Communication works because both sides assume the other is contributing what the exchange requires. Grice broke this into four maxims ([summary](https://www.futilitycloset.com/2019/04/08/grices-maxims/)):

| Maxim | Rule | Typical LLM violation |
| --- | --- | --- |
| Quantity | As informative as required, and **not more** | Exhaustive answers to narrow questions |
| Quality | Say only what you believe true and have evidence for | Confident claims without signalling uncertainty |
| Relation | Be relevant | Tangents, "it's also worth noting" |
| Manner | Avoid obscurity and ambiguity; be brief and orderly | Jargon, hedged phrasing, buried point |

The second half of the quantity maxim is the one most often ignored: excess information is a violation, not a bonus. Readers also assume every sentence is there for a reason, so padding makes them search for a significance that isn't there.

**Orwell, "Politics and the English Language" (1946).** His six rules: avoid stock figures of speech; never use a long word where a short one will do; cut every word you can; prefer active to passive; prefer everyday words to jargon or foreign phrases; and break any rule rather than write something barbarous ([Duke](https://sites.duke.edu/scientificwriting/orwells-6-rules/)). His deeper point is that vague language both reflects and causes vague thinking.

**Schopenhauer, "On Style" (1851).** He held that style is the silhouette of thought, and that obscure or vague expression is always a bad sign ([The Marginalian](https://www.brainpickings.org/2014/03/20/schopenhauer-on-style/)). He also warned that many writers hide poverty of thought under a flood of words ([Wist](https://wist.info/topic/logorrhea/)). His advice, in short: common words for uncommon things.

**Plain language law.** The US Plain Writing Act of 2010 requires agencies to write so the public can understand and use what they read. The federal guidelines order the work as: audience first, then organisation, then words, sentences and paragraphs, then testing with real readers ([plainlanguage.gov](https://plainlanguage.gov/guidelines/)). The order is the lesson: wording comes third.

**The empirical backing: fluency.**

- Needlessly complex vocabulary makes readers rate the author as *less* intelligent. Oppenheimer (2006) replaced words in real writing samples with their longest thesaurus synonyms and found the complex versions lowered ratings of the author ([Daily Princetonian](https://www.dailyprincetonian.com/article/2006/10/on-erudite-vernacular-i-e-big-words)).
- Easy-to-process statements are judged more true, more familiar and more pleasant; Reber and Schwarz found statements printed in easier-to-read colours were more often accepted ([Schwarz, Daedalus](https://www.amacad.org/publication/daedalus/judgments-truth-beauty)).

Fluency cuts both ways. It makes a correct explanation land, but it also makes a wrong one convincing. Clear writing raises the obligation to be right; it does not replace it.

## Bad practices: an anti-pattern catalogue

Each anti-pattern below violates at least one finding above. The right column names the mechanism, so you can tell why it hurts, not just that it does.

**Structure**

| Anti-pattern | Looks like | Why it fails |
| --- | --- | --- |
| Buried lede | Background, method, caveats, then the answer in paragraph four | Context-after-content: details arrive with no frame to attach to (Bransford & Johnson); violates BLUF |
| Flat emphasis | Ten bullets of equal weight, no ranking | Framing by omission: the reader can't tell what to keep (Entman); exceeds 3 to 5 chunk capacity (Cowan) |
| Topic headings | "Overview", "Analysis", "Considerations" | Headings signal structure but not findings; a scanner learns nothing (Lorch; F-pattern) |
| Selective signalling | Bold on some key points but not others | Unsignalled content is recalled worse than with no signals at all (Lorch & Lorch 1996) |
| Recap ending | "In summary..." restating the same points | Redundancy effect: processing repeated content costs memory and teaches nothing |

**Density and selection**

| Anti-pattern | Looks like | Why it fails |
| --- | --- | --- |
| Exhaustiveness | Every edge case, option and caveat for a narrow question | Violates Grice's quantity maxim; extraneous load (Sweller) |
| Caveat cloud | "It depends", "generally", "in many cases" on every claim | Hides which uncertainty actually matters; blocks the stress position |
| Detail before point | Parameters, flags, sub-cases before the reader knows why they matter | Fills working memory before the frame arrives |
| Over-explaining to experts | Defining terms the reader uses daily | Expertise reversal: guidance becomes extraneous load |
| Under-explaining to novices | Undefined symbols, skipped steps | Reader can't build the situation model; must infer what the text should state (McNamara & Kintsch) |

**Sentences and words**

| Anti-pattern | Looks like | Why it fails |
| --- | --- | --- |
| New-before-given | Sentences that open with an unfamiliar term | Breaks the given-new contract; reader must search and restructure |
| Weak endings | Sentences ending in qualifiers or citations | Wastes the stress position, where readers put emphasis (Gopen & Swan) |
| Subject-verb gap | A 20-word clause between subject and verb | Reader holds an incomplete proposition in working memory |
| Synonym drift | "model", "network", "policy" for the same thing | Reader must check whether a new entity appeared |
| Needless complexity | "Utilise", "leverage", "facilitate" | Lowers perceived intelligence of the writer (Oppenheimer) |
| Nominalisation and passive | "An optimisation was performed" | Hides the actor and the action; Orwell, AR 25-50 |
| Stock phrases | "It's worth noting", "delve", "in today's landscape" | Orwell's stale imagery; signals filler, which readers learn to skip |

**Visuals**

| Anti-pattern | Looks like | Why it fails |
| --- | --- | --- |
| Shape told as prose | A process with branches described in paragraphs | Forces sequential search that a diagram would make spatial (Larkin & Simon) |
| Picture plus re-description | A diagram followed by text narrating every box | Redundancy effect (Sweller; Mayer) |
| Decoration | Icons, gradients, unrelated images | Coherence principle: extraneous material hurts learning (Mayer) |
| Separated labels | A legend far from what it explains | Split attention; violates spatial contiguity (Mayer) |
| Wrong encoding | Pie or bubble chart to compare values | Angle and area are judged less accurately than position (Cleveland & McGill) |
| Topic titles on charts | "Revenue by quarter" | The reader has to find the finding; a title like "Revenue fell 12% in Q3" gives it |

**Trust**

| Anti-pattern | Looks like | Why it fails |
| --- | --- | --- |
| Fluency without accuracy | A polished, confident answer that is wrong | Easy text is judged truer (Reber & Schwarz); clarity amplifies errors |
| Story without the claim | A compelling example with the conclusion left implicit | Transportation reduces scrutiny (Green & Brock); state the claim plainly |
| Length as authority | A long answer that implies thoroughness | Low-ability readers fall back on peripheral cues like length (Petty & Cacioppo); LLM training rewards length (Saito et al.) |

## References

Primary works, grouped by discipline. Links go to the pages used for this document; some are summaries of the primary source.

**Cognitive psychology**

- Sweller, Ayres, Kalyuga & Chandler (2003). [The expertise reversal effect](https://ro.uow.edu.au/articles/journal_contribution/The_expertise_reversal_effect/27724950/1). *Educational Psychologist* 38(1).
- Cognitive load theory overview: [LITFL](https://litfl.com/cognitive-load-theory/); Sweller on redundancy: [Teacher Magazine](https://www.teachermagazine.com.au/articles/cognitive-load-theory-teaching-strategies)
- Cowan (2001). [The magical number 4 in short-term memory](https://www.cambridge.org/core/journals/behavioral-and-brain-sciences/article/magical-number-4-in-shortterm-memory-a-reconsideration-of-mental-storage-capacity/44023F1147D4A1D44BDC0AD226838496). *Behavioral and Brain Sciences* 24(1).
- Bransford & Johnson (1972). [Contextual prerequisites for understanding](https://paperguide.ai/papers/06070657-76e0-4355-b53c-5dfe9979bf2f/). *JVLVB*.
- Camerer, Loewenstein & Weber (1989); Newton (1990): [curse of knowledge summary](https://tactics.convertize.com/definitions/curse-of-knowledge)

**Psycholinguistics and discourse**

- Kintsch & van Dijk (1978); Kintsch (1998): [model summary](https://aura-lab.siue.edu/theories/model-of-text-comprehension/)
- Haviland & Clark (1974); Clark & Haviland (1977): [given-new contract](https://d.lib.msu.edu/etd/41917/FULL_TEXT/view)
- Gopen & Swan (1990). [The science of scientific writing](https://www.win.tue.nl/~wstomv/quotes/science-of-scientific-writing.html). *American Scientist* 78.
- McNamara, Kintsch et al. (1996): [cohesion and prior knowledge](https://www.frontiersin.org/journals/education/articles/10.3389/feduc.2020.00026/epub)

**Structure and reading behaviour**

- US Army AR 25-50 (BLUF): [overview](https://legalclarity.org/bottom-line-up-front-bluf-what-it-is-and-how-to-use-it/), [Wikipedia](<https://en.wikipedia.org/wiki/BLUF_(communication)>), [Strom](https://matthewstrom.com/writing/bluf)
- Minto (1985). *The Pyramid Principle*: [summary](https://www.supernormal.com/blog/mckinsey-presentation-playbook)
- Nielsen Norman Group: [scanning and the F-pattern](https://sites.krieger.jhu.edu/using-your-site/web-writing/)
- Lorch (1989). [Text-signaling devices](https://link.springer.com/doi/10.1007/BF01320135); Lorch & Lorch (1996). [Organizational signals and recall](https://scholars.uky.edu/es/publications/effects-of-organizational-signals-on-free-recall-of-expository-te/)

**Visualization and multimedia**

- Larkin & Simon (1987). [Why a diagram is (sometimes) worth ten thousand words](https://www.goodreads.com/author_blog_posts/20533703-diagrams-versus-words?tab=book). *Cognitive Science* 11.
- Paivio, dual coding: [summary](https://loterre.istex.fr/P66/en/page/-R0V3S7S8-W); aphantasia study: [UChicago](https://knowledge.uchicago.edu/record/15350)
- Mayer (2001). *Multimedia Learning*: [principles](https://twut.nd.edu:443/PDF/Principles-MultimediaLearning.pdf)
- Cleveland & McGill (1984). Graphical perception: [FlowingData](https://flowingdata.com/2010/03/20/graphical-perception-learn-the-fundamentals-first)
- Tufte, data-ink: [lecture notes](https://teaching.vda.univie.ac.at/vis/23s/LectureNotes/02_DesignPrinciples.pdf); Borkin et al. (2013): [What makes a visualization memorable?](https://vcg.seas.harvard.edu/publications/20130101-what-makes-a-visualization-memorable); Bateman et al. (2010): [Useful junk?](https://vis.csail.mit.edu/classes/6.859/readings/pdfs/Bateman-UsefulJunk.pdf)

**Rhetoric, persuasion and political communication**

- Petty & Cacioppo (1986), Elaboration Likelihood Model: [chapter](https://www.springermedicine.com/chapter/10.1007/978-1-4612-4964-1_7), [overview](https://www.simplypsychology.org/elaboration-likelihood-model.html)
- Entman (1993). Framing: [selection and salience](https://people.willamette.edu/~ccollins/framing/allenm/selectionandsalience.htm)
- Heath & Heath (2007). *Made to Stick*: [summary](https://oa.mo.gov/leadership-library/15501), [review](https://csmonitor.com/2007/0123/p15s02-bogn.html)
- Green & Brock (2000). Narrative transportation: [chapter](https://link.springer.com/chapter/10.1007/978-3-031-63284-6_3)
- Gentner, structure-mapping: [summary](https://arxiv.org/pdf/2001.06668); Fyfe et al. (2014). [Concreteness fading](https://pc.cogs.indiana.edu/?p=885)

**Philosophy and plain language**

- Grice (1975). Logic and conversation: [maxims](https://www.futilitycloset.com/2019/04/08/grices-maxims/)
- Orwell (1946). Politics and the English language: [six rules](https://sites.duke.edu/scientificwriting/orwells-6-rules/)
- Schopenhauer (1851). On authorship and style: [The Marginalian](https://www.brainpickings.org/2014/03/20/schopenhauer-on-style/), [Wist](https://wist.info/topic/logorrhea/)
- US Plain Writing Act (2010): [Federal plain language guidelines](https://plainlanguage.gov/guidelines/)
- Oppenheimer (2006). Consequences of erudite vernacular: [Daily Princetonian](https://www.dailyprincetonian.com/article/2006/10/on-erudite-vernacular-i-e-big-words)
- Reber & Schwarz (1999); Schwarz on fluency: [Daedalus](https://www.amacad.org/publication/daedalus/judgments-truth-beauty)

**LLM-specific**

- Saito et al. (2023). [Verbosity bias in preference labeling by LLMs](https://arxiv.org/abs/2310.10076v1).
