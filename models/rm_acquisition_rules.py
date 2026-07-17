# -*- coding: utf-8 -*-
from odoo import fields, models


class RmAcquisitionRules(models.Model):
    _name = 'rm.acquisition.rules'
    _description = 'Award Acquisition Rule'
    _order = 'name'

    name = fields.Selection([
        ('batch', 'Batch'),
        ('missions', 'Missions'),
        ('special', 'Special'),
        ('extensions', 'Extensions'),
        ('seniority', 'Seniority'),
    ], required=True, string='Rule Type')
    details = fields.Text()
    active = fields.Boolean(default=True)

    prb_ids = fields.One2many('rm.prb', 'rule_id', string='Decorations')
    prb_count = fields.Integer(compute='_compute_prb_count')

    def _compute_prb_count(self):
        for rule in self:
            rule.prb_count = len(rule.prb_ids)

    def _compute_display_name(self):
        selection_labels = dict(self._fields['name'].selection)
        for rule in self:
            rule.display_name = selection_labels.get(rule.name, rule.name or '')
