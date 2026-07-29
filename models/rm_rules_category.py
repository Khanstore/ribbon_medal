# -*- coding: utf-8 -*-
from odoo import fields, models


class RmAcquisitionRules(models.Model):
    _name = 'rm.rules.category'
    _description = 'Award Acquisition Rule Category'
    _order = 'name'

    name = fields.Selection([
        ('batch', 'Batch'),
        ('missions', 'Missions'),
        ('special', 'Special'),
        ('seniority', 'Seniority'),
    ], required=True, string='Rule Category')
    details = fields.Text()
    active = fields.Boolean(default=True)

    prb_ids = fields.One2many('rm.prb', 'rule_category_id', string='PRB')
    decoration_count = fields.Integer("Decoration Count", compute='_compute_prb_count')

    def _compute_prb_count(self):
        for category in self:
            category.decoration_count = len(category.prb_ids)

    def _compute_display_name(self):
        selection_labels = dict(self._fields['name'].selection)
        for category in self:
            category.display_name = selection_labels.get(category.name, category.name or '')
