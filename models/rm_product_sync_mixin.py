# -*- coding: utf-8 -*-
import re

from odoo import _, fields, models
from odoo.exceptions import UserError


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
        (e.g. deleted manually), instead of failing outright."""
        attribute = self.env.ref(
            'ribbon_medal.product_attribute_size', raise_if_not_found=False)
        if not attribute:
            attribute = self.env['product.attribute'].search(
                [('name', '=', 'Size')], limit=1)
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

    def _prepare_sync_product_vals(self, name, uom_id=None):
        """Base vals for a new auto-managed product: sellable, non-stock,
        with a Size S/L attribute line. Callers may add more keys (e.g.
        image_1920) before creating. Pass uom_id to override the default
        Unit of Measure (e.g. Meter for a ribbon-material product)."""
        attribute, values = self._get_size_attribute_and_values()
        vals = {
            'name': name,
            'type': 'consu',
            'sale_ok': True,
<<<<<<< Updated upstream
            'purchase_ok': False,
=======
            'purchase_ok': True,
            'is_storable': True,
>>>>>>> Stashed changes
            'attribute_line_ids': [(0, 0, {
                'attribute_id': attribute.id,
                'value_ids': [(6, 0, values.ids)],
            })],
        }
        if uom_id:
            vals['uom_id'] = uom_id
            vals['uom_po_id'] = uom_id
        # 'tracking' only exists when the stock module happens to be
        # installed (we don't depend on it - installing this module
        # shouldn't also pull in the Inventory app). When it is present,
        # it's NOT NULL with no DB-level default, so set it explicitly.
        if 'tracking' in self.env['product.template']._fields:
            vals['tracking'] = 'none'
        return vals

    def _get_size_variant(self, product_tmpl, size):
        """Return the `size` ('S' or 'L') product.product variant of
        `product_tmpl`. Shared by every model that needs a specific-size
        variant of an auto-managed product (Rack Lines, Set Orders,
        Medal Parts, Medal Racks) so the lookup logic lives in one
        place instead of being duplicated per model."""
        if not product_tmpl:
            return self.env['product.product']
        return product_tmpl.product_variant_ids.filtered(
            lambda p: size in p.product_template_attribute_value_ids.mapped(
                'product_attribute_value_id.name')
        )[:1]

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

    def _sync_single_product(self, active, tmpl_field, name, initial_image=None, uom_id=None):
        """Create/reactivate or archive the product.template linked via
        `tmpl_field` (on a singleton `self`) to match `active`. Runs as
        sudo so this doesn't require product-module access rights.
        `initial_image`, if given, seeds a brand-new product's image
        (an image field's own inverse can't do this, since the product
        doesn't exist yet at that point). `uom_id`, if given, only
        applies when actually creating a new product - it's not applied
        retroactively to one that already exists."""
        self.ensure_one()
        tmpl = self[tmpl_field]
        if active:
            if tmpl:
                if not tmpl.active:
                    tmpl.sudo().active = True
            else:
                vals = self._prepare_sync_product_vals(name, uom_id=uom_id)
                if initial_image:
                    vals['image_1920'] = initial_image
                new_tmpl = self._create_product_resilient(vals)
                # Note: _create_product_resilient() already flushes
                # immediately after creating, so this template's variants
                # (Size S/L) are fully materialized to the DB before a
                # caller looping over many records moves to the next one.
                self.sudo().write({tmpl_field: new_tmpl.id})
        else:
            if tmpl and tmpl.active:
                tmpl.sudo().active = False
