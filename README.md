# Ribbon Medal — User Manual

Personnel decorations, ribbon rack display, and manufacturing for
ribbons, medals, and racks.

---

## 1. Core Concepts

| Term | Meaning |
|---|---|
| **Decoration** | A type of award (e.g. "BGB Medal"). Can be flagged **Is Ribbon**, **Is Medal**, or both. Each flag auto-manages its own sellable product (with Small/Large size variants). |
| **PRB** ("PRB of Decorations") | The actual award *rule* a person can earn: links a Ribbon decoration and/or a Medal decoration, a Force, a Rules Category, and (for Seniority/Batch rules) the qualifying service age or start date. This is what gets awarded to a person. |
| **Attachment** | A small device (numeral, star, club) worn on top of a ribbon to mark a repeat award. Auto-manages its own sellable product the same way a Decoration does. |
| **Acquisition Ledger** | The read-only, always-current list of everything a person has actually earned, combined from four sources (below). |
| **Ribbon Rack** | The visual strip of ribbon cells shown on a person's Decorations tab, built live from the Acquisition Ledger. |
| **Set Template** | Defines what a manufactured set (e.g. a full rack) is made of, as category-level rules rather than one fixed recipe. |
| **Rack Line** | An assembled *row* of ribbons (several ribbons mounted side by side). The intermediate stock unit between raw ribbon material and a full rack. |
| **Rack Product** | A specific, locked combination of Lines — i.e. one particular rack design, as its own stock-tracked product. |

---

## 2. Personnel

**Personnel → Personnel** holds each person's record: name, rank, force,
service dates, and (on the **Decorations** tab) their ribbon rack.

The **Service Information** group tracks service confirmation date,
computed service age, retirement status. **Personal & Contact** holds
name-plate spellings, birth date/age, email and phone.

### 2.1 Front desk: "Order Ribbon Rack"

**Personnel → Order Ribbon Rack** is the fast path for someone walking
up to the counter:

1. **Simple mode (default):** one search box, checked against name, ID
   number, phone, mobile, email, rank, and unit all at once — matching
   results appear live below. Toggle **Deep Search** on to instead get
   the full per-field breakdown (Name/ID/Phone/Mobile/Email/Rank/Unit),
   each filterable independently and OR-combined across whichever ones
   are actually filled in — useful when a simple search returns too
   many matches. You can also type straight into **Selected Person**
   itself; it searches the same fields, not just name.
2. Found them? Set **Selected Person**, then **Confirm & Create Sale
   Order**. Not found? **No Match - Create New Person** opens a blank
   Personnel form; save it, then come back here (or use the
   Decorations tab's own buttons directly).
3. Confirming creates a **Sale Order** for that person with one
   "Ribbon Rack" line, priced at their current **Estimated Price**
   (§5). Review/adjust it like any normal sale order.
4. **Confirming that Sale Order** (Odoo's own Confirm button) is what
   actually triggers everything — it runs the exact same stock-aware
   cascade as the **Issue Ribbon Rack** button (§6.3): reuse of ready
   Rack/Line stock where possible, manufacture-and-reserve otherwise.
   The resulting **Rack Unit** is linked back onto the Sale Order (a
   smart button on the order form jumps straight to it), and an
   "Awaiting Delivery" button appears there too until it's actually
   handed over — see §6.4 for closing that out.

So placing an order and fulfilling it are deliberately two separate
confirmations — the first locks in price and paperwork, the second is
what actually moves stock/starts manufacturing.

---

## 3. Decorations & PRB

**Decorations → Decorations** is the master catalog. Each decoration
has:

- **Is Ribbon** / **Is Medal** checkboxes — checking either auto-creates
  a sellable product for it (with S/L size variants), unchecking
  archives that product. Re-checking reactivates the *same* product
  rather than creating a duplicate.
- **Ribbon Image** / **Medal Image** — uploading here writes straight
  through to the underlying product's own image (they're the same
  picture, just editable from either place).
- **Attachment** — this decoration's *default* device, used as a
  fallback wherever a specific acquisition doesn't record its own.

**Decorations → PRB of Decorations** defines the actual award rules:
links a Ribbon and/or Medal decoration, a Force, a Rules Category
(Personal/Missions/Seniority/Batch), the display **Sequence** (lower
number = higher precedence — closer to the bottom-right of the rack),
and — for Seniority/Batch rules — the qualifying service age or a
starting date. The **Medal** and **Ribbon** fields are pre-filtered to
only show decorations actually flagged for that type.

---

## 4. The Acquisition Ledger

**Personnel → [a person] → Award / Service / Seniority / Customised
tabs** show a read-only, always-current combination of four sources:

1. **Award tab** (Personal Awards) — individually entered per person.
2. **Service tab** — missions/postings, individually entered.
3. **Seniority tab** — automatic: any PRB rule whose required service
   age the person has now reached, for their own force.
4. **Customised tab** — an editable *snapshot* you can take of the
   above three (via **Copy from Ledger**), for cases where you need to
   manually adjust or override what the live ledger would otherwise
   show.

Each row can optionally carry an **Attachment** (the specific device
received at *that* acquisition) — if left blank, it falls back to the
decoration's own default attachment. Exclusions (Decorations →
Excluded Awards) remove a specific decoration from a specific person's
ledger regardless of which of the four sources it would otherwise come
from.

