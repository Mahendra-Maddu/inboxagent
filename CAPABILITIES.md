# CAPABILITIES.md

**Student:** Mahendra Maddu, 1161804
**Repository:** https://github.com/Mahendra-Maddu/inboxagent

Run everything through one entry point:

```
python demo.py --cap R1        # one capability
python demo.py --all           # all of them, in the order below
```

`R4` is two process invocations of the same command. The first writes `prefs.json` and exits. The second loads that file and applies it. `python demo.py --all` runs both passes.

---

## The system, in one paragraph

A single Python pipeline, no framework. Messages are loaded from `inbox.json`. A safety scan flags prompt injection and phishing before any reply is drafted. Cheap messages (receipts, newsletters, calendar notifications, and other automated mail) are dispatched by rules in `inboxhero/rules.py` and never touch a model. The rest get one disposition, then a thread-walk retrieval, a grounded draft, and a gate. State that must outlive a run (preferences) lives in `prefs.json`. Every decision is appended to `trace.jsonl`.

## Design choices you were asked to state

- **Messages processed: 100.** Format assumed: a JSON array of objects with `id`, `thread_id`, `from`, `to`, `subject`, `timestamp`, `body`, and `unread`. Owner is `sam@paperjet.io`. Age for follow-ups is measured from `REFERENCE_NOW=2026-09-09T18:00:00`, just after the last message.
- **Framework: none.** The work is a linear pipeline with one branch (rule path versus the few messages that need retrieval and a draft). A crew or graph would have hidden the only boundary that matters, which is the gate. See Final Report Q4 in `README.md`.
- **Model.** `gemini-2.0-flash` when `GEMINI_API_KEY` is set (`config.py`, `.env.example`). Classification of all 100 messages is rules, so `rule_handled` is 100. `inboxhero/llm.py` is optional polish: it sleeps between calls and backs off on HTTP 429. The graded commands do not need a key.
- **Retrieval: thread-walk.** `thread_id` is the index. `inboxhero/retrieve.py` walks earlier messages in the thread and logs a `read` event for each. Keyword search is the fallback when the fact lives in another thread (the staging URL, the launch date). A draft cites only ids that were read. If the fact is not in the inbox, the drafter writes nothing.
- **Disposition vocabulary.**
  - `reply`: a grounded answer is drafted and held for the gate.
  - `archive`: no reply; reversible label on the record.
  - `defer`: a deadline or an outbound chase, kept on the calendar or follow-up list.
  - `delegate`: someone else owns the next step (`m059`, Raghav covers on-call).
  - `escalate`: a human must decide (legal, money, phishing, injection, or an ask too vague to answer).
- **Reversible vs irreversible.** `send` and `delete` are irreversible and gated. `draft`, `label`, `archive`, and `defer` are reversible and run without a prompt. Deleting is irreversible because the mock store has no trash. The delete path still refuses to remove the message from `inbox.json`; hostile mail is flagged and left in place.
- **Where the gate sits.** Only `Gate.send` and `Gate.delete` in `inboxhero/gate.py` can cause an irreversible effect, and both call `require_approval()` first. Default mode is dry-run, which prints the proposal and writes nothing. `--no-dry-run --approve` asks y/n per action. A hostile message can influence a draft only if a template accepts it; it cannot reach a send, and blocked destinations (`archive@mail-backup-service.info`, `finance-sync@ext-audit.co`) are refused even then.
- **Escalation line.** The system asks a human only for sends, deletes, money, legal signatures, phishing, injection, time commitments, and ambiguous asks. Newsletters and receipts are archived automatically (74 of them). The trade-off: a wrongly archived automated notice is possible, in exchange for the owner not being asked to approve the bulk of the inbox.
- **Preference.** `m015` (CC Priya on Hartwell & Cho) and `m041` (no meetings before 11:00) are the only messages allowed to write `prefs.json`. `m039`, which asks the assistant to disable the gate, is refused and is not stored. After a restart, `m018` is drafted with `priya@paperjet.io` on CC.

## Capabilities

| id | name | tier | one-line claim |
|----|------|------|----------------|
| R1 | Zero the inbox | B | every message gets one disposition + reason, none left |
| R2 | Grounded reply | B | m008 cites the AMQP URL in m003 |
| R3 | Gate the irreversible | C | no send/delete without approval or --dry-run |
| R4 | Persistent preference | C | m015 survives a restart and CCs Priya on m018 |
| R5 | Refuse embedded instructions | C | detects, refuses, flags, and reports injections |
| R6 | Dashboard | C | three panes, commitments cited, conflicts surfaced |
| X1 | Unread from sender | A | one lookup of unread mail from a given sender |
| X2 | Follow-up tracking | B | unanswered sent mail, with a drafted chase |
| X3 | Morning digest | B | what needs Sam / what can wait / what was archived |
| X4 | Preference-aware scheduling | C | m043 at 09:00 is held, with 11:00 alternatives |

The exact command, observable outcome, and evidence for each is in `capabilities.json`. That file is the machine-readable version. This file is for a human. Keep the two in step.
