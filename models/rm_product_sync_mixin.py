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
            'purchase_ok': True,
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

    # ------------------------------------------------------------------
    # Shared-template + per-record "Combination" variant support.
    #
    # Used by rm.rack.line / rm.rack.product / rm.medal.part /
    # rm.medal.rack instead of _prepare_sync_product_vals above: rather
    # than each unique combination getting its OWN product.template
    # (which is what those 4 models used to do, and what
    # _prepare_sync_product_vals above is still built for), every
    # combination within one of those 4 families is instead a VARIANT
    # of ONE shared template for that family, distinguished by a
    # dedicated "Combination" product.attribute whose values are
    # created one-per-record, lazily, the first time that record
    # actually needs a product (same lazy timing as before - nothing
    # about WHEN a product gets created changes here, only HOW).
    #
    # This does NOT touch rm.decoration / rm.attachment's use of
    # _prepare_sync_product_vals above - those keep their own
    # Size-only, one-template-per-record approach unchanged.
    # ------------------------------------------------------------------

    def _get_or_create_rm_shared_template(self, template_name, extra_vals=None):
        """Find-or-create the ONE shared product.template for a whole
        family of combination-identity records - e.g. every
        rm.rack.line row shares this ONE 'Rack Line' template,
        distinguished from each other as variants (see
        _get_or_create_rm_variant below), not as separate templates.
        Deterministic (lowest id) if duplicates are ever found, same
        defensive reasoning as _get_size_attribute_and_values above."""
        Template = self.env['product.template']
        candidates = Template.search([('name', '=', template_name)], order='id asc')
        if len(candidates) > 1:
            _logger.warning(
                "Multiple '%s' product.template records found (ids %s) - "
                "using the oldest (id %s) for every sync. Merge or remove "
                "the duplicates to avoid variants being silently split "
                "across two templates.", template_name, candidates.ids, candidates[0].id)
        template = candidates[:1]
        if template:
            return template
        vals = {
            'name': template_name,
            'type': 'consu',
            'sale_ok': True,
            'purchase_ok': True,
            'is_storable': True,
        }
        if 'tracking' in Template._fields:
            vals['tracking'] = 'none'
        if extra_vals:
            vals.update(extra_vals)
        return self._create_product_resilient(vals)

    def _get_or_create_rm_attribute(self, attribute_name):
        """Find-or-create the dedicated "Combination" product.attribute
        for one family (its own attribute, not shared across families,
        so e.g. Rack Line's combinations never mix into Medal Part's
        value list). create_variant='always' so adding a value
        immediately produces the matching product.product, the same
        way _get_size_attribute_and_values' Size attribute already
        works for rm.decoration/rm.attachment."""
        Attribute = self.env['product.attribute']
        candidates = Attribute.search([('name', '=', attribute_name)], order='id asc')
        if len(candidates) > 1:
            _logger.warning(
                "Multiple '%s' product.attribute records found (ids %s) - "
                "using the oldest (id %s) for every sync.",
                attribute_name, candidates.ids, candidates[0].id)
        attribute = candidates[:1]
        if attribute:
            return attribute
        return Attribute.create({
            'name': attribute_name,
            'create_variant': 'always',
        })

    def _get_or_create_rm_variant(self, template, attribute, value_name):
        """Add ONE brand-new product.attribute.value (named
        `value_name`) to `template`'s attribute line for `attribute`,
        creating that line if `template` doesn't have one yet, and
        return the product.product variant Odoo's own variant
        generation produces for it.

        Always creates a fresh value rather than searching for an
        existing one by name - this is only ever called once per
        record (from that record's own _ensure_product, guarded by
        "if not self.product_id"), and each record's combination is
        already guaranteed unique by its own identity_key SQL
        constraint, so there's nothing to find-or-reuse here."""
        value = self.env['product.attribute.value'].create({
            'name': value_name,
            'attribute_id': attribute.id,
        })
        line = template.attribute_line_ids.filtered(lambda l: l.attribute_id == attribute)
        if line:
            line.value_ids = [(4, value.id)]
        else:
            self.env['product.template.attribute.line'].create({
                'product_tmpl_id': template.id,
                'attribute_id': attribute.id,
                'value_ids': [(6, 0, [value.id])],
            })
        template.invalidate_recordset(['product_variant_ids'])
        variant = template.product_variant_ids.filtered(
            lambda p: value in p.product_template_attribute_value_ids.product_attribute_value_id
        )[:1]
        if not variant:
            raise UserError(_(
                'Failed to create a product variant for "%s" - check that '
                '"%s" still has create_variant set to "Always".'
            ) % (value_name, attribute.display_name))
        return variant

    def _ensure_rm_variant(self, template_name, attribute_name, value_name, extra_template_vals=None):
        """Convenience wrapper tying the three methods above together -
        called by each of the 4 combination-identity models' own
        _ensure_product(). Returns the product.product variant for
        THIS record's own exact combination, creating the shared
        template/attribute/value/variant chain as needed."""
        template = self._get_or_create_rm_shared_template(template_name, extra_vals=extra_template_vals)
        attribute = self._get_or_create_rm_attribute(attribute_name)
        return self._get_or_create_rm_variant(template, attribute, value_name)

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

    # ------------------------------------------------------------------
    # Combination-variant support: for a model whose identity is an
    # arbitrarily-growing combination (Rack Lines, Rack Products, Medal
    # Parts, Medal Racks), rather than each new combination getting its
    # own product.template (the Size-based helpers above are for a
    # different shape of problem - a small FIXED set of S/L values
    # crossed against many templates), every combination instead
    # becomes one product.attribute.value under ONE shared template per
    # family. Adding a new value to that template's attribute line is
    # what makes Odoo generate the matching product.product variant, so
    # the number of *templates* stays fixed (one per family) no matter
    # how many distinct combinations are ever seen - only the variant
    # count grows.
    # ------------------------------------------------------------------

    def _rm_find_or_create_attribute(self, name):
        """Find-or-create (by name, deterministically lowest id if
        duplicates exist) the product.attribute used for one family's
        combination values. create_variant='always' so adding a value
        to the template's attribute line immediately materialises the
        product.product variant, matching this module's existing
        pattern of creating things explicitly/eagerly rather than
        relying on Odoo's lazier 'dynamic' variant creation."""
        Attribute = self.env['product.attribute'].sudo()
        candidates = Attribute.search([('name', '=', name)], order='id asc')
        if candidates:
            return candidates[0]
        return Attribute.create({'name': name, 'create_variant': 'always'})

    def _rm_find_or_create_shared_template(self, name, extra_vals=None):
        """Find-or-create (by name, deterministically lowest id if
        duplicates exist) the ONE product.template shared by every
        record of one family (e.g. every rm.rack.product shares the
        same 'Ribbon Rack' template). Not sellable/purchasable itself -
        only its per-combination VARIANTS are ever actually used."""
        Product = self.env['product.template'].sudo()
        candidates = Product.search([('name', '=', name)], order='id asc')
        if candidates:
            tmpl = candidates[0]
        else:
            vals = {
                'name': name,
                'type': 'consu',
                'sale_ok': False,
                'purchase_ok': False,
                'is_storable': True,
            }
            if 'tracking' in Product._fields:
                vals['tracking'] = 'none'
            tmpl = self._create_product_resilient(vals)
        if extra_vals:
            # Harmless to (re)write every call - same values every time
            # for a given family (e.g. rm_is_finished_rack).
            tmpl.write(extra_vals)
        return tmpl

    def _ensure_rm_variant(self, template_name, attribute_name, value_label, extra_template_vals=None):
        """Return the product.product variant for `value_label` under
        the ONE shared `template_name` template for this family -
        creating the attribute value / attribute line / template
        itself, in that order, the first time each is needed.
        `value_label` should be unique and stable per distinct
        combination - it doesn't need to be pretty (callers that want a
        short, friendly, user-facing label - e.g. "Rack #6" - store
        that separately on their own product_label field; it can also
        double as value_label directly, as rm.rack.product does, since
        uniqueness there comes from the record's own id)."""
        attribute = self._rm_find_or_create_attribute(attribute_name)
        tmpl = self._rm_find_or_create_shared_template(template_name, extra_template_vals)

        value = attribute.value_ids.filtered(lambda v: v.name == value_label)[:1]
        if not value:
            value = self.env['product.attribute.value'].sudo().create({
                'name': value_label, 'attribute_id': attribute.id,
            })

        line = tmpl.attribute_line_ids.filtered(lambda l: l.attribute_id == attribute)
        if not line:
            tmpl.sudo().write({'attribute_line_ids': [(0, 0, {
                'attribute_id': attribute.id, 'value_ids': [(6, 0, value.ids)],
            })]})
        elif value not in line.value_ids:
            line.sudo().write({'value_ids': [(4, value.id)]})

        tmpl.invalidate_recordset(['product_variant_ids'])
        variant = tmpl.product_variant_ids.filtered(
            lambda p: value in p.product_template_attribute_value_ids.mapped(
                'product_attribute_value_id'))[:1]
        if not variant:
            raise UserError(_(
                'Could not resolve the product variant for "%(value)s" under '
                '"%(template)s" - check that the "%(attribute)s" product '
                'attribute is set to create variants "Instantly".'
            ) % {'value': value_label, 'template': template_name, 'attribute': attribute_name})
        return variant
