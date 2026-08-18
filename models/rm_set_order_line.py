# -*- coding: utf-8 -*-
from odoo import fields, models


class RmSetOrderLine(models.Model):
    """Per-cell (or per-rack) product selection captured on a
    rm.set.order, for template component rules that are user-selected
    but aren't already resolvable from existing acquisition data.

    RIBBON and ATTACHMENT resolve automatically - the ribbon is the
    cell's own award product, the attachment is the acquisition's own
    attachment_id (see rm.set.order._resolve_rule_product). Anything
    else marked "User Picks Product" (e.g. BACKING: Rexine vs Velcro)
    has no existing field to resolve from, so it needs an explicit
    choice captured here before a BOM can be generated.

    `award_id` (not the acquisition ledger row itself) identifies the
    cell, since rm.acquisition is a SQL view whose row ids aren't stable
    identity across recomputation - award_id is a real, stable
    rm.prb id. Left empty for a per_rack selection (applies once, not
    tied to any one cell)."""
    _name = 'rm.set.order.line'
    _description = 'Ribbon Rack Set Order - Per-Cell Component Selection'
    _order = 'order_id, award_id, category_id'

    order_id = fields.Many2one('rm.set.order', required=True, ondelete='cascade')
    award_id = fields.Many2one(
        'rm.prb', string='Cell (Award)',
        help='The specific award/cell this selection applies to. Empty '
             'for a Per Rack selection.')
    category_id = fields.Many2one('rm.component.category', required=True)
    product_id = fields.Many2one('product.product', string='Selected Product')

    _sql_constraints = [
        ('order_award_category_unique', 'unique(order_id, award_id, category_id)',
         'Only one selection per order/cell/category is allowed.'),
    ]
