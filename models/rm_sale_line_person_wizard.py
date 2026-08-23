# -*- coding: utf-8 -*-
from odoo import _, api, fields, models
from odoo.exceptions import UserError


class RmSaleLinePersonWizard(models.TransientModel):
    _name = 'rm.sale.line.person.wizard'
    _description = 'Select Person for a Ribbon Rack Order Line'

    # Either line_id is set (re-price/re-note an existing Ribbon Rack
    # line) or order_id is set (create a brand-new Ribbon Rack line on
    # that order, fully priced and noted, in one step).
    line_id = fields.Many2one('sale.order.line')
    order_id = fields.Many2one('sale.order')
    search_term = fields.Char(string='Search')
    result_person_ids = fields.Many2many(
        'res.person', string='Matches', compute='_compute_results')
    person_id = fields.Many2one(
        'res.person', string='Person', required=True,
        help='Pick the matching person from the results below, or type '
             'a name/ID/phone/mobile/email directly into this field to '
             'search.')
    rack_total_price = fields.Float(related='person_id.rack_total_price', readonly=True)

    @api.depends('search_term')
    def _compute_results(self):
        Person = self.env['res.person']
        for wizard in self:
            term = wizard.search_term
            if not term:
                wizard.result_person_ids = Person
                continue
            clauses = [
                ('name', 'ilike', term),
                ('id_number', 'ilike', term),
                ('phone', 'ilike', term),
                ('mobile', 'ilike', term),
                ('email', 'ilike', term),
                ('rank_id.name', 'ilike', term),
                ('current_workplace.name', 'ilike', term),
            ]
            domain = ['|'] * (len(clauses) - 1) + clauses
            wizard.result_person_ids = Person.search(domain, limit=20)

    def action_confirm(self):
        self.ensure_one()
        if self.line_id:
            if not self.line_id.exists():
                raise UserError(_(
                    'This order line no longer exists - reopen the order and try again.'))
            self.line_id.person_id = self.person_id
            self.line_id._apply_ribbon_rack_person()
        elif self.order_id:
            if not self.order_id.exists():
                raise UserError(_(
                    'This order no longer exists - reopen it and try again.'))
            rack_tmpl = self.env.ref('ribbon_medal.product_ribbon_rack', raise_if_not_found=False)
            if not rack_tmpl:
                raise UserError(_('The "Ribbon Rack" product is not set up.'))
            self.env['sale.order.line'].create({
                'order_id': self.order_id.id,
                'product_id': rack_tmpl.product_variant_id.id,
                'product_uom_qty': 1,
                'price_unit': self.person_id.rack_total_price,
                'person_id': self.person_id.id,
                'name': _('%s\n(For: %s)') % (rack_tmpl.name, self.person_id.display_name),
            })
        else:
            raise UserError(_('Nothing to apply this to - reopen the order and try again.'))
        return {'type': 'ir.actions.client', 'tag': 'soft_reload'}
