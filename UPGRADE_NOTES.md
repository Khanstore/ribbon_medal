# Upgrade notes — 18.0.2.7.1

## Fix
Odoo rejected the personnel search view because `is_retired` is computed with `store=False`, making it unsearchable. The invalid filters and group-by option have been removed. Personnel search still supports name/English name, ID number, rank, force, workplace and phone.

## Upgrade
1. Back up the database and filestore.
2. Replace the module directory with this release.
3. Restart Odoo and upgrade `ribbon_medal` on a staging database first.
4. Confirm registry loads successfully and test personnel search and grouping.

No schema migration is included. If retirement filters are needed later, implement a correctly maintained stored status or a search method; simply storing a date-dependent Boolean is insufficient unless refreshed when dates roll over.


## 18.0.2.7.2
Upgrade the module normally after backing up database and filestore. Existing sale lines with the legacy `deposited_award_ids` relation are not migrated automatically into the new quantity map; review any open quotations that already have deposits and re-enter their deposit quantities in the person wizard. No inventory records are created by this feature.


## 18.0.2.7.3
No schema migration is intended. Upgrade the module so the wizard view includes `force_save="1"` on the Medal / Award field. Test the deposit quantity workflow in a staging database before production use.

## Upgrade to 18.0.2.7.4
This is a code-only wizard display improvement. Back up the database and filestore, replace the module files, restart Odoo, and upgrade `ribbon_medal`. Ensure the standard Ribbon/Tunic/Meskit rack products have product images configured for the fallback to display. Test editing an existing line and restoring deposited quantities on a database copy first.


## Upgrade to 18.0.2.7.5
No explicit schema migration is introduced. Back up the database and filestore, upgrade in staging first, and review Size attributes on existing decoration products if variant resolution still fails. The module may add a missing `S` or `L` value to an existing product template's `Size` attribute line so Odoo can generate the corresponding variant. This does not alter the shared BOM. After upgrade, test a normal rack and a rack with a partial customer deposit before production rollout.