---

## 5. The Ribbon Rack

The **Decorations** tab shows the person's ribbon rack: a grid built
live from the ledger, sorted by descending PRB **Sequence** (highest
precedence bottom-right, matching real ribbon-rack convention). An
incomplete top row is centered rather than padded with blanks.

Each cell shows the ribbon's own product image (falling back to plain
text if no image has been uploaded yet), with the attachment/device
image (if any) overlaid directly on top of it — the device image
should have a transparent background so the ribbon shows through
around the device graphic.

**Estimated Price**, shown next to the rack, sums each acquired
ribbon's product list price plus each acquisition's attachment device
list price.

---

## 6. Manufacturing

### 6.1 Set Templates (Configuration of what a rack is made of)

**Manufacturing → Set Templates** defines, as a set of rules rather
than one fixed recipe, what a set (e.g. a Ribbon Rack) requires:

- **Category** — which material category the rule needs (Ribbon, Gum,
  Backing, Fastener, Packaging, Attachment — manage the list itself
  under Configuration → Component Categories).
- **Scope** — **Per Cell** (once per acquired ribbon), **Per Rack**
  (once for the whole rack, regardless of cell count), or **Per
  Attachment** (once per cell, but only for cells that actually have
  one).
- **Quantity** / **Unit of Measure**.
- **User Picks Product** — unchecked means always use the rule's fixed
  **Default Product** (e.g. a standard safety pin). Checked means the
  actual product varies:
  - For the **RIBBON** category, it's resolved automatically — the
    cell's own award ribbon, Size L variant, always.
  - For the **ATTACHMENT** category, it's resolved automatically from
    that acquisition's own attachment.
  - For anything else (e.g. **BACKING** — Rexine vs Velcro), there's no
    existing field to auto-resolve from, so it needs an explicit
    per-cell choice — see 6.2.

### 6.2 Set Orders (manual, direct build)

**Manufacturing → Ribbon Rack Set Orders**, or the **Build Fresh
(Manual)** button on a person's Decorations tab: always builds a
brand-new generic Ribbon Rack from raw materials for that person,
ignoring any existing Rack/Line stock. Useful for a guaranteed
from-scratch build, or when you want direct control over the BOM.

Workflow: pick a **Set Template**, click **Prepare Cell Selections**
(stubs out a row for every cell/category combination that needs an
explicit pick, e.g. Backing), fill in the **Per-Cell Component
Selections** tab, then **Generate Manufacturing Order**. If any
required selection is still blank, generation stops with a clear list
of exactly what's missing rather than producing a wrong BOM silently.

