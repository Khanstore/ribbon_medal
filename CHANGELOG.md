# Changelog

## 18.0.2.7.1 — 2026-10-16
- Fixed personnel search-view registry error: removed filters/grouping on `is_retired`, a computed non-stored field that Odoo cannot search/group.
- Kept personnel lookup by name and English name, ID number, rank, force, workplace and phone.
- Added dedicated user and developer manuals under `docs/`.
- Updated manifest author and summary.
- No business-model or database-schema change in this hotfix.

## 18.0.2.7.2
- Added per-award deposited quantity entry to the rack-person wizard.
- Deducted only the deposited count from estimated medal-rack pricing instead of excluding every matching acquisition.
- Persisted deposit quantities on sale order lines and carried them to dedicated manufacturing adjustment without inventory receipts or stock movements.


## 18.0.2.7.3
- Fix required Medal / Award validation when editing deposited quantities: force-save the preselected readonly award field in the editable wizard list.

## 18.0.2.7.4
- Improve rack configuration wizard image: use existing order-line product image, person-specific variant image, or standard rack product image as fallback.
- Document reopening the wizard from an existing rack line and restoring saved deposit quantities.


## 18.0.2.7.5
- Repair missing S/L variant values on existing decoration product templates before resolving a Medal Rack BOM component; show an actionable error if a variant still cannot be materialized.
- Make customer-deposited medal manufacturing quantity-aware: reduce raw-material moves by the deposited count instead of removing the entire product move for any positive deposit. Shared BOMs remain untouched.
- Pass the saved per-award quantities from the sale order line into manufacturing and improve the line configuration button affordance.
- Updated the end-user and developer manuals with the new behavior and staging regression checks.
- Validation: offline static checks only; live Odoo registry and manufacturing regression checks remain required.


## 18.0.2.7.7 — rack-line pencil edit control
- Use a pencil-icon button on rack lines to reopen the custom person/deposit wizard.
- Keep the control conditional on `rack_type`; do not override the normal product configurator for ordinary products.
- Clarify that confirming an edit updates the existing line rather than creating a second line.
- Updated user and developer manuals.
- Validation: offline static checks only; live Odoo UI/registry behavior still requires staging verification.

## 18.0.2.7.8
- Hardened edit wizard defaults by reading the existing sale order line as the source of truth.
- Retained Odoo `soft_reload` after confirmation; the functional change is to load edit defaults from the persisted line.
- Updated user and developer manuals.
