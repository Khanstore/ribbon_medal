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

    # unit_ids = fields.One2many('rm.unit', 'level_id', string='Units')
    # unit_count = fields.Integer(compute='_compute_unit_count')

    def _compute_unit_count(self):
        for category in self:
            category.unit_count = len(category.unit_ids)

    def action_view_units(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': 'Units',
            'res_model': 'rm.unit',
            'view_mode': 'list,form',
            'domain': [('level_id', '=', self.id)],
            'context': {'default_level_id': self.id, 'default_force_id': self.force_id.id},
        }
