# -*- coding: utf-8 -*-
from odoo import _, api, fields, models
from odoo.exceptions import ValidationError


class RmPRB(models.Model):
    _name = 'rm.prb'
    _description = 'PRB of decorations'
    _order = 'seniority_sequence desc, name'

    name = fields.Char(required=True, string='PRB Name')
    medal_id = fields.Many2one('rm.decoration', string='Medal')
    ribbon_id = fields.Many2one('rm.decoration', string='Ribbon')
    seniority_sequence=fields.Integer("seniority")
    sequence = fields.Float(string='Sequence')
    starting_date = fields.Date(string='Starting Date')
    is_ribbon = fields.Boolean(string='Is Ribbon')
    is_medal = fields.Boolean(string='Is Medal')
    service_age=fields.Integer(string='Service Age')
    attachment_id = fields.Many2one('rm.attachment', string='Attachment')
    ribbon_image = fields.Binary(string='Ribbon Image', attachment=True)
    medal_image = fields.Binary(string='Medal Image', attachment=True)
    mission_name = fields.Char(string='Mission Name')
    active = fields.Boolean(default=True)

    force_id = fields.Many2one('rm.forces', string='Force', ondelete='restrict', index=True)
    rule_category_id = fields.Many2one(
        'rm.rules.category', string='Rules Category', ondelete='restrict')

    