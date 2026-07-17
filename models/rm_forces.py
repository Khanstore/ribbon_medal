# -*- coding: utf-8 -*-
from odoo import _, fields, models


class RmForces(models.Model):
    _name = 'rm.forces'
    _description = 'Force / Branch of Service'
    _order = 'name'

    name = fields.Char(required=True)
    description = fields.Text()
    logo = fields.Binary(attachment=True)
    active = fields.Boolean(default=True)

    rank_ids = fields.One2many('rm.ranks', 'force_id', string='Ranks')
    prb_ids = fields.One2many('rm.prb', 'force_id', string='Decorations')
    unit_ids = fields.One2many('rm.unit', 'force_id', string='Units')
    rank_count = fields.Integer(compute='_compute_rank_count')
    prb_count = fields.Integer(compute='_compute_prb_count')
    unit_count = fields.Integer(compute='_compute_unit_count')

    _sql_constraints = [
        ('name_uniq', 'unique(name)', 'A force with this name already exists.'),
    ]

    def _compute_rank_count(self):
        for force in self:
            force.rank_count = len(force.rank_ids)

    def _compute_prb_count(self):
        for force in self:
            force.prb_count = len(force.prb_ids)

    def _compute_unit_count(self):
        for force in self:
            force.unit_count = len(force.unit_ids)

    def action_view_units(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': 'Units',
            'res_model': 'rm.unit',
            'view_mode': 'list,form',
            'domain': [('force_id', '=', self.id)],
            'context': {'default_force_id': self.id},
        }

    def copy(self, default=None):
        default = dict(default or {})
        default.setdefault('name', _('%s (copy)') % self.name)
        return super().copy(default)
