# -*- coding: utf-8 -*-
from odoo import fields, models


class SaleOrder(models.Model):
    _inherit = 'sale.order'

    person_id = fields.Many2one(
        'res.person', string='Person', index=True,
        help='If set, confirming this order runs the Issue Ribbon Rack '
             'cascade for this person (see res.person._issue_ribbon_rack_unit): '
             'reuses ready Rack/Line stock where possible, manufactures '
             'and reserves a new unit otherwise.')
    rack_unit_id = fields.Many2one(
        'rm.rack.unit', string='Rack Unit', readonly=True, copy=False,
        help='The specific Rack Product unit produced or handed over for '
             'this order - reserved for the Person above until delivered '
             '(see Manufacturing > Pending Deliveries).')
    rack_unit_id_state = fields.Selection(related='rack_unit_id.state', string='Rack Unit Status')

    def action_confirm(self):
        res = super().action_confirm()
        for order in self:
            if order.person_id and not order.rack_unit_id:
                unit, message = order.person_id._issue_ribbon_rack_unit()
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
