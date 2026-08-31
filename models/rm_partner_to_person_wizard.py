# -*- coding: utf-8 -*-
from odoo import _, api, fields, models
from odoo.exceptions import UserError


class RmPartnerToPersonWizard(models.TransientModel):
    _name = 'rm.partner.to.person.wizard'
    _description = 'Convert Partners to Personnel Records'

    line_ids = fields.One2many(
        'rm.partner.to.person.wizard.line', 'wizard_id', string='Partners')
    convertible_count = fields.Integer(compute='_compute_counts')
    skipped_count = fields.Integer(compute='_compute_counts')

    @api.depends('line_ids.skip')
    def _compute_counts(self):
        for wizard in self:
            wizard.convertible_count = len(wizard.line_ids.filtered(lambda l: not l.skip))
            wizard.skipped_count = len(wizard.line_ids) - wizard.convertible_count

    @api.model
    def default_get(self, fields_list):
        vals = super().default_get(fields_list)
        partner_ids = self.env.context.get('active_ids') or []
        partners = self.env['res.partner'].browse(partner_ids)
        existing_person_by_partner = {
            p.partner_id.id: p for p in self.env['res.person'].search(
                [('partner_id', 'in', partner_ids)])
        }
        lines = []
        for partner in partners:
            existing = existing_person_by_partner.get(partner.id)
            is_company = partner.company_type == 'company'
            lines.append((0, 0, {
                'partner_id': partner.id,
                'existing_person_id': existing.id if existing else False,
                'is_company': is_company,
                'skip': bool(existing) or is_company,
            }))
        vals['line_ids'] = lines
        return vals

    def action_confirm(self):
        Person = self.env['res.person']
        to_create = self.line_ids.filtered(lambda l: not l.skip)
        already_have = Person.search([('partner_id', 'in', to_create.partner_id.ids)])
        if already_have:
            raise UserError(_(
                'These already have a Person record - tick Skip for them '
                '(or open their existing Person record instead): %s'
            ) % ', '.join(already_have.mapped('partner_id.display_name')))
        created = Person
        for line in to_create:
            created |= Person.create({
                'partner_id': line.partner_id.id,
                'id_number': line.id_number or False,
                'rank_id': line.rank_id.id if line.rank_id else False,
            })
        if not created:
            return {'type': 'ir.actions.act_window_close'}
        return {
            'type': 'ir.actions.act_window',
            'name': _('Converted Personnel'),
            'res_model': 'res.person',
            'view_mode': 'list,form',
            'domain': [('id', 'in', created.ids)],
        }


class RmPartnerToPersonWizardLine(models.TransientModel):
    _name = 'rm.partner.to.person.wizard.line'
    _description = 'Convert Partners to Personnel Records - Line'

    wizard_id = fields.Many2one('rm.partner.to.person.wizard', required=True, ondelete='cascade')
    partner_id = fields.Many2one('res.partner', required=True, readonly=True)
    is_company = fields.Boolean(readonly=True)
    existing_person_id = fields.Many2one('res.person', readonly=True)
    skip = fields.Boolean(
        default=False,
        help='Ticked automatically for partners that are already a '
             'Person, or are a Company rather than an individual - '
             'untick only if you\'re sure. You can also tick this '
             "yourself to skip any other partner in this batch.")
    id_number = fields.Char(string='ID Number')
    rank_id = fields.Many2one('rm.ranks', string='Rank')
