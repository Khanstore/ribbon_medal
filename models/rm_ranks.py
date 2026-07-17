# -*- coding: utf-8 -*-
from odoo import _, fields, models


class RmRanks(models.Model):
    _name = 'rm.ranks'
    _description = 'Personnel Rank'
    _order = 'force_id, seniority_level desc, name'

    name = fields.Char(required=True)
    code = fields.Char(string='Rank Code')
    force_id = fields.Many2one(
        'rm.forces', string='Force', required=True, ondelete='restrict', index=True)
    seniority_level = fields.Integer(
        default=0, help='Higher value indicates a more senior rank.')
    active = fields.Boolean(default=True)

    person_ids = fields.One2many('res.person', 'rank_id', string='Personnel')
    person_count = fields.Integer(compute='_compute_person_count')

    _sql_constraints = [
        ('code_force_uniq', 'unique(code, force_id)',
         'Rank code must be unique within a force.'),
    ]

    def _compute_person_count(self):
        for rank in self:
            rank.person_count = len(rank.person_ids)

    def _compute_display_name(self):
        for rank in self:
            if rank.force_id:
                rank.display_name = '%s / %s' % (rank.force_id.name, rank.name)
            else:
                rank.display_name = rank.name

    def copy(self, default=None):
        default = dict(default or {})
        default.setdefault('name', _('%s (copy)') % self.name)
        # code is unique per force; clear it so the duplicate doesn't
        # collide with the original and trigger the SQL constraint.
        default.setdefault('code', False)
        return super().copy(default)
