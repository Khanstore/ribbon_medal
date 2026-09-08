# -*- coding: utf-8 -*-
from odoo import _, api, fields, models
from odoo.exceptions import UserError

MEDAL_SIZE_SELECTION = [
    ('s', 'Small (Meskit)'),
    ('l', 'Large (Tunic)'),
]


class RmMedalPart(models.Model):
    """The "ribbon mount" - the physically manufactured assembly that
    holds the ribbon strip for EVERY medal-eligible award in a
    person's Medal Rack, at a specific size (S/L).

    Unlike a Ribbon Rack Line (one row of several ribbons), a Medal
    Part covers a person's WHOLE combination in one go: medals mount
    individually side by side on one board rather than splitting into
    rows, so there is exactly one Part per (award-combination, size) -
    the same role a Line plays for Ribbon Rack, just scaled to the
    entire set instead of one row of it.

    Its BOM consumes every per_cell rule on the 'medal_set' Set
    Template - RIBBON, GUM, and so on - once per award in the
    combination, EXCEPT:
      - MEDAL: the struck medal itself is combined only at the Medal
        Rack tier (see rm.medal.rack._build_bom).
      - BACKING: the backing board is one per whole rack, not one per
        medal, so it's a per_rack rule handled at the Rack tier too.

    Identity (`identity_key` = ordered award ids + size) is permanent:
    once a Part exists for a given combination/size it is reused
    forever - the same stock-reuse guarantee `rm.rack.line` gives
    Ribbon Rack rows. Matching here is EXACT only (no trim-matching
    like rm.rack.line does for partial row overlaps) - a Medal Part's
    combination is specific to one person's whole ledger, so partial
    reuse across different people isn't attempted.
    """
    _name = 'rm.medal.part'
    _inherit = ['rm.product.sync.mixin']
    _description = 'Medal Part (Ribbon mount for a full Medal Rack combination)'
    _order = 'id'

    identity_key = fields.Char(index=True, readonly=True, copy=False)
    size = fields.Selection(MEDAL_SIZE_SELECTION, required=True, readonly=True)
    award_ids = fields.One2many(
        'rm.medal.part.award', 'part_id', string='Awards', readonly=True)
    display_identity = fields.Char(
        compute='_compute_display_identity', store=True, string='Medal Part')
    product_tmpl_id = fields.Many2one('product.template', readonly=True, copy=False)
    bom_id = fields.Many2one('mrp.bom', readonly=True, copy=False)
    use_count = fields.Integer(default=0, readonly=True)
    last_used_date = fields.Datetime(readonly=True)
    unit_ids = fields.One2many('rm.medal.part.unit', 'part_id', string='Units')
    stock_count = fields.Integer(compute='_compute_stock_count', string='In Stock')
    bom_incomplete = fields.Boolean(
        readonly=True, copy=False,
        help='True if this Part\'s BOM could not fully auto-resolve '
             '(e.g. an award\'s Ribbon has no variant at this size). '
             'Review and complete its BOM manually.')

    _sql_constraints = [
        ('identity_key_unique', 'unique(identity_key)',
         'A Medal Part for this exact award combination and size already exists.'),
    ]

    @api.depends('award_ids.sequence', 'award_ids.award_id.name', 'size')
    def _compute_display_identity(self):
        size_labels = dict(MEDAL_SIZE_SELECTION)
        for part in self:
            names = ' + '.join(part.award_ids.sorted('sequence').mapped('award_id.name'))
            part.display_identity = (
                '%s (%s)' % (names, size_labels.get(part.size, '')) if names else '')

    def _compute_stock_count(self):
        for part in self:
            product = part._get_own_variant()
            part.stock_count = int(product.qty_available) if product else 0

    @api.model
    def _key_for_award_ids(self, award_ids, size):
        return '%s:%s' % (size, '-'.join(str(i) for i in award_ids))

    @api.model
    def get_or_create(self, award_ids, size):
        """award_ids: ORDERED list of rm.prb ids (highest precedence
        first) for the person's WHOLE medal-eligible combination.
        size: 's' or 'l'. Returns the rm.medal.part for that exact
        combination, creating it if it doesn't exist yet (product/BOM
        are NOT built here - see _ensure_product_and_bom, called only
        when actually needed)."""
        award_ids = list(award_ids)
        key = self._key_for_award_ids(award_ids, size)
        part = self.search([('identity_key', '=', key)], limit=1)
        if part:
            return part
        return self.create({
            'identity_key': key,
            'size': size,
            'award_ids': [(0, 0, {'sequence': idx, 'award_id': aid})
                          for idx, aid in enumerate(award_ids)],
        })

    def _get_own_variant(self):
        """Return this Part's own single-size product.product variant."""
        self.ensure_one()
        if not self.product_tmpl_id:
            return self.env['product.product']
        return self._get_size_variant(self.product_tmpl_id, self.size.upper())

    def _ensure_product(self):
        self.ensure_one()
        if not self.product_tmpl_id:
            vals = self._prepare_sync_product_vals(
                'Medal Part: %s' % self.display_identity,
                size_variants='l_only' if self.size == 'l' else 's_only')
            tmpl = self._create_product_resilient(vals)
            self.product_tmpl_id = tmpl.id

    def _ensure_product_and_bom(self):
        self.ensure_one()
        self._ensure_product()
        if not self.bom_id:
            self._build_bom()

    def _build_bom(self):
        """Every per_cell rule on the 'medal_set' Set Template, applied
        once per award in this Part's combination - EXCEPT MEDAL and
        BACKING, both resolved once at the Medal Rack tier instead
        (see the class docstring)."""
        self.ensure_one()
        self._ensure_product()
        template = self.env['rm.set.template'].search([('category', '=', 'medal_set')], limit=1)
        if not template:
            raise UserError(_('No "Medal Set" Set Template is configured. Create one under '
                               'Ribbon Medal > Manufacturing > Set Templates.'))

        totals = {}
        incomplete = False

        def add(product, qty, uom):
            if not product:
                return
            key = (product.id, uom.id)
            totals[key] = totals.get(key, 0.0) + qty

        size_label = self.size.upper()
        rules = template.component_rule_ids.filtered(
            lambda r: r.scope == 'per_cell' and r.category_id.code not in ('MEDAL', 'BACKING'))
        for row in self.award_ids.sorted('sequence'):
            for rule in rules:
                if not rule.is_user_selected:
                    product = rule.default_product_id.product_variant_id
                    if not product:
                        incomplete = True
                        continue
                    add(product, rule.quantity, rule.uom_id or product.uom_id)
                elif rule.category_id.code == 'RIBBON':
                    decoration = row.award_id.ribbon_id
                    tmpl = decoration.ribbon_product_tmpl_id if decoration else False
                    variant = self._get_size_variant(tmpl, size_label) if tmpl else False
                    if not variant:
                        incomplete = True
                        continue
                    add(variant, rule.quantity, rule.uom_id or variant.uom_id)
                else:
                    # No automatic source for this category at Part-build
                    # time (mirrors rm.rack.line._build_bom's handling of
                    # e.g. BACKING there - a manager must complete it
                    # manually if a new such category is ever added).
                    incomplete = True

        bom = self.env['mrp.bom'].create({
            'product_tmpl_id': self.product_tmpl_id.id,
            'product_id': self.product_tmpl_id.product_variant_id.id,
            'product_qty': 1.0,
            'type': 'normal',
            'code': 'MEDALPART-%s' % self.identity_key,
            'bom_line_ids': [(0, 0, {
                'product_id': pid,
                'product_qty': qty,
                'product_uom_id': uid,
            }) for (pid, uid), qty in totals.items()],
        })
        self.write({'bom_id': bom.id, 'bom_incomplete': incomplete})
        return bom

    def get_available_stock_quantity(self):
        self.ensure_one()
        product = self._get_own_variant()
        return product.qty_available if product else 0.0

    def get_stock_units(self, quantity):
        self.ensure_one()
        available_qty = self.get_available_stock_quantity()
        if available_qty < quantity:
            quantity = int(available_qty)
        if quantity <= 0:
            return self.env['rm.medal.part.unit']
        return self.env['rm.medal.part.unit'].search([
            ('part_id', '=', self.id), ('state', '=', 'in_stock'),
        ], limit=int(quantity))

    def consume_stock_units(self, quantity, person_name):
        self.ensure_one()
        units = self.get_stock_units(quantity)
        consumed = 0
        for unit in units:
            unit.write({'state': 'consumed', 'consumed_note': _('Used for %s') % person_name})
            consumed += 1
        return consumed

    def manufacture_units(self, quantity):
        self.ensure_one()
        created_units = self.env['rm.medal.part.unit']
        for _count in range(int(quantity)):
            created_units |= self.manufacture_unit()
        return created_units

    def record_usage(self):
        for part in self:
            part.write({'use_count': part.use_count + 1, 'last_used_date': fields.Datetime.now()})

    def manufacture_unit(self):
        """Create/fold into an MO for exactly one unit of this Part.
        Same MO-folding behaviour as rm.rack.line.manufacture_unit -
        see there for the full rationale (avoids one MO per unit when
        several units of the same Part are needed back to back)."""
        self.ensure_one()
        self._ensure_product_and_bom()
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
        return self.env['rm.medal.part.unit'].create({
            'part_id': self.id, 'state': 'in_stock', 'mrp_production_id': production.id,
        })


class RmMedalPartAward(models.Model):
    """One row of a Medal Part's locked, ordered award sequence."""
    _name = 'rm.medal.part.award'
    _description = 'Medal Part - Award in Sequence'
    _order = 'part_id, sequence'

    part_id = fields.Many2one('rm.medal.part', required=True, ondelete='cascade')
    sequence = fields.Integer(default=10)
    award_id = fields.Many2one('rm.prb', required=True, string='Award')


class RmMedalPartUnit(models.Model):
    """One physical, individually trackable unit of a Medal Part -
    either sitting in stock (a "blank" mount, ready for medals) or
    already consumed into a Medal Rack."""
    _name = 'rm.medal.part.unit'
    _description = 'Medal Part - Stock Unit'
    _order = 'id'

    part_id = fields.Many2one('rm.medal.part', required=True, ondelete='cascade')
    state = fields.Selection(
        [('in_stock', 'In Stock'), ('consumed', 'Consumed')], default='in_stock', required=True)
    mrp_production_id = fields.Many2one('mrp.production', readonly=True, string='Manufacturing Order')
    mo_state = fields.Selection(related='mrp_production_id.state', string='MO Status')
    consumed_note = fields.Char(readonly=True)
