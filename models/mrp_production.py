# -*- coding: utf-8 -*-
# -*- coding: utf-8 -*-
from odoo import fields, models

# A production is only safe to fold extra quantity into while it's still
# purely "pending" - confirmed but nothing has actually been consumed or
# produced against it yet. Once it's in progress, leave it alone and raise
# a separate MO instead.
RM_PENDING_STATE = 'confirmed'


class MrpProduction(models.Model):
    _inherit = 'mrp.production'

    rm_set_order_id = fields.Many2one(
        'rm.set.order', string='Ribbon Rack Set Order', ondelete='set null', copy=False, index=True)

    def _rm_pending_child_productions(self):
        """Not-yet-done MOs whose finished-product move directly feeds
        one of this MO's raw-material moves - i.e. the Rack Line /
        Medal Part sub-assembly MOs Odoo's own multi-level
        manufacturing already links here via the standard stock-move
        chain (move_raw_ids -> move_orig_ids -> production_id); this
        doesn't invent any new relationship, it just reads that one."""
        self.ensure_one()
        return self.move_raw_ids.move_orig_ids.production_id.filtered(
            lambda p: p.id != self.id and p.state not in ('done', 'cancel'))

    def button_mark_done(self):
        """Transparently cascades: before the standard "Produce All"
        goes through for any of these MOs, first (recursively) produce
        any not-yet-done MO supplying its components - a Rack Line /
        Medal Part sub-assembly - deepest dependency first. So clicking
        the ordinary "Produce All" on a top-level Rack/Medal Rack MO
        also produces every MO feeding it, in one click, without a
        separate button. Calling child.button_mark_done() here (this
        same override) is what makes it recurse through more than one
        level deep, not just the immediate children."""
        for production in self:
            if production.state in ('done', 'cancel'):
                continue
            for child in production._rm_pending_child_productions():
                if child.state not in ('done', 'cancel'):
                    child.button_mark_done()
        remaining = self.filtered(lambda p: p.state not in ('done', 'cancel'))
        if not remaining:
            return True
        return super(MrpProduction, remaining).button_mark_done()

    def rm_add_quantity(self, additional_qty, extra_origin=None):
        """Fold `additional_qty` more units into this still-pending MO
        instead of a new one being raised for the same need: bumps
        `product_qty` and rescales the not-yet-processed raw material
        moves off their originating BOM line (so component demand stays
        correct), and appends `extra_origin` to the Source/origin field
        if it isn't already represented there."""
        self.ensure_one()
        if additional_qty <= 0:
            return self
        new_qty = (self.product_qty or 0.0) + additional_qty
        old_qty = self.product_qty or 1.0
        bom = self.bom_id
        open_moves = self.move_raw_ids.filtered(lambda m: m.state not in ('done', 'cancel'))
        for move in open_moves:
            bom_line = move.bom_line_id
            if bom_line and bom and bom.product_qty:
                move.product_uom_qty = bom_line.product_qty * new_qty / bom.product_qty
            else:
                move.product_uom_qty = move.product_uom_qty * new_qty / old_qty
        self.product_qty = new_qty
        if extra_origin:
            parts = [p.strip() for p in (self.origin or '').split(' + ') if p.strip()]
            if extra_origin not in parts:
                parts.append(extra_origin)
                self.origin = ' + '.join(parts)
        return self
