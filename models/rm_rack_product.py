# -*- coding: utf-8 -*-
from odoo import _, api, fields, models
from odoo.exceptions import UserError


class RmRackProduct(models.Model):
    """A Rack Product = one specific, ordered combination of Lines (rows).
    Identity is LOCKED PERMANENTLY the moment it's first created - later
    changes to any rm.prb's `sequence` never reshuffle or invalidate an
    existing Rack Product, even if the "correct" row order for a fresh
    combination would now come out differently.

    Unlike Lines, matching against existing Rack stock is exact-identity
    only - no trimming/substitution at this level (a partial-rack "trim"
    would mean dropping a whole row, which changes who the rack even
    fits). All the flexibility lives at the Line tier.

    Stock units (rm.rack.unit) carry an optional reserved_person_id:
    empty = general stock, available to anyone; set = this unit was
    manufactured specifically because that person needed one, and stays
    locked to them until delivered (or their order is cancelled, which
    releases it back to general stock).
    """
    _name = 'rm.rack.product'
    _inherit = ['rm.product.sync.mixin', 'rm.rack.image.mixin']
    _description = 'Rack Product (locked-identity combination of Lines)'
    _order = 'id'

    name = fields.Char(
        string='Alias',
        help='Optional human-friendly name. The underlying identity '
             '(its exact row sequence) is locked and never changes, '
             'regardless of this alias.')
    identity_key = fields.Char(index=True, readonly=True, copy=False)
    display_identity = fields.Char(
        compute='_compute_display_identity', store=True, string='Rows')
    rack_line_ids = fields.One2many(
        'rm.rack.product.line', 'rack_id', string='Rows', readonly=True)
    product_id = fields.Many2one(
        'product.product', readonly=True, copy=False,
        help="This Rack's own variant of the shared 'Ribbon Rack' "
             "product.template - see _ensure_product below.")
    product_label = fields.Char(
        readonly=True, copy=False,
        help='This Rack\'s own short label (e.g. "Rack #6") - kept as '
             "a plain field since, unlike before, the product's own "
             "template name is now shared across every Rack (it no "
             "longer distinguishes this one) - used as the sale/"
             "delivery/MO product's own name (product_id.name), so all "
             "three naturally show the same specific label.")
    bom_id = fields.Many2one('mrp.bom', readonly=True, copy=False)
    use_count = fields.Integer(default=0, readonly=True)
    last_used_date = fields.Datetime(readonly=True)
    unit_ids = fields.One2many('rm.rack.unit', 'rack_id', string='Units')
    stock_count = fields.Integer(compute='_compute_stock_counts', string='In Stock')
    available_stock_count = fields.Integer(
        compute='_compute_stock_counts', string='Unreserved In Stock')

    _sql_constraints = [
        ('identity_key_unique', 'unique(identity_key)',
         'A Rack Product with this exact row sequence already exists.'),
    ]

    @api.depends('rack_line_ids.sequence', 'rack_line_ids.line_id.display_identity')
    def _compute_display_identity(self):
        for rack in self:
            rack.display_identity = ' | '.join(
                rack.rack_line_ids.sorted('sequence').mapped('line_id.display_identity'))

    def _compute_stock_counts(self):
        for rack in self:
            units = self.env['rm.rack.unit'].search(
                [('rack_id', '=', rack.id), ('state', '=', 'in_stock')])
            rack.stock_count = len(units)
            rack.available_stock_count = len(units.filtered(lambda u: not u.reserved_person_id))

    @api.model
    def _key_for_line_ids(self, line_ids):
        return '-'.join(str(i) for i in line_ids)

    @api.model
    def get_or_create(self, line_ids):
        """line_ids: ordered list of rm.rack.line ids (top row first).
        Returns the rm.rack.product for that EXACT row sequence,
        creating it (identity locked from this point on) if new."""
        line_ids = list(line_ids)
        key = self._key_for_line_ids(line_ids)
        rack = self.search([('identity_key', '=', key)], limit=1)
        if rack:
            return rack
        return self.create({
            'identity_key': key,
            'rack_line_ids': [(0, 0, {'sequence': idx, 'line_id': lid})
                              for idx, lid in enumerate(line_ids)],
        })

    def _ensure_product(self):
        self.ensure_one()
        if not self.product_id:
            label = self.name or f'Rack #{self.id}'
            variant = self._ensure_rm_variant(
                'Ribbon Rack', 'Ribbon Rack Combination', label,
                extra_template_vals={'rm_is_finished_rack': True})
            self.write({'product_id': variant.id, 'product_label': label})
        self._generate_rack_image()

    # Must match static/src/scss/ribbon_rack.scss's .o_ribbon_rack_cell
    # (108x39px) and background (#e9e9e9) exactly.
    _RIBBON_CELL_W, _RIBBON_CELL_H = 108, 39
    _RIBBON_BG = (233, 233, 233, 255)

    def _get_own_rows(self):
        """This Rack's own rows, top row first, each already in
        left-to-right rendering order - reconstructed from this
        record's own rack_line_ids/item_ids, mirroring
        res.partner._get_rack_rows()'s shape exactly, but from this
        Rack's fixed, own composition rather than a person's live,
        changing acquisitions."""
        self.ensure_one()
        return [prod_line.line_id.item_ids.sorted('sequence').mapped('award_id')
                for prod_line in self.rack_line_ids.sorted('sequence')]

    def _generate_rack_image(self):
        """(Re)generate this Rack's own product image - a real, stored
        picture matching the Ribbon Rack widget's own layout (see
        rm.rack.image.mixin) - set on the underlying variant
        (image_variant_1920), not the shared template. Safe/cheap to
        call repeatedly; does nothing if Pillow isn't available, there
        are no rows to draw, or the product isn't resolved yet."""
        self.ensure_one()
        if not self.product_id or not self._rm_pil_available():
            return
        rows = self._get_own_rows()
        if not rows:
            return
        n_cols = max(len(row) for row in rows)
        canvas = self._rm_new_canvas(
            n_cols * self._RIBBON_CELL_W, len(rows) * self._RIBBON_CELL_H, self._RIBBON_BG)
        for row_idx, row in enumerate(rows):
            x_offset = (canvas.width - len(row) * self._RIBBON_CELL_W) // 2
            top = row_idx * self._RIBBON_CELL_H
            for col_idx, prb in enumerate(row):
                left = x_offset + col_idx * self._RIBBON_CELL_W
                self._rm_paste_cell(
                    canvas,
                    prb.ribbon_id.ribbon_product_tmpl_id.image_1920,
                    prb.attachment_id.image,
                    (left, top, self._RIBBON_CELL_W, self._RIBBON_CELL_H))
        self.product_id.image_variant_1920 = self._rm_finalize_image(canvas, flatten=True)

    def _build_bom(self):
        """N x Line products (one per row, each ensured to have its own
        product+BOM first) + this template's per_rack fixed rules
        (fastener, packaging, ...)."""
        self.ensure_one()
        self._ensure_product()
        template = self.env['rm.set.template'].search([('category', '=', 'ribbon_rack')], limit=1)
        if not template:
            raise UserError(_('No "Ribbon Rack" Set Template is configured.'))

        totals = {}
        missing = []

        def add(product, qty, uom):
            if not product:
                return
            key = (product.id, uom.id)
            totals[key] = totals.get(key, 0.0) + qty

        for prod_line in self.rack_line_ids.sorted('sequence'):
            line = prod_line.line_id
            line._ensure_product_and_bom()
            variant = line.product_id
            add(variant, 1.0, line.product_id.uom_id)

        for rule in template.component_rule_ids.filtered(lambda r: r.scope == 'per_rack'):
            product = rule.default_product_id.product_variant_id
            if not product:
                missing.append(_('Default product for category "%s"') % rule.category_id.name)
                continue
            add(product, rule.quantity, rule.uom_id or product.uom_id)

        if missing:
            raise UserError(_('Missing product selection(s):\n- %s') % '\n- '.join(missing))

        bom = self.env['mrp.bom'].create({
            'product_tmpl_id': self.product_id.product_tmpl_id.id,
            'product_id': self.product_id.id,
            'product_qty': 1.0,
            'type': 'normal',
            'code': f'RACK-{self.id}',
            'bom_line_ids': [(0, 0, {
                'product_id': pid, 'product_qty': qty, 'product_uom_id': uid,
            }) for (pid, uid), qty in totals.items()],
        })
        self.bom_id = bom.id
        return bom

    def get_available_stock_quantity(self):
        """Return the actual available stock quantity of this rack's product.
        Checks the product's stock availability in all warehouses/locations."""
        self.ensure_one()
        if not self.product_id:
            return 0.0

        # Get available stock
        return self.product_id.qty_available

    def get_stock_units(self, quantity):
        """Get actual stock units (rm.rack.unit records) for this rack.
        Returns the specified quantity of in-stock units, or fewer if not enough."""
        self.ensure_one()
        # First check if we have enough actual product stock
        available_qty = self.get_available_stock_quantity()
        if available_qty < quantity:
            # We don't have enough physical stock, return what's available
            quantity = int(available_qty)

        if quantity <= 0:
            return self.env['rm.rack.unit']

        # Get the rack units that are in stock and not reserved
        return self.env['rm.rack.unit'].search([
            ('rack_id', '=', self.id),
            ('state', '=', 'in_stock'),
            ('reserved_person_id', '=', False)
        ], limit=int(quantity))

    def manufacture_units(self, quantity, reserved_person_id=False, component_productions=None):
        """Manufacture `quantity` units of this rack. Returns list of created units."""
        self.ensure_one()
        created_units = self.env['rm.rack.unit']
        for _ in range(int(quantity)):
            unit = self.manufacture_unit(
                reserved_person_id=reserved_person_id, component_productions=component_productions)
            created_units |= unit
        return created_units

    def record_usage(self):
        for rack in self:
            rack.write({'use_count': rack.use_count + 1, 'last_used_date': fields.Datetime.now()})

    def manufacture_unit(self, reserved_person_id=False, component_productions=None):
        """Add 1 unit of demand for this Rack to manufacturing. If an MO
        for this exact Rack's product/BOM is already pending (confirmed,
        nothing consumed yet), the unit is folded into it - quantity and
        origin merged onto the existing MO - rather than raising a new
        one. Only when no pending MO exists is a new mrp.production
        created+confirmed. Returns the resulting rm.rack.unit. Same
        MO-confirm-means-in_stock simplification as
        rm.rack.line.manufacture_unit - see there.

        component_productions: any Rack Line MO(s) just created to
        supply this same build - linked onto this MO's own matching
        raw-material move (see _rm_link_component_productions) so the
        existing cascading "Produce All" actually finds and produces
        them first. Linked whether this call reuses a pending MO or
        creates a fresh one, since either way that MO's Line-consuming
        move needs the link to cascade correctly."""
        self.ensure_one()
        if not self.bom_id:
            self._build_bom()
        product = self.product_id
        Production = self.env['mrp.production']
        pending = Production.search([
            ('product_id', '=', product.id),
            ('bom_id', '=', self.bom_id.id),
            ('state', '=', 'confirmed'),
        ], order='id', limit=1)
        if pending:
            production = pending.rm_add_quantity(1.0, extra_origin=self.display_identity)
        else:
            production = Production.create({
                'product_id': product.id,
                'product_qty': 1.0,
                'product_uom_id': self.product_id.uom_id.id,
                'bom_id': self.bom_id.id,
                'origin': self.display_identity,
            })
            production.action_confirm()
        if component_productions:
            self._rm_link_component_productions(production, component_productions)
        return self.env['rm.rack.unit'].create({
            'rack_id': self.id,
            'state': 'in_stock',
            'reserved_person_id': reserved_person_id,
            'mrp_production_id': production.id,
        })


