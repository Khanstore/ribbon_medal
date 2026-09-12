# -*- coding: utf-8 -*-
from odoo import _, api, fields, models
from odoo.exceptions import UserError

from .rm_medal_part import MEDAL_SIZE_SELECTION


class RmMedalRack(models.Model):
    """A Medal Rack (Tunic = size L, Meskit = size S): the finished
    product for one specific Medal Part (a person's whole
    medal-eligible award combination, already mounted on ribbon), with
    the awards' own Medals combined in, plus the fixed
    backing/fastener/packaging.

    There is exactly one Medal Rack per (Medal Part, size) - `part_id`
    IS this Rack's identity, so `identity_key` is simply copied from
    the Part it wraps. Two people who share the exact same
    medal-eligible combination and size share the same Part AND the
    same Rack, the same stock-reuse guarantee `rm.rack.product` gives
    Ribbon Racks.
    """
    _name = 'rm.medal.rack'
    _inherit = ['rm.product.sync.mixin', 'rm.rack.image.mixin']
    _description = 'Medal Rack (Tunic/Meskit - finished rack for one Medal Part)'
    _order = 'id'

    identity_key = fields.Char(index=True, readonly=True, copy=False)
    size = fields.Selection(MEDAL_SIZE_SELECTION, required=True, readonly=True)
    part_id = fields.Many2one(
        'rm.medal.part', required=True, readonly=True, string='Medal Part')
    display_identity = fields.Char(
        related='part_id.display_identity', store=True, string='Medals')
    part_award_ids = fields.One2many(
        related='part_id.award_ids', string='Award Sequence', readonly=True)
    product_id = fields.Many2one(
        'product.product', readonly=True, copy=False,
        help="This Rack's own variant of the shared 'Medal Rack' "
             "product.template - see _ensure_product below.")
    product_label = fields.Char(
        readonly=True, copy=False,
        help='This Rack\'s own short label (e.g. "Medal Rack #6") - kept '
             "as a plain field for reference on this record's own form, "
             "since the underlying product's own name is now shared "
             "across every Medal Rack (it no longer distinguishes this "
             "one) - the actual product shown to users elsewhere "
             "(sale order lines, deliveries, MOs) is product_id itself, "
             "which is what actually carries the specific variant now.")
    bom_id = fields.Many2one('mrp.bom', readonly=True, copy=False)
    use_count = fields.Integer(default=0, readonly=True)
    last_used_date = fields.Datetime(readonly=True)
    unit_ids = fields.One2many('rm.medal.rack.unit', 'rack_id', string='Units')
    stock_count = fields.Integer(compute='_compute_stock_counts', string='In Stock')
    available_stock_count = fields.Integer(
        compute='_compute_stock_counts', string='Unreserved In Stock')

    _sql_constraints = [
        ('identity_key_unique', 'unique(identity_key)',
         'A Medal Rack for this exact Medal Part already exists.'),
    ]

    def _compute_stock_counts(self):
        for rack in self:
            units = self.env['rm.medal.rack.unit'].search([
                ('rack_id', '=', rack.id), ('state', '=', 'in_stock'),
            ])
            rack.stock_count = len(units)
            rack.available_stock_count = len(units.filtered(lambda u: not u.reserved_person_id))

    @api.model
    def get_or_create(self, part_id):
        """part_id: the id of the rm.medal.part this Rack wraps.
        Returns the rm.medal.rack for that exact Part, creating it
        (with the SAME identity_key as the Part, since it's a 1:1
        relationship) if it doesn't exist yet."""
        part = self.env['rm.medal.part'].browse(part_id)
        rack = self.search([('identity_key', '=', part.identity_key)], limit=1)
        if rack:
            return rack
        return self.create({
            'identity_key': part.identity_key,
            'size': part.size,
            'part_id': part.id,
        })

    def _ensure_product(self):
        self.ensure_one()
        if not self.product_id:
            label = 'Medal Rack #%s' % (self.id or 'new')
            variant = self._ensure_rm_variant(
                'Medal Rack', 'Medal Rack Combination', label,
                extra_template_vals={'rm_is_finished_rack': True})
            self.write({'product_id': variant.id, 'product_label': label})
        self._generate_rack_image()

    # Must match static/src/scss/medal_rack.scss's fixed 12cm row / 3cm
    # cell / 8cm cell-height layout exactly, at a chosen 40px/cm scale
    # (arbitrary but consistent - only the ratios need to match CSS).
    _MEDAL_CELL_W, _MEDAL_CELL_H = 120, 320
    _MEDAL_ROW_W = 480

    def _get_own_row(self):
        """This Medal Rack's own row, left-to-right, highest
        precedence on the right - reconstructed from its own Part's
        award_ids (junction sequence 0 = highest precedence, matching
        how it was created), then reversed to match rendering order
        (see medal_rack.js's `row` getter, which this mirrors)."""
        self.ensure_one()
        if not self.part_id:
            return self.env['rm.prb']
        ordered_desc = self.part_id.award_ids.sorted('sequence').mapped('award_id')
        return ordered_desc[::-1]

    def _generate_rack_image(self):
        """(Re)generate this Rack's own product image - a real, stored
        picture matching the Medal Rack widget's own layout (fixed
        12cm-wide row, cells overlapping equally once there are more
        than 4) - set on the underlying variant (image_variant_1920),
        not the shared template. Safe/cheap to call repeatedly; does
        nothing if Pillow isn't available, there's no row to draw, or
        the product isn't resolved yet."""
        self.ensure_one()
        if not self.product_id or not self._rm_pil_available():
            return
        row = self._get_own_row()
        count = len(row)
        if not count:
            return
        canvas = self._rm_new_canvas(self._MEDAL_ROW_W, self._MEDAL_CELL_H)
        if count == 1:
            lefts = [(self._MEDAL_ROW_W - self._MEDAL_CELL_W) // 2]
        else:
            overlap = max(0.0, self._MEDAL_CELL_W - (self._MEDAL_ROW_W - self._MEDAL_CELL_W) / (count - 1))
            step = self._MEDAL_CELL_W - overlap
            total_w = step * (count - 1) + self._MEDAL_CELL_W
            start = (self._MEDAL_ROW_W - total_w) / 2
            lefts = [round(start + i * step) for i in range(count)]
        # Paste right-to-left so the LEFTMOST cell ends up drawn last
        # (on top) wherever cells overlap - matching the widget's own
        # z-index: count - index (leftmost highest).
        for idx in reversed(range(count)):
            prb = row[idx]
            self._rm_paste_cell(
                canvas, prb.medal_id.medal_product_tmpl_id.image_1920,
                prb.attachment_id.image,
                (lefts[idx], 0, self._MEDAL_CELL_W, self._MEDAL_CELL_H))
        self.product_id.image_variant_1920 = self._rm_finalize_image(canvas, flatten=False)

    def _build_bom(self):
        """1x this Rack's own Medal Part product (ensured to have its
        own product+BOM first) + one Medal per award in that Part's
        combination (size-matched, auto-resolved via the 'medal_set'
        Set Template's MEDAL category rule - the point where "ribbon
        parts and medals are combined to manufacture a medal rack") +
        the template's fixed per_rack items (backing, fastener,
        packaging), once each."""
        self.ensure_one()
        self._ensure_product()
        template = self.env['rm.set.template'].search([('category', '=', 'medal_set')], limit=1)
        if not template:
            raise UserError(_('No "Medal Set" Set Template is configured. Create one under '
                               'Ribbon Medal > Manufacturing > Set Templates.'))

        totals = {}
        missing = []

        def add(product, qty, uom):
            if not product:
                return
            key = (product.id, uom.id)
            totals[key] = totals.get(key, 0.0) + qty

        size_label = self.size.upper()

        self.part_id._ensure_product_and_bom()
        add(self.part_id.product_id, 1.0, self.part_id.product_id.uom_id)

        medal_rule = template.component_rule_ids.filtered(
            lambda r: r.scope == 'per_cell' and r.category_id.code == 'MEDAL')[:1]

        for row in self.part_id.award_ids.sorted('sequence'):
            decoration = row.award_id.medal_id
            medal_tmpl = decoration.medal_product_tmpl_id if decoration else False
            medal_variant = self._get_size_variant(medal_tmpl, size_label) if medal_tmpl else False
            if not medal_variant:
                missing.append(_('Size %s medal variant for "%s"') % (
                    size_label, row.award_id.display_name))
                continue
            qty = medal_rule.quantity if medal_rule else 1.0
            uom = (medal_rule.uom_id if medal_rule else False) or medal_variant.uom_id
            add(medal_variant, qty, uom)

        for rule in template.component_rule_ids.filtered(lambda r: r.scope == 'per_rack'):
            product = rule.default_product_id.product_variant_id
            if not product:
                missing.append(_('Default product for category "%s"') % rule.category_id.name)
                continue
            add(product, rule.quantity, rule.uom_id or product.uom_id)

        if missing:
            raise UserError(_('This Medal Rack\'s BOM could not be fully resolved:\n- %s') %
                             '\n- '.join(missing))

        bom = self.env['mrp.bom'].create({
            'product_tmpl_id': self.product_id.product_tmpl_id.id,
            'product_id': self.product_id.id,
            'product_qty': 1.0,
            'type': 'normal',
            'code': 'MEDALRACK-%s' % self.id,
            'bom_line_ids': [(0, 0, {
                'product_id': pid,
                'product_qty': qty,
                'product_uom_id': uid,
            }) for (pid, uid), qty in totals.items()],
        })
        self.bom_id = bom.id
        return bom

    def get_available_stock_quantity(self):
        self.ensure_one()
        return self.product_id.qty_available if self.product_id else 0.0

    def get_stock_units(self, quantity):
        self.ensure_one()
        available_qty = self.get_available_stock_quantity()
        if available_qty < quantity:
            quantity = int(available_qty)
        if quantity <= 0:
            return self.env['rm.medal.rack.unit']
        return self.env['rm.medal.rack.unit'].search([
            ('rack_id', '=', self.id), ('state', '=', 'in_stock'), ('reserved_person_id', '=', False),
        ], limit=int(quantity))

    def manufacture_units(self, quantity, reserved_person_id=False):
        self.ensure_one()
        created_units = self.env['rm.medal.rack.unit']
        for _count in range(int(quantity)):
            created_units |= self.manufacture_unit(reserved_person_id=reserved_person_id)
        return created_units

    def record_usage(self):
        for rack in self:
            rack.write({'use_count': rack.use_count + 1, 'last_used_date': fields.Datetime.now()})

    def manufacture_unit(self, reserved_person_id=False):
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
        return self.env['rm.medal.rack.unit'].create({
            'rack_id': self.id,
            'state': 'in_stock',
            'reserved_person_id': reserved_person_id,
            'mrp_production_id': production.id,
        })


class RmMedalRackUnit(models.Model):
    """One physical, individually trackable unit of a Medal Rack -
    in stock (optionally reserved for a person) or already delivered."""
    _name = 'rm.medal.rack.unit'
    _description = 'Medal Rack - Stock Unit'
    _order = 'id'

    rack_id = fields.Many2one('rm.medal.rack', required=True, ondelete='cascade')
    size = fields.Selection(related='rack_id.size', string='Size', store=True)
    state = fields.Selection(
        [('in_stock', 'In Stock'), ('delivered', 'Delivered')], default='in_stock', required=True)
    reserved_person_id = fields.Many2one(
        'res.partner', string='Reserved For', domain=[('is_person', '=', True)],
        help='Set when this unit was freshly manufactured for a specific person '
             'but not yet marked delivered.')
    mrp_production_id = fields.Many2one('mrp.production', readonly=True, string='Manufacturing Order')
    mo_state = fields.Selection(related='mrp_production_id.state', string='MO Status')
    delivered_to_person_id = fields.Many2one(
        'res.partner', readonly=True, string='Delivered To', domain=[('is_person', '=', True)])
    delivery_date = fields.Datetime(readonly=True)

    def action_deliver(self, person_id=None):
        self.ensure_one()
        target = person_id or (self.reserved_person_id.id if self.reserved_person_id else False)
        if not target:
            raise UserError(_('No person specified to deliver this Medal Rack unit to.'))
        self.write({
            'state': 'delivered',
            'delivered_to_person_id': target,
            'delivery_date': fields.Datetime.now(),
        })

    def action_release_reservation(self):
        self.write({'reserved_person_id': False})
