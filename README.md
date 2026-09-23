# inboxHero

**Student:** Mahendra Maddu, 1161804
**Repository:** https://github.com/Mahendra-Maddu/inboxagent

Local agent that takes Sam's mock inbox (`inbox.json`, 100 messages) from unread to a disposition on every message. Sending means writing a file under `outbox/`. Nothing talks to a real mailbox.

```
pip install -r requirements.txt
copy .env.example .env
python demo.py --all
python demo.py --cap R2 --msg m008
```

Dry-run is the default. Irreversible sends prompt only with `python demo.py --cap R3 --no-dry-run --approve`.

## Architecture

```
inbox.json
   -> safety scan (injection / phishing)     inboxhero/safety.py
   -> rule router (one disposition each)     inboxhero/rules.py
   -> thread-walk retrieval                   inboxhero/retrieve.py
   -> grounded draft                          inboxhero/draft.py
   -> gate (dry-run or y/n)                   inboxhero/gate.py
   -> outbox/ only if approved
   -> dashboard.html                          inboxhero/dashboard.py
```

Preferences that must survive a process exit live in `prefs.json` (`inboxhero/memory.py`). Every step appends to `trace.jsonl`.

Email bodies enter the model, when a model is used, inside an `UNTRUSTED_EMAIL` fence. Model output cannot call `Gate.send` or `Gate.delete`. Those two functions are the only writers.

## Framework

None. See Final Report question 4. Optional model is Gemini (`GEMINI_API_KEY`, `GEMINI_MODEL`, default `gemini-2.0-flash`) loaded in `config.py`. The 100 dispositions are rules, so a full demo runs with no API key. `inboxhero/llm.py` sleeps between calls and retries HTTP 429.

## Disposition vocabulary

| Disposition | Meaning |
|-------------|---------|
| reply | Draft a grounded answer and hold it for the gate |
| archive | No reply; reversible |
| defer | Deadline or outbound chase; keep it, do not send yet |
| delegate | Someone else owns the next step (`m059`, Raghav covers on-call) |
| escalate | Human must decide: legal, money, phishing, injection, or too vague |

Every message gets exactly one. `python demo.py --cap R1` prints `undecided: 0` and `rule_handled: 100`.

## Reversible and irreversible

| Irreversible (gated) | Reversible (automatic) |
|----------------------|------------------------|
| send | draft |
| delete | label, archive, defer |

Delete is irreversible because this store has no trash. inboxHero still does not remove hostile messages from `inbox.json`; it flags them and leaves them.

The gate is dry-run by default (prints the proposal, `outbox/ writes: 0`) and per-action approval when `--no-dry-run --approve` is set. Both are implemented. The line: automatic archive for receipts and newsletters (74 messages); a human for sends, deletes, money, legal signatures, phishing, injection, time commitments, and ambiguous asks. The trade-off is that a mis-filed automated notice is possible, so the owner is not asked to approve the bulk of the inbox.

## Retrieval

Thread-walk on `thread_id`, then keyword search when the needed fact is in another message. `m008` is answered from `m003` and the draft records `cited: ['m003']`. A missing fact produces no draft.

## Standing preferences

Only `m015` and `m041` may be written to `prefs.json`. `m039` (disable the gate, auto-send investor mail) is refused. Run `python demo.py --cap R4` twice: the second process CCs `priya@paperjet.io` on the reply to `m018`.

## Final Report

### 1. What did you refuse to automate?

The system drafts a clarifying question for `m012` ("the thing") and then stops. It does not guess which standup item Priya meant, and it does not send that question. Sending is irreversible, and a wrong guess would commit Sam's time or his word. The same line covers `m018` (a SAFE signature), `m021` and `m023` (wires), and every other outbound reply: `Gate.send` will not write `outbox/` until a person approves that one action, or until dry-run has shown it and suppressed it. `m012` is the clearest case because even the content of the reply is something the system is not entitled to invent.

### 2. Where does untrusted text enter your system?

Untrusted text enters at load time, as the `subject` and `body` fields of `inbox.json`. From there it is data. `inboxhero/safety.py` wraps any body that would be shown to a model in an `UNTRUSTED_EMAIL` fence, and the preference writer ignores every message except the allowlist `m015` and `m041`. Tools that change the world are `Gate.send` and `Gate.delete`; nothing in a message body is a function call. An attacker who wants a send (the forward in `m024`, the RELEASE blast in `m017`, the silent forward in `m047`, or the gate bypass in `m039`) has to defeat that split: they must get the pipeline to treat body text as a tool invocation, and they must get past `require_approval`, which only a human at the terminal can do. A better prompt is not part of this boundary.

### 3. Who is accountable when it sends the wrong thing?

Sam, the mailbox owner, is answerable for anything that leaves in his name, because a send happens only after he answers y on that action (or because he chose to turn dry-run off). The system makes the failure traceable. `trace.jsonl` records the proposal (recipient, cited message ids, body preview), the human's answer, and whether a file was written. A bad reply to `m008` can be checked against the `read` event for `m003` and the `draft` event that cited it. A send that should never have existed, such as one aimed at `archive@mail-backup-service.info`, shows up as a `refusal` rather than an outbox file. The gate log is the record of who approved what.

### 4. Name your own machinery

`inboxhero/rules.py` is the router: one disposition, and a branch that keeps noise off the model. `inboxhero/caps.py` is the task list (`R1` through `X4`), each runnable alone. Retrieval (`retrieve.py`), drafting (`draft.py`), and the safety scan (`safety.py`) are the specialist steps a framework would call agents. There is no crew object; `demo.py` runs the tasks in order. The piece a framework would have handed over, and that this project builds itself, is the gate: a single choke point for send and delete, with a log of the proposal and the decision. Using CrewAI or ADK here would have hurt. Those libraries are built to let a model pick tools, and this inbox is full of text that tries to be that model. The useful property is that message text cannot reach a tool, which is easier to see in a short explicit pipeline than inside a framework's tool loop.
