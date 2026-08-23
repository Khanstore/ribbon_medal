# -*- coding: utf-8 -*-
import logging
import re

from odoo import _, fields, models
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)


class RmProductSyncMixin(models.AbstractModel):
    """Shared logic for auto-managing a sellable product.template (with
    Small/Large size variants) that tracks some condition on the
    inheriting model - used by rm.decoration (is_ribbon/is_medal flags)
    and rm.attachment (its own active state)."""
    _name = 'rm.product.sync.mixin'
    _description = 'Auto-managed Product Sync Mixin'

    def _get_size_attribute_and_values(self):
        """Return the shared 'Size' product.attribute and its S/L values,
        used on every auto-created product. Falls back to
        finding-or-creating them if the module's data record is missing
        (e.g. deleted manually), instead of failing outright. If more
        than one 'Size' attribute exists (e.g. left over from an earlier
        partial install), always resolves to the same one (lowest id)
        deterministically instead of whatever `search()` happens to
        return - resolving to a different row between syncs is what
        makes Odoo treat a product's variant combination as changed and
        delete/recreate its variants."""
        attribute = self.env.ref(
            'ribbon_medal.product_attribute_size', raise_if_not_found=False)
        if not attribute or not attribute.exists():
            candidates = self.env['product.attribute'].search(
                [('name', '=', 'Size')], order='id asc')
            if len(candidates) > 1:
                _logger.warning(
                    "Multiple 'Size' product.attribute records found (ids %s) - "
                    "using the oldest (id %s) for every sync. Merge or remove "
                    "the duplicates to avoid product variants being silently "
                    "deleted and recreated.", candidates.ids, candidates[0].id)
            attribute = candidates[:1]
            if not attribute:
                attribute = self.env['product.attribute'].create({
                    'name': 'Size',
                    'create_variant': 'always',
                })
        values = attribute.value_ids.filtered(lambda v: v.name in ('S', 'L'))
        missing = [name for name in ('S', 'L') if name not in values.mapped('name')]
        if missing:
            values |= self.env['product.attribute.value'].create([
                {'name': name, 'attribute_id': attribute.id} for name in missing
            ])
        return attribute, values

    def _prepare_sync_product_vals(self, name, uom_id=None, size_variants='both'):
        """Base vals for a new auto-managed product.
        size_variants: 'both' (create S and L), 'l_only' (create only L), or 's_only' (create only S)"""
        attribute, values = self._get_size_attribute_and_values()

        if size_variants == 'l_only':
            value_ids = values.filtered(lambda v: v.name == 'L')
        elif size_variants == 's_only':
            value_ids = values.filtered(lambda v: v.name == 'S')
        else:  # 'both'
            value_ids = values

        vals = {
            'name': name,
            'type': 'consu',  # Changed from 'consu' to 'stock'
            'sale_ok': True,
            'purchase_ok': False,
            'is_storable': True,
            'attribute_line_ids': [(0, 0, {
                'attribute_id': attribute.id,
                'value_ids': [(6, 0, value_ids.ids)],
            })],
        }
        if uom_id:
            vals['uom_id'] = uom_id
            vals['uom_po_id'] = uom_id
        if 'tracking' in self.env['product.template']._fields:
            vals['tracking'] = 'none'
        return vals

    def _zero_value_for_field(self, field):
        """A conservative, inoffensive default for a field we don't
        actually care about, just to satisfy a NOT NULL constraint."""
        if field.type == 'boolean':
            return False
        if field.type in ('integer', 'float', 'monetary'):
            return 0
        if field.type in ('char', 'text', 'html'):
            return ''
        if field.type == 'date':
            return fields.Date.today()
        if field.type == 'datetime':
            return fields.Datetime.now()
        if field.type == 'selection':
            try:
                options = field.get_description(self.env)['selection']
                for key, _label in options:
                    if key:
                        return key
                return options[0][0] if options else False
            except Exception:
                return False
        return False

    def _create_product_resilient(self, vals):
        """Create a product.template, automatically supplying a default
        for any field THIS environment's installed modules happen to
        require at the DB level with no ORM-level default of their own
        (seen in practice: stock's 'tracking', a customization's
        'base_unit_count' - the exact set depends on which third-party
        modules are installed, so rather than hardcoding a fixed list
        this discovers them one at a time from the DB error and retries)."""
        Product = self.env['product.template'].sudo()
        vals = dict(vals)
        patched_fields = set()
        for _attempt in range(10):
            try:
                with self.env.cr.savepoint():
                    new_tmpl = Product.create(vals)
                    # Force immediate flush so any NOT NULL violation
                    # surfaces right here (and can be retried) instead of
                    # much later, deep in an unrelated flush.
                    self.env.flush_all()
                    return new_tmpl
            except Exception as exc:
                match = re.search(r'column "(\w+)"', str(exc))
                field_name = match.group(1) if match else None
                field = Product._fields.get(field_name) if field_name else None
                if not field or field_name in patched_fields:
                    raise
                patched_fields.add(field_name)
                vals[field_name] = self._zero_value_for_field(field)
        raise UserError(_(
            'Could not create product "%s" - repeatedly hit new required fields (%s).'
        ) % (vals.get('name'), ', '.join(sorted(patched_fields))))

    def _sync_single_product(self, active, tmpl_field, name, initial_image=None, uom_id=None, size_variants='both'):
        """Create/reactivate or archive the product.template linked via
        `tmpl_field` on a singleton `self` to match `active`.
        size_variants: 'both', 'l_only', or 's_only'"""
        self.ensure_one()
        tmpl = self[tmpl_field]
        if tmpl and not tmpl.exists():
            # Stale reference - the linked template/variant is gone
            # (e.g. deleted outside this mixin's control). Drop it and
            # fall through to rebuild it below instead of crashing.
            _logger.warning(
                "%s.%s pointed at a %s that no longer exists (id %s) - "
                "rebuilding it.", self._name, tmpl_field, tmpl._name, tmpl.id)
            self.sudo().write({tmpl_field: False})
            tmpl = self.env['product.template']
        if active:
            if tmpl:
                if not tmpl.active:
                    tmpl.sudo().active = True
            else:
                vals = self._prepare_sync_product_vals(name, uom_id=uom_id, size_variants=size_variants)
                if initial_image:
                    vals['image_1920'] = initial_image
                new_tmpl = self._create_product_resilient(vals)
                self.sudo().write({tmpl_field: new_tmpl.id})
        else:
            if tmpl and tmpl.active:
                tmpl.sudo().active = False