### 6.3 Issue Ribbon Rack (stock-aware, recommended)

The **Issue Ribbon Rack** button on a person's Decorations tab runs
the full stock-aware cascade instead:

1. **Exact match in Rack stock** — if a Rack Product already exists for
   this *exact* combination of rows, and has an unreserved unit, that
   unit is handed straight over. Nothing else happens.
2. Otherwise, **each row (Line) is resolved independently**:
   - Exact match in Line stock → use it.
   - No exact match, but a longer in-stock Line *contains* what's
     needed as a contiguous run (trimmed from the left end, right end,
     or both — never the middle) → use it. The source unit is fully
     consumed; the trimmed-off ribbons are scrap. Among several
     possible trims, least waste wins, then highest usage count, then
     most recently used.
   - No stock at all → a brand-new Line is created and manufactured
     from raw materials.
3. The rows are then assembled/manufactured into a Rack unit —
   **reserved for this person** until delivered. If their order is
   later cancelled, un-reserve the unit manually (Rack Product → Stock
   Units tab → clear "Reserved For") to release it back to general
   stock.

A Rack Product's identity (its exact sequence of rows) is **locked
permanently** the moment it's first created — later changes to any
PRB's Sequence never reshuffle or invalidate a Rack Product that
already exists in the catalog.

### 6.4 Pending Deliveries — closing out a manufactured reservation

When a rack has to be manufactured (rather than pulled from ready
stock), the resulting unit is **reserved** for that person but not yet
marked delivered — manufacturing takes real time, and the rack isn't
physically in anyone's hands the moment the order is placed.

**Manufacturing → Pending Deliveries** lists every such reserved,
not-yet-delivered unit across all Rack Products in one place, each
with its linked Manufacturing Order and status. Once the physical rack
is actually handed over, click **Mark as Delivered** right there. If a
person's order is cancelled before delivery, click **Release
Reservation** instead — the unit drops its person-tag and rejoins
general stock automatically, available to the next matching request.

Browse the resulting catalogs any time under **Manufacturing → Rack
Lines** / **Rack Products** — each shows its stock count, use count,
and last-used date.

> **Note on timing:** a manufactured unit is marked "in stock" as soon
> as its Manufacturing Order is *confirmed*, not when it's actually
> completed on the shop floor. Check the linked MO's own status (shown
> as **MO Status** on the stock unit) if that distinction matters for
> your workflow.

> **Note on Line BOMs:** a Line's BOM only auto-resolves the RIBBON
> category and any fixed (non-user-selected) category. A user-selected
> category other than RIBBON (e.g. BACKING) has no one to prompt
> mid-cascade, so it's skipped and the Line is flagged for manual BOM
> review (shown as a warning banner on the Line's form).

---

## 7. Configuration Reference

Under **Configuration**:

- **Forces**, **Ranks**, **Unit Categories**, **Units**, **BCS
  Batches** — organisational reference data.
- **Attachments** — the device catalog (see §1/§3).
- **Component Categories** — the material categories used by Set
  Templates (§6.1).

---

## 8. Units of Measure

Newly-created products default to sensible units: **Ribbon** products
use **Meter** (ribbon material is bought/consumed by length), **Medal**
products use **Unit** (a discrete countable item). This only applies
the first time a product is created — it isn't retroactively changed
for a decoration whose ribbon/medal product already existed before
this behavior was added.

---

## 9. Known Limitations

- Reordering a set of ribbons into a different sequence than a
  stocked Line already has (e.g. matching `[A,C,B,D]` against a Line
  stocked as `[A,B,C,D]`) is not supported — only true contiguous
  substrings match.
- Rack stock reservation is tracked at the Rack level only; Lines are
  always general-purpose stock, never locked to a person.
- This module tracks manufacturing *intent* and stock *allocation*, not
  live shop-floor execution — always cross-check the linked MO's own
  status for real completion timing.
