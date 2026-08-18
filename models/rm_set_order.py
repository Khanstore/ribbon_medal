# -*- coding: utf-8 -*-
from odoo import _, api, fields, models
from odoo.exceptions import UserError


class RmSetOrder(models.Model):
    """Ribbon Rack manufacturing request for one person.

    Bridges the read-only Acquisition Ledger (`rm.acquisition`) with
    Manufacturing: `action_get_or_create_bom` builds a `mrp.bom` specific
    to this person's exact combination of decorations, following the
    rules on `template_id` (`rm.set.template` -> `rm.set.template.component`)
    rather than a fixed hardcoded recipe - each rule says which category
    of material is needed, at what scope (per cell / per rack / per
    attachment), how much, and whether the product is fixed or picked by
    the user. `action_create_mo` then raises a `mrp.production` against
    that BoM for whatever quantity of racks is requested.
    """
    _name = 'rm.set.order'
    _description = 'Ribbon Rack Set Order'
    _order = 'id desc'

    name = fields.Char(default='New', copy=False, readonly=True)
    person_id = fields.Many2one(
        'res.person', required=True, string='Person', ondelete='restrict', index=True)
    product_id = fields.Many2one(
        'product.product', required=True, string='Ribbon Rack Product',
        default=lambda self: self._default_product_id(),
        help='The finished "Ribbon Rack" product this order manufactures.')
    template_id = fields.Many2one(
        'rm.set.template', string='Set Template', required=True,
        default=lambda self: self._default_template_id(),
        help='Defines what this set is made of, as category-level rules '
             'rather than a fixed recipe.')
    quantity = fields.Float(string='Default Quantity', default=1.0, required=True)
    unit_price = fields.Float(
        string='Unit Price', compute='_compute_unit_price',
        help="This person's rack_total_price: sum of each acquired "
             "ribbon's list price plus each acquisition's attachment "
             'device list price (when set).')
    total_price = fields.Float(string='Estimated Total Price', compute='_compute_unit_price')
    bom_id = fields.Many2one(
        'mrp.bom', string='Bill of Materials', readonly=True, copy=False,
        help="This person's specific ribbon combination, built the first "
             'time a BoM is needed and reused after that.')
    line_ids = fields.One2many(
        'rm.set.order.line', 'order_id', string='Per-Cell Component Selections',
        help='Explicit product choices for template rules marked "User '
             'Picks Product" that cannot be auto-resolved (e.g. which '
             'backing material) - RIBBON and ATTACHMENT resolve '
             'automatically from the acquisition itself and never need '
             'a row here.')
    mrp_production_ids = fields.One2many(
        'mrp.production', 'rm_set_order_id', string='Manufacturing Orders')
    mrp_production_count = fields.Integer(compute='_compute_mrp_production_count')

    def _default_product_id(self):
        rack_tmpl = self.env.ref('ribbon_medal.product_ribbon_rack', raise_if_not_found=False)
        return rack_tmpl.product_variant_id if rack_tmpl else self.env['product.product']

    def _default_template_id(self):
        return self.env['rm.set.template'].search(
            [('category', '=', 'ribbon_rack')], limit=1)

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('name', 'New') == 'New':
                vals['name'] = self.env['ir.sequence'].next_by_code('rm.set.order') or 'New'
        return super().create(vals_list)

    def _compute_mrp_production_count(self):
        for order in self:
            order.mrp_production_count = len(order.mrp_production_ids)

    def _compute_unit_price(self):
        for order in self:
            order.unit_price = order.person_id.rack_total_price
            order.total_price = order.unit_price * (order.quantity or 0.0)

    def _get_size_l_variant(self, product_tmpl):
        """Return the Size=L product.product variant of `product_tmpl`."""
        if not product_tmpl:
            return self.env['product.product']
        return product_tmpl.product_variant_ids.filtered(
            lambda p: 'L' in p.product_template_attribute_value_ids.mapped(
                'product_attribute_value_id.name')
        )[:1]

    def action_prepare_selection_lines(self):
        """Create a blank rm.set.order.line for every (cell, category)
        combination that needs an explicit user choice but doesn't have
        one yet, so the form has rows ready to fill in before
        generating a BoM. Safe to call repeatedly - never duplicates an
        existing selection."""
        self.ensure_one()
        if not self.template_id:
            raise UserError(_('Select a Set Template first.'))
        acquisitions = self.env['rm.acquisition'].search([('person_id', '=', self.person_id.id)])
        rules = self.template_id.component_rule_ids.filtered(
            lambda r: r.is_user_selected and r.category_id.code not in ('RIBBON', 'ATTACHMENT'))
        Line = self.env['rm.set.order.line']
        existing = set(Line.search([('order_id', '=', self.id)]).mapped(
            lambda l: (l.award_id.id, l.category_id.id)))
        to_create = []
        for rule in rules:
            if rule.scope == 'per_rack':
                if (False, rule.category_id.id) not in existing:
                    to_create.append({'order_id': self.id, 'category_id': rule.category_id.id})
                    existing.add((False, rule.category_id.id))
            else:
                for acquisition in acquisitions:
                    if rule.scope == 'per_attachment' and not acquisition.attachment_id:
                        continue
                    key = (acquisition.award_id.id, rule.category_id.id)
                    if key not in existing:
                        to_create.append({
                            'order_id': self.id,
                            'award_id': acquisition.award_id.id,
                            'category_id': rule.category_id.id,
                        })
                        existing.add(key)
        if to_create:
            Line.create(to_create)
        return True

    def _resolve_rule_product(self, rule, acquisition, missing):
        """Return the product.product this rule resolves to for
        `acquisition` (False for a per_rack rule), or False (and append
        a description to `missing`) if it can't be resolved."""
        if not rule.is_user_selected:
            product = rule.default_product_id.product_variant_id
            if not product:
                missing.append(_('Default product for category "%s"') % rule.category_id.name)
            return product

        code = rule.category_id.code
        if code == 'RIBBON' and acquisition:
            decoration = acquisition.award_id.ribbon_id
            tmpl = decoration.ribbon_product_tmpl_id if decoration else False
            variant = self._get_size_l_variant(tmpl)
            if not variant:
                missing.append(_('Size L ribbon variant for "%s"') % acquisition.award_id.display_name)
            return variant

        if code == 'ATTACHMENT' and acquisition:
            if not acquisition.attachment_id:
                return self.env['product.product']
            product = acquisition.attachment_id.device_product_tmpl_id.product_variant_id
            if not product:
                missing.append(_('Attachment device product for "%s"') % acquisition.award_id.display_name)
            return product

        # Anything else user-selected (e.g. BACKING): look up a captured
        # selection line.
        domain = [
            ('order_id', '=', self.id),
            ('category_id', '=', rule.category_id.id),
            ('award_id', '=', acquisition.award_id.id if acquisition else False),
        ]
        line = self.env['rm.set.order.line'].search(domain, limit=1)
        if not line or not line.product_id:
            label = acquisition.award_id.display_name if acquisition else self.template_id.display_name
            missing.append(_('%s selection for "%s"') % (rule.category_id.name, label))
            return self.env['product.product']
        return line.product_id

    def _prepare_bom_lines(self):
        """Build BoM lines by walking this order's template rules:
        per_cell and per_attachment rules apply once per acquisition
        (per_attachment only for cells that have one), per_rack rules
        apply once for the whole order. Lines for the same product are
        aggregated into one."""
        self.ensure_one()
        if not self.template_id:
            raise UserError(_('Select a Set Template first.'))
        acquisitions = self.env['rm.acquisition'].search([('person_id', '=', self.person_id.id)])
        if not acquisitions:
            raise UserError(_(
                '%s has no acquisitions on the Acquisition Ledger to build a set for.'
            ) % self.person_id.display_name)

        rules = self.template_id.component_rule_ids
        missing = []
        totals = {}  # {(product_id, uom_id): qty}

        def add(product, rule):
            if not product:
                return
            uom = rule.uom_id or product.uom_id
            key = (product.id, uom.id)
            totals[key] = totals.get(key, 0.0) + rule.quantity

        per_cell_rules = rules.filtered(lambda r: r.scope == 'per_cell')
        per_attachment_rules = rules.filtered(lambda r: r.scope == 'per_attachment')
        per_rack_rules = rules.filtered(lambda r: r.scope == 'per_rack')

        for acquisition in acquisitions:
            for rule in per_cell_rules:
                add(self._resolve_rule_product(rule, acquisition, missing), rule)
            if acquisition.attachment_id:
                for rule in per_attachment_rules:
                    add(self._resolve_rule_product(rule, acquisition, missing), rule)

        for rule in per_rack_rules:
            add(self._resolve_rule_product(rule, False, missing), rule)

        if missing:
            raise UserError(_('Missing product selection(s):\n- %s') % '\n- '.join(missing))

        return [(0, 0, {
            'product_id': product_id,
            'product_qty': qty,
            'product_uom_id': uom_id,
        }) for (product_id, uom_id), qty in totals.items()]

    def action_get_or_create_bom(self):
        """Return this order's BoM, creating it the first time it's needed."""
        self.ensure_one()
        if self.bom_id:
            return self.bom_id
        bom = self.env['mrp.bom'].create({
            'product_tmpl_id': self.product_id.product_tmpl_id.id,
            'product_id': self.product_id.id,
            'product_qty': 1.0,
            'type': 'normal',
            'code': f'RACK-{self.person_id.display_name}',
            'bom_line_ids': self._prepare_bom_lines(),
        })
        self.bom_id = bom.id
        return bom

    def action_rebuild_bom(self):
        """Discard and rebuild the BoM from the person's current ledger -
        use after their acquisitions have changed since the BoM was
        first generated."""
        self.ensure_one()
        old_bom = self.bom_id
        self.bom_id = False
        new_bom = self.action_get_or_create_bom()
        if old_bom and old_bom != new_bom:
            old_bom.unlink()
        return new_bom

    def action_open_mo_wizard(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _('Generate Manufacturing Order'),
            'res_model': 'rm.set.order.mo.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {'default_order_id': self.id, 'default_quantity': self.quantity},
        }

    def action_create_mo(self, quantity=None):
        """Create and confirm an mrp.production for `quantity` racks
        (default: this order's `quantity`), auto-creating this person's
        BoM first if it doesn't exist yet."""
        self.ensure_one()
        bom = self.action_get_or_create_bom()
        qty = quantity if quantity else (self.quantity or 1.0)
        production = self.env['mrp.production'].create({
            'product_id': self.product_id.id,
            'product_qty': qty,
            'product_uom_id': self.product_id.uom_id.id,
            'bom_id': bom.id,
            'rm_set_order_id': self.id,
            'origin': self.name,
        })
        production.action_confirm()
        # Note: deliberately NOT auto-opening the mrp.production form here.
        # Use the "Manufacturing Orders" smart button on this order (list
        # view) to see it instead.
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('Manufacturing Order Created'),
                'message': _('%s was created and confirmed for %s (qty %s). '
                             'Use the Manufacturing Orders button to view it.')
                           % (production.name, self.person_id.display_name, qty),
                'type': 'success',
                'sticky': False,
            },
        }

    def action_view_mrp_productions(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _('Manufacturing Orders'),
            'res_model': 'mrp.production',
            'view_mode': 'list,form',
            'domain': [('rm_set_order_id', '=', self.id)],
        }


class RmSetOrderMoWizard(models.TransientModel):
    _name = 'rm.set.order.mo.wizard'
    _description = 'Generate Manufacturing Order for a Ribbon Rack Set Order'

    order_id = fields.Many2one('rm.set.order', required=True, ondelete='cascade')
    quantity = fields.Float(string='Quantity', default=1.0, required=True)

    def action_confirm(self):
        self.ensure_one()
        if self.quantity <= 0:
            raise UserError(_('Quantity must be greater than zero.'))
        return self.order_id.action_create_mo(quantity=self.quantity)
