# -*- coding: utf-8 -*-
from odoo import models


class StockPicking(models.Model):
    _inherit = 'stock.picking'

    def _rm_related_productions(self):
        """Every top-level Rack/Medal Rack MO tied to this delivery's
        sale order - one per rack-type line, via that line's own
        specific unit's mrp_production_id (rack_unit_id /
        tunic_medal_rack_unit_id / meskit_medal_rack_unit_id) - that
        isn't done or cancelled yet.

        Only the TOP-level MO is needed here: producing it runs the
        existing cascading Produce All (see
        mrp.production.button_mark_done), which already pulls in its
        own supporting Rack Line / Medal Part MO first on its own."""
        self.ensure_one()
        order = self.sale_id
        if not order:
            return self.env['mrp.production']
        productions = self.env['mrp.production']
        for line in order.order_line:
            unit = line.rack_unit_id or line.tunic_medal_rack_unit_id or line.meskit_medal_rack_unit_id
            if unit and unit.mrp_production_id:
                productions |= unit.mrp_production_id
        return productions.filtered(lambda p: p.state not in ('done', 'cancel'))

    def button_validate(self):
        """Before this delivery actually validates, produce every
        rack/medal-rack MO tied to its sale order that isn't done yet -
        otherwise "delivering" it would just be moving a paper
        quantity that was never physically manufactured. Runs before
        super() on purpose: button_validate checks stock availability,
        which needs the goods to exist first.

        Producing an MO puts the finished good into stock, but doesn't
        by itself reserve this delivery's own moves against it - that
        still needs a fresh action_assign() (the same thing "Check
        Availability" does) run afterward, or button_validate's own
        "no quantities are reserved nor done" check still fails even
        though the stock now genuinely exists. Calling it unconditionally
        here is safe - action_assign() is a normal, idempotent no-op on
        a picking that's already ready or has nothing to do with any of
        this."""
        for picking in self:
            for production in picking._rm_related_productions():
                production.button_mark_done()
        self.action_assign()
        return super().button_validate()
