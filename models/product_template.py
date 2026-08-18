# -*- coding: utf-8 -*-
from odoo import fields, models


class ProductTemplate(models.Model):
    _inherit = 'product.template'

    # 'tracking' is defined by the stock module as a required (NOT NULL)
    # field with no default of its own. Redeclaring it here just to add a
    # default means every new product template - including the
    # ribbon/medal ones rm.decoration auto-creates - always gets a valid
    # value, instead of relying on whichever code happens to create it to
    # remember to pass one explicitly.
    tracking = fields.Selection(default='none')
