# -*- coding: utf-8 -*-
from odoo import fields, models


class RmComponentCategory(models.Model):
    """Classifies materials into categories so a set template can
    reference a category requirement (e.g. 'RIBBON', 'BACKING') instead
    of one specific fixed product - the actual product is then either
    fixed on the template rule (default_product_id) or picked by the
    user at BOM-generation time (see rm.set.template.component)."""
    _name = 'rm.component.category'
    _description = 'Component Category'
    _order = 'code'

    code = fields.Char(
        required=True, string='Category Code',
        help='e.g. RIBBON, GUM, BACKING, FASTENER, PACKAGING, ATTACHMENT')
    name = fields.Char(required=True, string='Display Name')

    _sql_constraints = [
        ('code_unique', 'unique(code)', 'A component category with this code already exists.'),
    ]

    def name_get(self):
        return [(rec.id, f'[{rec.code}] {rec.name}') for rec in self]
