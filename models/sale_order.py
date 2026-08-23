# -*- coding: utf-8 -*-
from odoo import _, api, fields, models
from odoo.exceptions import UserError


class SaleOrder(models.Model):
    _inherit = 'sale.order'

    person_id = fields.Many2one(
        'res.person', string='Person', index=True,
        help='Legacy/fallback only - prefer setting Person directly on '
             'each Ribbon Rack order line instead, since one order can '
             'have Ribbon Rack lines for several different people. This '
             'is only used for a Ribbon Rack line that has no Person of '
             'its own set.')
    rack_unit_id = fields.Many2one(
        'rm.rack.unit', string='Rack Unit', readonly=True, copy=False,
        help='Set to the first Rack Unit issued for this order, for '
             'quick reference - see each Ribbon Rack line for its own '
             'specific unit when there is more than one.')
    rack_unit_id_state = fields.Selection(related='rack_unit_id.state', string='Rack Unit Status')

    def _get_ribbon_rack_product(self):
        rack_tmpl = self.env.ref('ribbon_medal.product_ribbon_rack', raise_if_not_found=False)
        return rack_tmpl.product_variant_id if rack_tmpl else self.env['product.product']

    def action_confirm(self):
        rack_product = self._get_ribbon_rack_product()
        if rack_product:
            for order in self:
                for line in order.order_line:
                    if line.product_id == rack_product and not (line.person_id or order.person_id):
                        raise UserError(_(
                            'Line "%s" on "%s" is a Ribbon Rack line with no '
                            'Person set - select one on that line before '
                            'confirming.'
                        ) % (line.product_id.display_name, order.name))
        res = super().action_confirm()
        for order in self:
            for line in order.order_line:
                person = line.person_id or (order.person_id if line.product_id == rack_product else False)
                if person and line.product_id == rack_product and not line.rack_unit_id:
                    unit, message = person._issue_ribbon_rack_unit()
                    line.rack_unit_id = unit.id
                    if not order.rack_unit_id:
                        order.rack_unit_id = unit.id
                    order.message_post(body=message)
        return res

    def action_open_rack_unit(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': 'Rack Unit',
            'res_model': 'rm.rack.unit',
            'view_mode': 'form',
            'res_id': self.rack_unit_id.id,
        }

    def action_add_ribbon_rack_line(self):
        """Pops the Person-picker wizard and, on confirm, creates a
        brand-new Ribbon Rack line already priced and noted - so there's
        no need to manually pick the Ribbon Rack product from the line's
        product dropdown at all."""
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _('Select a Person'),
            'res_model': 'rm.sale.line.person.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {'default_order_id': self.id},
        }


class SaleOrderLine(models.Model):
    _inherit = 'sale.order.line'

    person_id = fields.Many2one(
        'res.person', string='Person',
        help="Whose Ribbon Rack this line is for. Selecting them prices "
             "the line at their current estimated rack price and, on "
             "order confirmation, runs the Issue Ribbon Rack cascade for "
             "them (reuses ready stock where possible, manufactures and "
             "reserves a new unit otherwise).")
    rack_unit_id = fields.Many2one(
        'rm.rack.unit', string='Rack Unit', readonly=True, copy=False,
        help='The specific Rack Product unit produced or handed over for '
             'this line.')
    is_ribbon_rack_line = fields.Boolean(compute='_compute_is_ribbon_rack_line')

    @api.depends('product_id')
    def _compute_is_ribbon_rack_line(self):
        rack_tmpl = self.env.ref('ribbon_medal.product_ribbon_rack', raise_if_not_found=False)
        rack_product = rack_tmpl.product_variant_id if rack_tmpl else self.env['product.product']
        for line in self:
            line.is_ribbon_rack_line = bool(rack_product) and line.product_id == rack_product

    @api.onchange('product_id')
    def _onchange_product_id_ribbon_rack_prompt(self):
        """Selecting the generic Ribbon Rack product on a line prompts
        for the Person it's for, right here on the line, and prices +
        annotates the line immediately if one is already set."""
        if not self.is_ribbon_rack_line:
            return
        if self.person_id:
            self._apply_ribbon_rack_person()
        else:
            return {'warning': {
                'title': _('Select a Person'),
                'message': _(
                    "This is the Ribbon Rack product - use the Select "
                    "Person button on this line (save the order first if "
                    "needed) so it can be priced at their rack's current "
                    'estimated price.'),
            }}

    @api.onchange('person_id')
    def _onchange_person_id_ribbon_rack(self):
        if self.is_ribbon_rack_line:
            self._apply_ribbon_rack_person()

    def action_open_person_wizard(self):
        """Row button on a Ribbon Rack line - opens a popup to pick the
        Person it's for."""
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _('Select a Person'),
            'res_model': 'rm.sale.line.person.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {
                'default_line_id': self.id,
                'default_person_id': self.person_id.id,
            },
        }

    def _apply_ribbon_rack_person(self):
        """Price this line at the Person's current estimated rack price
        (res.person.rack_total_price) and add a small note right after
        the product name in the line description, e.g. 'Ribbon Rack /
        (For: John Doe)'."""
        self.ensure_one()
        self.price_unit = self.person_id.rack_total_price if self.person_id else 0.0
        lines = (self.name or self.product_id.name or '').split('\n')
        base_name = lines[0] if lines else (self.product_id.name or '')
        rest = [l for l in lines[1:] if not l.strip().startswith('(For:')]
        new_lines = [base_name]
        if self.person_id:
            new_lines.append(_('(For: %s)') % self.person_id.display_name)
        new_lines.extend(rest)
        self.name = '\n'.join(new_lines)
