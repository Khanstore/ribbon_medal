# -*- coding: utf-8 -*-
from odoo import _, api, fields, models
from odoo.exceptions import UserError


class RmSetOrder(models.Model):
    """Production request for one Force Member's Ribbon Set, Big Medal Set,
    or Mini Medal Set.

    Bridges the read-only Acquisition Ledger (`rm.acquisition` - how many
    times a person acquired each decoration, i.e. their "points" per
    decoration) with Manufacturing: `action_populate_lines` groups the
    ledger by decoration into `rm.set.order.line` rows (one per decoration,
    qty = point count), and `action_generate_manufacturing_orders` creates
    one `mrp.production` per line for the matching Set component product
    (Ribbon Bar / Big Medal / Mini Medal), in the `Point` UoM - so the
    BoM (defined per 1 Point) auto-scales raw material consumption.
    """
    _name = 'rm.set.order'
    _description = 'Ribbon / Medal Set Production Order'
    _order = 'id desc'

    name = fields.Char(default='New', copy=False, readonly=True)
    person_id = fields.Many2one(
        'res.person', required=True, string='Force Member',
        ondelete='restrict')
    set_type = fields.Selection([
        ('ribbon', 'Ribbon Set'),
        ('big_medal', 'Big Medal Set'),
        ('mini_medal', 'Mini Medal Set'),
    ], required=True, string='Set Type', default='ribbon')
    state = fields.Selection([
        ('draft', 'Draft'),
        ('confirmed', 'Confirmed'),
        ('produced', 'Produced'),
        ('cancel', 'Cancelled'),
    ], default='draft', string='Status', copy=False, tracking=True)
    line_ids = fields.One2many(
        'rm.set.order.line', 'order_id', string='Lines')
    production_count = fields.Integer(
        string='Manufacturing Orders', compute='_compute_production_count')

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('name', 'New') == 'New':
                vals['name'] = self.env['ir.sequence'].next_by_code(
                    'rm.set.order') or 'New'
        return super().create(vals_list)

    def _compute_production_count(self):
        for order in self:
            order.production_count = len(
                order.line_ids.mapped('mrp_production_id'))

    def _get_component_product(self, award):
        """Resolve the Set component product (UoM=Point) to manufacture for
        a given rm.prb award, according to this order's set_type."""
        self.ensure_one()
        if self.set_type == 'ribbon':
            return award.ribbon_id.ribbon_bar_product_id
        if self.set_type == 'big_medal':
            return award.medal_id.big_medal_product_id
        if self.set_type == 'mini_medal':
            return award.medal_id.mini_medal_product_id
        return self.env['product.product']

    def action_populate_lines(self):
        """(Re)build line_ids from the person's live Acquisition Ledger:
        one line per decoration actually earned, qty = number of times it
        was earned (their "points" for that decoration), restricted to
        decorations relevant to this order's set_type (is_ribbon for Ribbon
        Set, is_medal for the two Medal Sets) and that have a configured
        Set component product."""
        Acquisition = self.env['rm.acquisition']
        Line = self.env['rm.set.order.line']
        for order in self:
            if order.state != 'draft':
                raise UserError(_(
                    'Only Draft orders can have their lines repopulated.'))
            order.line_ids.unlink()

            entries = Acquisition.search([('person_id', '=', order.person_id.id)])
            point_counts = {}
            for entry in entries:
                award = entry.award_id
                if order.set_type == 'ribbon' and not award.is_ribbon:
                    continue
                if order.set_type in ('big_medal', 'mini_medal') and not award.is_medal:
                    continue
                point_counts[award] = point_counts.get(award, 0) + 1

            lines = []
            for award, point_qty in point_counts.items():
                component = order._get_component_product(award)
                if not component:
                    continue
                lines.append({
                    'order_id': order.id,
                    'award_id': award.id,
                    'point_qty': point_qty,
                    'component_product_id': component.id,
                })
            if lines:
                Line.create(lines)
        return True

    def action_confirm(self):
        for order in self:
            if not order.line_ids:
                raise UserError(_(
                    'Populate the lines before confirming this order.'))
            order.state = 'confirmed'

    def action_generate_manufacturing_orders(self):
        Production = self.env['mrp.production']
        Bom = self.env['mrp.bom']
        for order in self:
            if order.state != 'confirmed':
                raise UserError(_(
                    'Only Confirmed orders can generate Manufacturing Orders.'))
            for line in order.line_ids.filtered(lambda l: not l.mrp_production_id):
                bom = Bom.search([
                    ('product_tmpl_id', '=', line.component_product_id.product_tmpl_id.id),
                ], limit=1)
                production = Production.create({
                    'product_id': line.component_product_id.id,
                    'product_qty': line.point_qty,
                    'product_uom_id': line.component_product_id.uom_id.id,
                    'bom_id': bom.id if bom else False,
                    'origin': order.name,
                })
                line.mrp_production_id = production.id
            order.state = 'produced'
        return True

    def action_view_productions(self):
        self.ensure_one()
        productions = self.line_ids.mapped('mrp_production_id')
        return {
            'type': 'ir.actions.act_window',
            'name': _('Manufacturing Orders'),
            'res_model': 'mrp.production',
            'view_mode': 'list,form',
            'domain': [('id', 'in', productions.ids)],
        }

    def action_cancel(self):
        for order in self:
            if order.line_ids.mapped('mrp_production_id'):
                raise UserError(_(
                    'Cannot cancel: Manufacturing Orders were already '
                    'generated for this Set Order.'))
            order.state = 'cancel'

    def action_reset_to_draft(self):
        self.write({'state': 'draft'})


class RmSetOrderLine(models.Model):
    _name = 'rm.set.order.line'
    _description = 'Ribbon / Medal Set Production Order Line'
    _rec_name = 'award_id'

    order_id = fields.Many2one(
        'rm.set.order', required=True, ondelete='cascade', index=True)
    person_id = fields.Many2one(
        related='order_id.person_id', store=True, string='Force Member')
    award_id = fields.Many2one('rm.prb', required=True, string='Award')
    point_qty = fields.Integer(string='Points', default=1)
    component_product_id = fields.Many2one(
        'product.product', string='Set Component')
    mrp_production_id = fields.Many2one(
        'mrp.production', string='Manufacturing Order',
        readonly=True, copy=False)