class RmRackProductLine(models.Model):
    _name = 'rm.rack.product.line'
    _description = 'Rack Product - Row in Sequence'
    _order = 'rack_id, sequence'

    rack_id = fields.Many2one('rm.rack.product', required=True, ondelete='cascade')
    sequence = fields.Integer(default=10)
    line_id = fields.Many2one('rm.rack.line', required=True, string='Line (Row)')


class RmRackUnit(models.Model):
    _name = 'rm.rack.unit'
    _description = 'Rack Product - Stock Unit'
    _order = 'id'

    rack_id = fields.Many2one('rm.rack.product', required=True, ondelete='cascade')
    state = fields.Selection(
        [('in_stock', 'In Stock'), ('delivered', 'Delivered')], default='in_stock', required=True)
    reserved_person_id = fields.Many2one(
        'res.partner', string='Reserved For', domain=[('is_person', '=', True)],
        help='Set only when this unit was manufactured specifically '
             'because this person needed one - it stays locked to them '
             'until delivered. Empty = general stock, available to '
             'anyone with a matching need.')
    mrp_production_id = fields.Many2one('mrp.production', readonly=True)
    mo_state = fields.Selection(related='mrp_production_id.state', string='MO Status')
    delivered_to_person_id = fields.Many2one(
        'res.partner', readonly=True, domain=[('is_person', '=', True)])
    delivery_date = fields.Datetime(readonly=True)

    def action_deliver(self, person_id=None):
        self.ensure_one()
        target = person_id or (self.reserved_person_id.id if self.reserved_person_id else False)
        if not target:
            raise UserError(_('No person specified to deliver this rack to.'))
        self.write({
            'state': 'delivered',
            'delivered_to_person_id': target,
            'delivery_date': fields.Datetime.now(),
        })

    def action_release_reservation(self):
        """Call when a person's order is cancelled - the unit falls back
        into general (unreserved) stock automatically."""
        self.write({'reserved_person_id': False})