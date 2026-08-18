# -*- coding: utf-8 -*-
from odoo import fields, models


class MrpProduction(models.Model):
    _inherit = 'mrp.production'

    rm_set_order_id = fields.Many2one(
        'rm.set.order', string='Ribbon Rack Set Order', ondelete='set null', copy=False, index=True)
