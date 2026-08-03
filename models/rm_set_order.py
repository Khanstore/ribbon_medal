# -*- coding: utf-8 -*-
from odoo import _, api, fields, models
from odoo.exceptions import UserError

# Fixed per the spec: each acquired decoration contributes this much Size-L
# ribbon material (in the ribbon product's own UoM, e.g. cm) and this many
# Kathi (mounting bar) units to a rack.
RIBBON_QTY_PER_ACQUISITION = 0.04
KATHI_QTY_PER_ACQUISITION = 0.25


class RmSetOrder(models.Model):
    """Ribbon Rack manufacturing request for one person.

    Bridges the read-only Acquisition Ledger (`rm.acquisition`) with
    Manufacturing: `action_get_or_create_bom` builds a `mrp.bom` specific
    to this person's exact combination of decorations (one line of Size-L
    ribbon per active acquisition, plus one Kathi line sized to the total
    count), and `action_create_mo` raises a `mrp.production` against that
    BoM for whatever quantity of racks is requested.
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
    mrp_production_ids = fields.One2many(
        'mrp.production', 'rm_set_order_id', string='Manufacturing Orders')
    mrp_production_count = fields.Integer(compute='_compute_mrp_production_count')

    def _default_product_id(self):
        rack_tmpl = self.env.ref('ribbon_medal.product_ribbon_rack', raise_if_not_found=False)
        return rack_tmpl.product_variant_id if rack_tmpl else self.env['product.product']

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

    def _prepare_bom_lines(self):
        """One BoM line of Size-L ribbon per active acquisition, plus one
        Kathi (mounting bar) line sized to the total acquisition count."""
        self.ensure_one()
        acquisitions = self.env['rm.acquisition'].search([('person_id', '=', self.person_id.id)])
        if not acquisitions:
            raise UserError(_(
                '%s has no acquisitions on the Acquisition Ledger to build a ribbon rack for.'
            ) % self.person_id.display_name)

        uom_unit = self.env.ref('uom.product_uom_unit', raise_if_not_found=False)
        lines = []
        for acquisition in acquisitions:
            decoration = acquisition.award_id.ribbon_id
            tmpl = decoration.ribbon_product_tmpl_id if decoration else False
            variant = self._get_size_l_variant(tmpl)
            if not variant:
                raise UserError(_(
                    'No Size L ribbon product variant found for "%s". Make sure that '
                    'decoration is flagged "Is Ribbon" so its ribbon product is created.'
                ) % (decoration.decoration_name if decoration else acquisition.award_id.name))
            lines.append((0, 0, {
                'product_id': variant.id,
                'product_qty': RIBBON_QTY_PER_ACQUISITION,
                'product_uom_id': variant.uom_id.id,
            }))

        kathi_tmpl = self.env.ref('ribbon_medal.product_ribbon_kathi', raise_if_not_found=False)
        if not kathi_tmpl:
            raise UserError(_('The "Ribbon Kathi" component product is not set up.'))
        kathi = kathi_tmpl.product_variant_id
        lines.append((0, 0, {
            'product_id': kathi.id,
            'product_qty': len(acquisitions) * KATHI_QTY_PER_ACQUISITION,
            'product_uom_id': (uom_unit or kathi.uom_id).id,
        }))
        return lines

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
