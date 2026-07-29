# -*- coding: utf-8 -*-
from odoo import fields, models


class RmUnitCategory(models.Model):
    _name = 'rm.unit.category'
    _description = 'Unit Category / Level'
    _order = 'name'
    name = fields.Char(string='Category Name', required=True)
    force_id = fields.Many2one('rm.forces', string='Force', ondelete='restrict', index=True)
    parent_id = fields.Many2one('rm.unit.category', string='Parent', ondelete='restrict', index=True)
    level=fields.Integer(string='Level', required=True)
    chief_id = fields.Many2one(
        'rm.ranks', string='Chief', ondelete='restrict',
        help='Rank required to serve as chief/commanding officer of units '
             'under this category. Personnel can only be posted to a unit '
             'of this category if their own rank seniority does not exceed '
             "the chief's rank seniority.")
    active = fields.Boolean(default=True)
