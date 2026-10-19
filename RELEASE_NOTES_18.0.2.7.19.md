# Release 18.0.2.7.19

- Simplified `res.partner` autocomplete search to use Odoo 18 `_rec_names_search`.
- Search fields are `name`, `id_number`, `phone`, `mobile`, and `email`.
- Removed the custom `_search_display_name()` override so the module does not replace Odoo's standard partner-search pipeline.
- No `name_search()` override is introduced by this change.
