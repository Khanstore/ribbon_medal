# Ribbon Medal — Developer Manual
Version: 18.0.2.7.7
Target: Odoo 18

## Purpose and scope
This module manages personnel award eligibility, award acquisition history, visual ribbon/medal racks, sale quotations, stock-aware rack fulfillment, and manufacturing. Personnel data is integrated into `res.partner`, not a separate personnel table.

## Installation and upgrade
1. Back up the PostgreSQL database and filestore.
2. Place `ribbon_medal` in an enabled custom addons path.
3. Restart Odoo and update the Apps list.
4. Upgrade with `-u ribbon_medal` against a staging database first.
5. Review server logs and complete the regression checklist below before production deployment.

## Dependencies
Manifest dependencies include `base`, `sale`, `stock`, `mail`, `website_sale`, `purchase`, `product`, and `mrp`. Backend JavaScript, XML templates and SCSS are declared under `web.assets_backend`.

## Main model areas
- `models/res_partner.py`: extends `res.partner` with personnel identity, force/rank/workplace, service dates, award ledgers and rack pricing/counts. `is_retired` is a computed non-stored field; do not use it in search domains or group-by contexts unless redesigned as a properly maintained stored field.
- `models/rm_decoration.py`, `models/attachments.py`, `models/prb.py`, `models/rm_prb.py`, `models/rm_rules_category.py`: award catalog and eligibility configuration.
- `models/rm_acquisition.py`, `models/rm_personal_award.py`, `models/posting_mision.py`, `models/rm_acquisition_custom.py`, `models/rm_excluded_award.py`: acquisition sources, ledger and overrides/exclusions.
- `models/rm_rack_line.py`, `models/rm_rack_product.py`, `models/rm_medal_part.py`, `models/rm_medal_rack.py`: rack/line/part products and stock units.
- `models/rm_set_template.py`, `models/rm_set_order.py`, `models/rm_set_order_line.py`, `models/mrp_production.py`: templates, component selections and manufacturing integration.
- `models/sale_order.py`, `models/stock_picking.py`: sales and delivery integration.
- `models/rm_person_search_wizard.py`, `models/rm_partner_to_person_wizard.py`, `models/rm_sale_line_person_wizard.py`: transient workflows.

## Views and navigation
- XML views live in `views/`; menu hierarchy is declared in `views/ribbon_medal_menus.xml`.
- Personnel search uses searchable fields such as name, `name_eng`, `id_number`, rank, force, workplace and phone. Computed non-stored fields must not be used as searchable domain/group-by fields.
- Keep existing XML IDs stable when changing views/actions.

## Security and data
- Access control is defined in `security/ir.model.access.csv` and `security/ribbon_medal_security.xml`.
- Data and initial catalogs are in `data/`. Migration scripts are under `migrations/`; preserve existing migration directories.
- Avoid direct SQL changes to business records unless a migration requires them with safe transaction/rollback handling.

## Engineering guidelines
- Use Odoo ORM and `@api` conventions; avoid raw SQL for normal CRUD.
- Validate required data on the server side and keep user-facing errors actionable.
- Keep stock quantities/reservations consistent with Odoo stock moves and manufacturing states.
- Cancellation/release behavior must be idempotent and must not release delivered or otherwise committed units.
- Batch searches/creates for large datasets; avoid per-record search loops.
- Use Odoo 18 `<list>` views, direct expression modifiers such as `invisible="..."`, and avoid deprecated `attrs`/`states`.
- Add tests for reservation, manufacturing and award eligibility edge cases.

## Regression checklist
- Module install and upgrade on a production-like Odoo 18 database copy.
- Personnel create/edit, ID uniqueness per force, search by name and English name.
- Award acquisition, exclusion, custom ledger and rack rendering.
- Rack order wizard, quotation creation and sale confirmation.
- Exact stock reuse, line reuse/trimming, component shortages, manufacturing status.
- Delivery, cancellation and reservation release; retry actions to check idempotency.
- Access rights for ordinary users versus managers.
- Asset compilation and browser console after hard refresh.

## Validation boundary
This release removes invalid search filters on computed non-stored `is_retired`. Syntax checks can run offline, but registry loading and workflow behavior must be verified in the target Odoo environment.


## Quantity-aware customer deposits (18.0.2.7.2)

- The transient `rm.sale.line.person.wizard.deposit` rows display one row per medal-eligible award with an acquired count and deposited count. The count is validated against the person's active customised or live medal ledger.
- `sale.order.line.deposited_award_quantities` stores a JSON map (`award_id` string to integer quantity) to preserve the quantity selection without a new stock or consignment model. `_rm_deposit_quantities()` parses it defensively.
- `res.partner._medal_rack_price()` deducts only N matching acquisition/custom-ledger rows per award. Legacy `excluded_award_ids` remains supported for existing internal callers.
- At order confirmation, any award with a positive deposit is passed to the dedicated rack MO adjustment. The current rack BOM requires one medal component per award row, so a positive quantity suppresses that award's one rack component; quantity does not generate stock moves for customer-owned medals.
- Regression tests should cover two same-award acquisitions with deposit 0/1/2, customised ledger duplicates, upper-bound validation, price changes, and MO raw material requirements. This release has offline syntax/XML checks only; runtime registry and production-flow tests must be run in staging.


## Release 18.0.2.7.3 — wizard readonly-field persistence

In `views/rm_sale_line_person_wizard_views.xml`, the readonly `award_id` in the editable One2many list uses `force_save="1"`. This is intentional: Odoo can omit readonly values when serializing edited virtual One2many rows, causing the required `rm.sale.line.person.wizard.deposit.award_id` field to be absent on create. Preserve this flag if the list is refactored. Regression-test by opening a Tunic/Meskit rack wizard, selecting a person with multiple acquired medals, changing one deposited quantity, confirming, and verifying the price adjustment and absence of stock moves for deposited units.


