# Insurance & Connect — build plan

**Status:** researched, plan written, build starting · **Date:** 2026-08-07

Both are `to: null` placeholders in the navigation today. Insurance has no code at
all; Connect has `Comment` and `Notification` in `apps/workspace` and nothing else.

## Insurance

### What the market does

Pharmacy claim systems converge on the same spine, whoever builds them: real-time
**eligibility** before dispensing, **split billing** between patient and payer,
**adjudication** with reason codes, **reversal** when a script is not collected,
and **coordination of benefits** when a member holds two policies. Reconciliation
is a separate discipline again — remittance advice matched against what was
claimed, with the shortfall aged and chased.

### What Rwanda specifically requires

* **CBHI / Mutuelle de Santé** — run by RSSB since 2015, covering the large
  majority of the population. Co-payment is **10%**, capped, plus a flat facility
  fee (RWF 200 at health-centre level). **Ubudehe category 1 members are fully
  subsidised — 0%.** A scheme model with a single co-pay percentage cannot express
  that; the rate depends on the member, not only the scheme.
* **RSSB medical (RAMA)** and private insurers (MMI, Radiant, Britam, Prime, UAP)
  sit alongside it at different rates.
* **The 2026 reform matters.** A Prime Minister's order of 24 February moved CBHI
  from fee-for-service reimbursement to **upfront capitation** for primary
  healthcare facilities, piloted in Eastern Province in January 2026 and rolling
  out nationally. A build that assumes fee-for-service only would be obsolete on
  arrival; a build that assumes capitation only cannot serve private pharmacies,
  which still bill per script. **Both are modelled.**

### Design

| Model | Why |
|---|---|
| `InsuranceScheme` | Payer + settlement model (fee-for-service or capitation), default co-pay, claim window, reimbursement period. |
| `MemberPolicy` | The card presented at the counter: member number, scheme, validity, principal/dependant, and the **member-level co-pay override** that Ubudehe category 1 requires. |
| `SchemeFormulary` | What a scheme covers, at what co-pay, and whether it needs prior authorisation. Absence means not covered — silence must not mean "pay it". |
| `Claim` / `ClaimLine` | Built from insured sales. Adjudication with reason codes; reversal for uncollected scripts. |
| `RemittanceAdvice` / `RemittanceLine` | What the insurer actually paid, matched against what was claimed, so short-pays surface instead of quietly ageing. |

### Rules the engine must hold

1. **Eligibility is checked before dispensing, not after.** An expired card found
   at claim time is a debt the pharmacy already incurred.
2. **The patient's share and the insurer's share must sum to the sale.** Any
   rounding lands on the patient portion, once, and never leaves a gap.
3. **An uncovered product is the patient's to pay in full** — never silently
   claimed against a scheme that does not list it.
4. **A claim cannot exceed what was dispensed**, and reversing one restores the
   patient's liability rather than deleting the record.
5. **Insurer receivables are real AR** and post to the ledger like any other.

## Connect

Chat and email, in the shape people already know from Google Workspace and
Microsoft 365 — that is the reference the user named, and it is the right one:
nobody needs to be taught an inbox.

### Chat

Spaces (Teams channels / Google Chat Spaces) and direct messages, both threaded.
Google added inline threading to DMs and group chats in November 2025, so
threading everywhere — not only in spaces — is now the expected behaviour rather
than a Slack-ism.

| Model | Why |
|---|---|
| `Space` | A named room: branch, department, or ad-hoc. Direct messages are a space with two members and no name. |
| `SpaceMember` | Membership, role, last-read marker (unread counts are per member, not per message). |
| `Message` | Body, author, optional `parent` for a thread reply, edited/deleted markers. |
| `MessageReaction` | Emoji, one per member per message. |

### Email

Internal mail — an inbox people can be given without provisioning mailboxes.

| Model | Why |
|---|---|
| `MailThread` | Subject and participants; replies group under it, as Gmail does. |
| `MailMessage` | Body, sender, sent-at. |
| `MailRecipient` | Per-recipient state: to/cc/bcc, read, starred, archived, trashed. Read status belongs to the recipient, not the message. |
| `MailLabel` | User-owned labels/folders. |

### Rules

1. **Unread is per person.** A message read by one recipient is unread for
   everyone else — so read state lives on the recipient row.
2. **A space you are not a member of is invisible**, including in search.
3. **Deleting is per recipient** unless the sender retracts, which marks rather
   than erases.

## Method

As with Finance, Retail, Distribution and Inventory: logic before UI, tests per
phase, then a live HTTP walkthrough — which has caught bugs in every phase of
this project that unit tests did not.
