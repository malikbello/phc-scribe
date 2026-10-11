# Error taxonomy (eval plan §7)

**What:** the kinds of mistakes base N-ATLaS and the shipped model make on the frozen tests (G, S5, H, R: 1,090 items).

**When and how:**
- read **after** the verdicts were final; it changes no model, prompt or threshold;
- every error gets a category from fixed definitions (`scripts/error_taxonomy.py`);
- a seeded random sample of **50 items with an error per system** is categorised, as the plan says;
- numbers are in `results/errors/taxonomy.20261011.json`, and the examples are from our constructed and public sets.

## 1. How many items have an error
| System | Items with any error | of 1,090 |
|---|---|---|
| Base N-ATLaS few-shot (comparator) | 647 | 59% |
| **Fine-tuned Q4 (shipped)** | **545** | **50%** |

An "error" is anything that differs from gold: a missed or extra finding of any kind, or a wrong assertion, measurement or schema.

## 2. All errors by category
| Category | Base | Fine-tuned Q4 | Change |
|---|---|---|---|
| **False danger sign: not said at all** | 261 | **157** | −40% |
| False danger sign: a past pregnancy read as current | 58 | **17** | −71% |
| False danger sign: a milder symptom escalated (headache → severe headache) | 30 | 31 | same |
| False danger sign: gold says she denied it | 14 | 18 | +4 |
| **Missed danger sign: not recorded** | 53 | **36** | −32% |
| Missed danger sign: recorded as a milder symptom | 33 | **19** | −42% |
| Missed danger sign: marked absent | 0 | 2 | +2 |
| Other finding added (not a danger sign) | 645 | **445** | −31% |
| Other finding missed | 162 | **129** | −20% |
| Other finding with the wrong assertion | 23 | **16** | −30% |
| Measurement (BP or gestational age) wrong or missing | 12 | **4** | −67% |
| Invalid output (schema) | 17 | 35 | **+18** |

**Sample of 50 items with an error, by primary category:**

| Primary category | Base | Fine-tuned Q4 |
|---|---|---|
| False danger sign (any) | 23 | 20 |
| Missed danger sign (any) | 1 | 5 |
| Other finding (any) | 25 | 22 |
| Invalid output | 1 | 3 |

## 3. Which danger signs
| | Base | Fine-tuned Q4 |
|---|---|---|
| **Most missed** | severe headache 19, unconscious 16, severe vomiting 12, severe abdominal pain 11 | **severe abdominal pain 18**, convulsions 9, unconscious 7, severe headache 6 |
| **Most often raised falsely** | looks very ill 91, swelling of face/hands 62, fever 43, severe pallor 41 | **vaginal bleeding 70**, leaking fluid 30, swelling of face/hands 23, severe headache 22 |

**Fine-tuning removed most of the base model's false alarms:**
- "looks very ill": from 91 to 11 or fewer;
- swelling: from 62 to 23;
- fever: from 43 to 13.

It introduced one pattern of its own, bleeding (section 4.1).

## 4. The failure modes, in words
1. **A danger sign attached to a quote that has nothing to do with it.** This is the shipped model's main false alarm.
   - 48 of its 70 false "vaginal bleeding" findings are in the English clinical notes (G), marked *possible*, with quotes such as "TCA 4/52." (the return date), "nil" or "everything taken".
   - Grounding checks only that the quote exists in the transcript, so these pass, and the bleeding rule fires.
   - **Next:** a concept–quote check that flags a danger finding whose quote has none of the concept's words in any language ("bleed", "blood", "spotting", "ẹ̀jẹ̀", "blood dey comot"). It flags and never drops, like the polarity check (ADR-0030), and is developed on dev data only.
2. **General advice read as her symptom.**
   - *"If pregnant woman leg swell, make she raise the leg up"* became "swelling of face/hands: present".
   - Health talk contains advice and other people's stories, so the speaker-role rule (ADR-0024 F5) needs training examples of advice sentences.
3. **Strong Pidgin and Yorùbá pain talk under-graded.**
   - *"My belle dey pain me die, I no fit stand up"* became "low back pain", not severe abdominal pain. That is the most-missed sign (18).
   - **Next:** the rare-sign phrase bank (ADR-0028) for the severity markers ("die", "well well", "I no fit stand up", "gan").
4. **Extra "possible" findings from routine words.** "T 36.5" became heartburn (*possible*); "your urine is too yellowish" became abnormal discharge (*possible*).
   - These are harmless for the danger rules when the concept is not a danger sign, but they are noise for the nurse.
   - **Next:** more empty and plain records in training, and a review rule for *possible* findings without a symptom word.
5. **Invalid outputs rose from 17 to 35 (3.2%).** The commonest cause is a lab test named without a result, which the grammar cannot forbid.
   - Serving now repairs these instead of rejecting them (ADR-0029): 30 of 33 recovered on H.
6. **Past pregnancies:** the base model read "fit catch me for my last belle" as current 58 times; fine-tuning cut this to 17.

## 5. What this means
- **Fine-tuning reduced every kind of error except two:** invalid outputs, now repaired in serving, and the unrelated-quote bleeding alarm, which has a clear, testable fix.
- **The nurse's review stays essential:** about half of the items have some difference from gold, mostly extra or missing *non*-danger findings.
- **The three fixes above** (concept–quote check, advice sentences, Pidgin and Yorùbá severity) are the next training and serving work. Each is chosen on dev data and confirmed on a fresh pre-registered test.
