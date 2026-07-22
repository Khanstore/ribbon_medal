# -*- coding: utf-8 -*-
from odoo import _, api, fields, models
from odoo.exceptions import ValidationError


class RmDecoration(models.Model):
    _name = 'rm.decoration'
    _description = 'Decoration (Ribbon / Medal)'
    _order = 'decoration_name'
    _rec_name = 'decoration_name'

    decoration_name = fields.Char(required=True, string='Award Name')
    attachment_id = fields.Many2one('rm.attachment', string='Attachment')
    is_ribbon = fields.Boolean(string='Is Ribbon')
    is_medal = fields.Boolean(string='Is Medal')
    ribbon_image = fields.Binary(string='Ribbon Image', attachment=True)
    medal_image = fields.Binary(string='Medal Image', attachment=True)
    mission_name = fields.Char(string='Mission Name')
    active = fields.Boolean(default=True)

    @api.constrains('is_ribbon', 'is_medal')
    def _check_award_type(self):
        for record in self:
            if not record.is_ribbon and not record.is_medal:
                raise ValidationError(
                    _('The award "%s" must be flagged as at least a Ribbon or a Medal.')
                    % record.decoration_name)
