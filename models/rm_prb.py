# -*- coding: utf-8 -*-
from odoo import _, api, fields, models
from odoo.exceptions import ValidationError


class RmPrb(models.Model):
    _name = 'rm.prb'
    _description = 'Decoration (Ribbon / Medal)'
    _order = 'seniority_sequence desc, award_name'
    _rec_name = 'award_name'

    award_name = fields.Char(required=True, string='Award Name')
    starting_date = fields.Date(string='Starting Date')
    attachment_id = fields.Many2one('rm.attachment', string='Attachment')
    is_ribbon = fields.Boolean(string='Is Ribbon')
    is_medal = fields.Boolean(string='Is Medal')
    ribbon_image = fields.Binary(string='Ribbon Image', attachment=True)
    medal_image = fields.Binary(string='Medal Image', attachment=True)
    mission_name = fields.Char(string='Mission Name')
    active = fields.Boolean(default=True)

    force_id = fields.Many2one('rm.forces', string='Force', ondelete='restrict', index=True)
    rule_id = fields.Many2one(
        'rm.acquisition.rules', string='Acquisition Rule', ondelete='restrict')
    seniority_sequence = fields.Integer(
        default=0, required=True,
        help='Determines precedence in the Ribbon Rack display. Higher value '
             'means higher precedence and is placed closer to the bottom-right '
             'position of the rack.')

    person_ids = fields.Many2many(
        'res.person', 'rm_prb_res_person_rel', 'prb_id', 'person_id',
        string='Awarded To')
    person_count = fields.Integer(compute='_compute_person_count')

    _sql_constraints = [
        ('seniority_sequence_positive', 'CHECK(seniority_sequence >= 0)',
         'Seniority sequence must be a positive value.'),
    ]

    def _compute_person_count(self):
        for prb in self:
            prb.person_count = len(prb.person_ids)

    @api.constrains('is_ribbon', 'is_medal')
    def _check_award_type(self):
        for record in self:
            if not record.is_ribbon and not record.is_medal:
                raise ValidationError(
                    _('The award "%s" must be flagged as at least a Ribbon or a Medal.')
                    % record.award_name)
