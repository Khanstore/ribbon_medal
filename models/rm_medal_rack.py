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
    _inherit = ['rm.product.sync.mixin']
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
    product_tmpl_id = fields.Many2one('product.template', readonly=True, copy=False)
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
        if not self.product_tmpl_id:
            vals = self._prepare_sync_product_vals(
                'Medal Rack #%s' % (self.id or 'new'),
                size_variants='l_only' if self.size == 'l' else 's_only')
            tmpl = self._create_product_resilient(vals)
            self.product_tmpl_id = tmpl.id

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
        add(self.part_id.product_tmpl_id.product_variant_id, 1.0, self.part_id.product_tmpl_id.uom_id)

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
            'product_tmpl_id': self.product_tmpl_id.id,
            'product_id': self.product_tmpl_id.product_variant_id.id,
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
        if not self.product_tmpl_id:
            return 0.0
        product = self.product_tmpl_id.product_variant_id
        return product.qty_available if product else 0.0

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
        product = self.product_tmpl_id.product_variant_id
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
                'product_uom_id': self.product_tmpl_id.uom_id.id,
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
        'res.person', string='Reserved For',
        help='Set when this unit was freshly manufactured for a specific person '
             'but not yet marked delivered.')
    mrp_production_id = fields.Many2one('mrp.production', readonly=True, string='Manufacturing Order')
    mo_state = fields.Selection(related='mrp_production_id.state', string='MO Status')
    delivered_to_person_id = fields.Many2one('res.person', readonly=True, string='Delivered To')
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
