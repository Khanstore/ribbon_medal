# Release 18.0.2.7.18

## Fix
- Fixed `res.partner` Many2one autocomplete in Odoo 18 so partner searches also match the custom `id_number` field.
- This applies to the standard Sale Order `partner_id` customer field without requiring a separate search field or custom JS search UI.
- Removed the temporary Sale Order person-search UI introduced in the previous build.
