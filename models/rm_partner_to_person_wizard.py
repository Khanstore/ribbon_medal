# -*- coding: utf-8 -*-
from odoo import _, api, fields, models
from odoo.exceptions import UserError


class RmPartnerToPersonWizard(models.TransientModel):
    """Bulk-mark selected Contacts as Personnel.

    Under the earlier res.person model (delegation inheritance to a
    separate table), "converting" a Contact meant creating a brand-new
    Person record pointing at it. Now that Personnel is just
    is_person=True directly on res.partner, this wizard's job is much
    simpler: for each selected Contact not already Personnel (and not a
    Company), tick is_person and fill in ID Number/Rank.
    """
    _name = 'rm.partner.to.person.wizard'
    _description = 'Mark Contacts as Personnel'

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
        lines = []
        for partner in partners:
            is_company = partner.company_type == 'company'
            lines.append((0, 0, {
                'partner_id': partner.id,
                'already_person': partner.is_person,
                'is_company': is_company,
                'skip': partner.is_person or is_company,
            }))
        vals['line_ids'] = lines
        return vals

    def action_confirm(self):
        to_convert = self.line_ids.filtered(lambda l: not l.skip)
        already_have = to_convert.filtered('already_person')
        if already_have:
            raise UserError(_(
                'These are already Personnel - tick Skip for them instead: %s'
            ) % ', '.join(already_have.mapped('partner_id.display_name')))
        converted = self.env['res.partner']
        for line in to_convert:
            line.partner_id.write({
                'is_person': True,
                'id_number': line.id_number or False,
                'rank_id': line.rank_id.id if line.rank_id else False,
            })
            converted |= line.partner_id
        if not converted:
            return {'type': 'ir.actions.act_window_close'}
        return {
            'type': 'ir.actions.act_window',
            'name': _('Converted Personnel'),
            'res_model': 'res.partner',
            'view_mode': 'list,form',
            'domain': [('id', 'in', converted.ids)],
        }


class RmPartnerToPersonWizardLine(models.TransientModel):
    _name = 'rm.partner.to.person.wizard.line'
    _description = 'Mark Contacts as Personnel - Line'

    wizard_id = fields.Many2one('rm.partner.to.person.wizard', required=True, ondelete='cascade')
    partner_id = fields.Many2one('res.partner', required=True, readonly=True)
    is_company = fields.Boolean(readonly=True)
    already_person = fields.Boolean(readonly=True)
    skip = fields.Boolean(
        default=False,
        help='Ticked automatically for partners that are already '
             'Personnel, or are a Company rather than an individual - '
             'untick only if you\'re sure. You can also tick this '
             "yourself to skip any other partner in this batch.")
    id_number = fields.Char(string='ID Number')
    rank_id = fields.Many2one('rm.ranks', string='Rank')
