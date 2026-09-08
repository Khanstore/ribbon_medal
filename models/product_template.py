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

    # Set (once, at creation) by rm.rack.product._ensure_product and
    # rm.medal.rack._ensure_product for the finished, top-level rack
    # assembly product they each manage - never by rm.rack.line /
    # rm.medal.part (the intermediate Line/Part component products) or
    # any other auto-managed product. Lets the Manufacturing Orders list
    # offer a "Racks Only" filter that shows just the finished-rack MOs,
    # not every Line/Part MO along the way.
    rm_is_finished_rack = fields.Boolean(
        default=False, copy=False,
        help='Technical flag: this product is a finished Rack/Medal Rack '
             "assembly (as opposed to one of its Line/Part components).")
