# -*- coding: utf-8 -*-
from odoo import fields, models


class RmUnit(models.Model):
    _name = 'rm.unit'
    _description = 'Unit'
    _order = 'name'

    name = fields.Char(required=True)
    parent_id = fields.Many2one('rm.unit', string='Parent')
    force_id = fields.Many2one('rm.forces', string='Force', ondelete='restrict', index=True)
    # level_id = fields.Many2one(
    #     'rm.unit.category', string='Level', ondelete='restrict',
    #     help='Category/level of this unit, which determines the rank '
    #          'required of its chief.')
    level = fields.Integer(string='Level',related='chief_id.seniority_level')
    chief_id = fields.Many2one(
        'rm.ranks', string='Chief Rank')
    active = fields.Boolean(default=True)

    person_ids = fields.One2many('res.person', 'current_workplace', string='Personnel')
    person_count = fields.Integer(compute='_compute_person_count')

    def _compute_person_count(self):
        for unit in self:
            unit.person_count = len(unit.person_ids)

    def action_view_personnel(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': 'Personnel',
            'res_model': 'res.person',
            'view_mode': 'list,kanban,form',
            'domain': [('current_workplace', '=', self.id)],
            'context': {'default_current_workplace': self.id},
        }
