# Ribbon Medal 18.0.2.7.8

## Fix
- Existing rack-line wizard restores person, rack type, and deposited medal quantities from the persisted sale order line.
- Wizard confirmation uses the standard Odoo `soft_reload` action.
- Ordinary sale lines keep the standard product configurator.

## Verification
Offline checks cover Python syntax, XML parsing, manifest data paths, ZIP integrity, and manual presence. This package has not been live-tested against the user's Odoo database; the rack edit and manufacturing workflow still requires runtime validation.


## 18.0.2.7.9 — Sale Order pencil button

- Fixed rack-line editor visibility by using `is_rack_line`.
- Explicitly target the Odoo 18 Sale Order line `<list>` in the inherited view.
- Retained the pencil icon and added an `Edit` label fallback.
- Legacy/imported finished-rack lines with empty `rack_type` are repaired when the editor is opened.