## Release 18.0.2.7.4 - wizard image and edit flow

`rm.sale.line.person.wizard._compute_rack_preview_image` now follows a fallback chain: existing sale line product image, resolved person-specific variant image, then the standard rack product template image from `_get_rack_kind_config()`. This prevents an empty preview when a generic rack product has an image but a person-specific variant does not. The existing `sale.order.line.action_open_person_wizard` passes `line_id`, `person_id`, `rack_type`, and `deposited_award_quantities` into the wizard context so the edit path can restore the configuration.

Regression checks: open an existing line and confirm person/deposit quantities are restored; check image fallback with an existing product image but no variant image; change deposit quantity and confirm price; verify no stock receipt is generated for customer-deposited medals.


## Release 18.0.2.7.5 — size-variant repair and exact deposit quantities

- `rm.product.sync.mixin._get_size_variant()` now checks the selected template's own `Size` attribute line and safely restores a missing S/L value before resolving its generated variant. It does not replace the product template or touch unrelated attributes. If Odoo cannot materialize a variant (for example, because the attribute is configured for dynamic variants), it raises an actionable error instead of proceeding with an incomplete BOM.
- Customer-deposited medal quantities now flow from the sale line to the rack manufacturing order as an award-ID-to-quantity mapping. The MO raw-material move is reduced by the requested quantity; it is deleted only when the remaining requirement reaches zero. The shared BOM is not modified, so other orders still consume the full medal quantity. Legacy internal callers passing a list of award IDs remain supported as full-exclusion requests.
- The sale-order line configuration control now uses a sliders icon and describes its full configuration purpose.

### Release validation boundary
Offline validation covers Python syntax, XML well-formedness, manifest data-file references, CSV headers, and archive contents. It does not prove that the module loads in a live Odoo registry or that manufacturing behaves correctly against your configured product catalogue. Staging checks must include a legacy decoration template missing Size L, two acquisitions for the same award with deposit quantities 0/1/2, confirmation, MO raw-material demand, and a non-deposit order proving the shared BOM is unchanged.


## Release 18.0.2.7.7 — scoped rack-line edit action

- `views/sale_order_views.xml` exposes `sale.order.line.action_open_person_wizard` as a pencil-icon object button only when `rack_type` is set. It does not replace the `product_id` field widget, so standard Odoo product configuration remains intact for non-rack lines.
- `models/sale_order.py:SaleOrderLine.action_open_person_wizard` passes the persisted `line_id`, person, rack type and JSON deposit snapshot to `rm.sale.line.person.wizard`.
- `models/rm_sale_line_person_wizard.py:action_confirm` updates the existing `sale.order.line` when `line_id` is supplied; it only creates a new line in the separate `order_id` path. `_apply_rack_person()` recalculates the price and rebuilds the line description from current saved deposits.
- Static validation for this package includes Python compilation, XML parsing, manifest/data-path validation, and ZIP integrity. These checks do not simulate an Odoo browser session or prove the configured database's product/BOM behavior. Stage-test: edit one existing rack line, verify no duplicate line is created, verify person/deposit values and price are restored/updated, then edit a normal product and verify its standard configurator still opens.

## Release 18.0.2.7.8 — rack-line edit reliability

- `rm.sale.line.person.wizard.default_get()` now treats the persisted `sale.order.line` as the authoritative source when `default_line_id` is supplied. It explicitly restores `line_id`, `person_id`, `rack_type`, and saved deposited-award JSON instead of relying solely on action context defaults.
- Deposit rows are rebuilt from saved quantities and clamped to the person's currently acquired count. Missing/deleted person records are handled safely.
- Wizard confirmation retains Odoo’s `soft_reload` client action after applying the configuration so the current view refreshes without a hard browser reload.
- The row pencil remains conditional on `rack_type`; the global product configurator is not replaced.


## Release 18.0.2.7.11 — deposited quantity validation per rack quantity

- The maximum customer-deposited quantity for each medal is now **acquired medals × Rack Qty**.
- The wizard's existing deposited values are restored against that multiplied maximum.
- Changing Rack Qty recalculates the displayed maximum immediately.
- The constraint rejects any deposited quantity below 0 or above the multiplied maximum; it does not silently reduce the user's entered quantity.
- Example: if a person has acquired 3 of an award and Rack Qty is 2, the allowed deposited quantity is 0–6.


## Release 18.0.2.7.10 — rack quantity and row editor UI

- The rack-row editor button is now positioned immediately before `product_uom_qty`, uses the `fa-user` icon, and has no visible `Edit` label.
- `rm.sale.line.person.wizard.rack_quantity` is an editable rack-unit quantity, defaulting to the existing Sale Order Line quantity when editing and to `1.0` for a new rack line.
- Deposited-medal quantities are explicitly per rack unit. The existing unit-price calculation therefore remains correct when a line contains multiple identical rack units.
- Confirming the wizard writes `rack_quantity` to `sale.order.line.product_uom_qty` for both new and existing rack lines.
- The wizard shows `Rack Qty` in the right-hand panel above the rack preview.

## Release 18.0.2.7.9 — Sale Order rack editor visibility fix

The rack-line edit button now uses the computed `is_rack_line` flag rather than requiring `rack_type` to already be populated. The flag recognises finished rack products as well as lines with a stored rack type. `action_open_person_wizard()` repairs a missing rack type before opening the existing editor. The Sale Order XML targets the Odoo 18 `<list>` structure explicitly and gives the pencil button a visible `Edit` label as a fallback while retaining the `fa-pencil` icon.
