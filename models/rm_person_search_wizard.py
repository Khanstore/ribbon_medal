# -*- coding: utf-8 -*-
from odoo import _, api, fields, models
from odoo.exceptions import UserError


class RmPersonSearchWizard(models.TransientModel):
    """Front-desk quick search: find an existing person by name, ID
    number, phone, mobile, email, rank, or unit - or fall through to
    creating a new one - then move straight into placing a Ribbon Rack
    order for them.

    Two modes, toggled by `deep_search`:
    - Off (default): one simple search box, matched against every
      searchable field via OR - the fast path for the common case.
    - On: the full per-field breakdown (Name/ID/Phone/Mobile/Email/
      Rank/Unit), each independently filterable, OR-combined across
      whichever ones are actually filled in.

    Confirming here only creates a Sale Order (with one Ribbon Rack
    line, priced at the person's current estimated rack price) - it
    does NOT trigger manufacturing yet. Manufacturing/allocation only
    happens once that Sale Order is itself confirmed (see the
    sale.order override in models/sale_order.py), so staff get a
    chance to review price/details first.
    """
    _name = 'rm.person.search.wizard'
    _description = 'Find or Create Person - Ribbon Rack Order'

    deep_search = fields.Boolean(
        string='Deep Search',
        help='Off: one simple search box, checked against every field. '
             'On: search each field (Name/ID/Phone/Mobile/Email/Rank/'
             'Unit) independently.')
    search_term = fields.Char(string='Search')
    search_name = fields.Char(string='Search by Name')
    search_id_number = fields.Char(string='Search by ID Number')
    search_phone = fields.Char(string='Search by Phone')
    search_mobile = fields.Char(string='Search by Mobile')
    search_email = fields.Char(string='Search by Email')
    search_rank_id = fields.Many2one('rm.ranks', string='Search by Rank')
    search_unit_id = fields.Many2one('rm.unit', string='Search by Unit')
    result_person_ids = fields.Many2many(
        'res.person', string='Matches', compute='_compute_results')
    person_id = fields.Many2one(
        'res.person', string='Selected Person',
        help='Pick the matching person from the results above, or type '
             'a name/ID/phone/mobile/email directly into this field to '
             'search - or leave blank and use "No Match - Create New '
             'Person" instead.')

    @api.depends('deep_search', 'search_term', 'search_name', 'search_id_number',
                 'search_phone', 'search_mobile', 'search_email',
                 'search_rank_id', 'search_unit_id')
    def _compute_results(self):
        Person = self.env['res.person']
        for wizard in self:
            if wizard.deep_search:
                clauses = []
                if wizard.search_name:
                    clauses.append(('name', 'ilike', wizard.search_name))
                if wizard.search_id_number:
                    clauses.append(('id_number', 'ilike', wizard.search_id_number))
                if wizard.search_phone:
                    clauses.append(('phone', 'ilike', wizard.search_phone))
                if wizard.search_mobile:
                    clauses.append(('mobile', 'ilike', wizard.search_mobile))
                if wizard.search_email:
                    clauses.append(('email', 'ilike', wizard.search_email))
                if wizard.search_rank_id:
                    clauses.append(('rank_id', '=', wizard.search_rank_id.id))
                if wizard.search_unit_id:
                    clauses.append(('current_workplace', '=', wizard.search_unit_id.id))
            else:
                term = wizard.search_term
                clauses = [
                    ('name', 'ilike', term),
                    ('id_number', 'ilike', term),
                    ('phone', 'ilike', term),
                    ('mobile', 'ilike', term),
                    ('email', 'ilike', term),
                    ('rank_id.name', 'ilike', term),
                    ('current_workplace.name', 'ilike', term),
                ] if term else []
            if not clauses:
                wizard.result_person_ids = Person
                continue
            domain = ['|'] * (len(clauses) - 1) + clauses
            wizard.result_person_ids = Person.search(domain, limit=20)

    def action_create_new_person(self):
        """No match found - hand off to the standard blank Personnel
        form. Once saved there, come back to this wizard (or use the
        Decorations tab's own Issue/Build buttons directly) to place
        the order."""
        return {
            'type': 'ir.actions.act_window',
            'name': _('New Personnel'),
            'res_model': 'res.person',
            'view_mode': 'form',
            'target': 'current',
        }

    def action_confirm(self):
        """Create a Sale Order for the selected person with one Ribbon
        Rack line, priced at their current estimated rack price."""
        self.ensure_one()
        if not self.person_id:
            raise UserError(_('Select a person first (or create a new one).'))
        rack_tmpl = self.env.ref('ribbon_medal.product_ribbon_rack', raise_if_not_found=False)
        if not rack_tmpl:
            raise UserError(_('The "Ribbon Rack" product is not set up.'))
        order = self.env['sale.order'].create({
            'partner_id': self.person_id.partner_id.id,
            'person_id': self.person_id.id,
            'order_line': [(0, 0, {
                'product_id': rack_tmpl.product_variant_id.id,
                'product_uom_qty': 1,
                'price_unit': self.person_id.rack_total_price,
                'person_id': self.person_id.id,
                'name': _('%s\n(For: %s)') % (rack_tmpl.name, self.person_id.display_name),
            })],
        })
        return {
            'type': 'ir.actions.act_window',
            'name': _('Sale Order'),
            'res_model': 'sale.order',
            'view_mode': 'form',
            'res_id': order.id,
        }
