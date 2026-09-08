# -*- coding: utf-8 -*-
from odoo import api, fields, models


class StockMove(models.Model):
    _inherit = 'stock.move'

    rm_rack_instance_name = fields.Char(
        compute='_compute_rm_rack_instance_name', string='Product',
        help="For a Rack/Medal Rack line, the specific manufactured "
             "instance behind it (e.g. 'Rack #6', 'Medal Rack #11') - "
             "since every such line sells the same generic product "
             "(Ribbon Rack / Tunic Medal Rack / Meskit Medal Rack), this "
             "is what actually distinguishes two different people's "
             "lines on the same delivery. Falls back to the move's own "
             "product name for every other, non-rack line, so this is "
             "safe to use as the Product column everywhere.")

    @api.depends(
        'product_id.display_name',
        'sale_line_id.rack_unit_id.rack_id.product_tmpl_id.name',
        'sale_line_id.tunic_medal_rack_unit_id.rack_id.product_tmpl_id.name',
        'sale_line_id.meskit_medal_rack_unit_id.rack_id.product_tmpl_id.name')
    def _compute_rm_rack_instance_name(self):
        for move in self:
            line = move.sale_line_id
            unit = line.rack_unit_id or line.tunic_medal_rack_unit_id or line.meskit_medal_rack_unit_id
            move.rm_rack_instance_name = (
                unit.rack_id.product_tmpl_id.name if unit else move.product_id.display_name)
