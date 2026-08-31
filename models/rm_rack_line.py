# -*- coding: utf-8 -*-
from odoo import _, api, fields, models
from odoo.exceptions import UserError


class RmRackLine(models.Model):
    """A Line = one physically assembled row (several ribbons mounted
    side by side, gummed and backed) - the intermediate stock unit
    between raw ribbon material and a full Rack. Identity is the EXACT
    ordered sequence of ribbons (rm.prb ids) in that row.

    Never holds attachments - those are applied to individual ribbons,
    not to the assembled row.

    Matching is two-tier (see find_best_stock_match): exact identity
    first, then a "trim" match against any in-stock Line whose sequence
    CONTAINS what's needed as a contiguous run (left/right/both-end
    trim only, never a middle removal). A trim always fully consumes
    the source unit - the trimmed-off ribbons are scrap.
    """
    _name = 'rm.rack.line'
    _inherit = ['rm.product.sync.mixin']
    _description = 'Rack Line (assembled row of ribbons)'
    _order = 'id'

    identity_key = fields.Char(index=True, readonly=True, copy=False)
    item_ids = fields.One2many('rm.rack.line.item', 'line_id', string='Ribbons', readonly=True)
    display_identity = fields.Char(
        compute='_compute_display_identity', store=True, string='Ribbons')
    product_tmpl_id = fields.Many2one('product.template', readonly=True, copy=False)
    bom_id = fields.Many2one('mrp.bom', readonly=True, copy=False)
    use_count = fields.Integer(default=0, readonly=True)
    last_used_date = fields.Datetime(readonly=True)
    unit_ids = fields.One2many('rm.rack.line.unit', 'line_id', string='Units')
    stock_count = fields.Integer(compute='_compute_stock_count', string='In Stock')
    bom_incomplete = fields.Boolean(
        readonly=True, copy=False,
        help='True if this Line\'s BOM could not fully auto-resolve (e.g. '
             'a "User Picks Product" category other than RIBBON, such as '
             'BACKING, has no way to be chosen automatically while a Line '
             'is being created deep inside the allocation cascade). '
             "Review and complete this Line's BOM manually.")

    _sql_constraints = [
        ('identity_key_unique', 'unique(identity_key)',
         'A Line with this exact ribbon sequence already exists.'),
    ]

    @api.depends('item_ids.sequence', 'item_ids.award_id.name')
    def _compute_display_identity(self):
        for line in self:
            line.display_identity = ' + '.join(
                line.item_ids.sorted('sequence').mapped('award_id.name'))

    def _compute_stock_count(self):
        for line in self:
            line.stock_count = self.env['rm.rack.line.unit'].search_count(
                [('line_id', '=', line.id), ('state', '=', 'in_stock')])

    @api.model
    def _key_for_award_ids(self, award_ids):
        return '-'.join(str(i) for i in award_ids)

    @api.model
    def get_or_create(self, award_ids):
        """award_ids: ordered list of rm.prb ids for one row. Returns the
        rm.rack.line for that EXACT sequence, creating it if it doesn't
        exist yet (product/BOM are NOT built here - see
        _ensure_product_and_bom, called only when actually needed)."""
        award_ids = list(award_ids)
        key = self._key_for_award_ids(award_ids)
        line = self.search([('identity_key', '=', key)], limit=1)
        if line:
            return line
        return self.create({
            'identity_key': key,
            'item_ids': [(0, 0, {'sequence': idx, 'award_id': aid})
                         for idx, aid in enumerate(award_ids)],
        })

    def _ensure_product(self):
        self.ensure_one()
        if not self.product_tmpl_id:
            vals = self._prepare_sync_product_vals(f'Rack Line: {self.display_identity}')
            tmpl = self._create_product_resilient(vals)
            self.product_tmpl_id = tmpl.id

    def _ensure_product_and_bom(self):
        self.ensure_one()
        self._ensure_product()
        if not self.bom_id:
            self._build_bom()

    def _build_bom(self):
        """Ribbon (Size L, auto per ribbon) + any fixed (non-user-selected)
        per_cell rule from the default 'ribbon_rack' rm.set.template,
        applied once per ribbon in this line. A per_cell rule that's
        user-selected and isn't RIBBON (e.g. BACKING) has no way to be
        resolved automatically here - it's skipped and bom_incomplete is
        set, rather than blocking the whole allocation cascade."""
        self.ensure_one()
        self._ensure_product()
        template = self.env['rm.set.template'].search([('category', '=', 'ribbon_rack')], limit=1)
        if not template:
            raise UserError(_('No "Ribbon Rack" Set Template is configured.'))

        totals = {}
        incomplete = False

        def add(product, qty, uom):
            if not product:
                return
            key = (product.id, uom.id)
            totals[key] = totals.get(key, 0.0) + qty

        rules = template.component_rule_ids.filtered(lambda r: r.scope == 'per_cell')
        for item in self.item_ids.sorted('sequence'):
            for rule in rules:
                if not rule.is_user_selected:
                    product = rule.default_product_id.product_variant_id
                    if not product:
                        incomplete = True
                        continue
                    add(product, rule.quantity, rule.uom_id or product.uom_id)
                elif rule.category_id.code == 'RIBBON':
                    decoration = item.award_id.ribbon_id
                    tmpl = decoration.ribbon_product_tmpl_id if decoration else False
                    variant = self._get_size_l_variant(tmpl)
                    if not variant:
                        incomplete = True
                        continue
                    add(variant, rule.quantity, rule.uom_id or variant.uom_id)
                else:
                    # e.g. BACKING - no automatic source at Line-creation
                    # time. Flag for manual review rather than blocking.
                    incomplete = True

        bom = self.env['mrp.bom'].create({
            'product_tmpl_id': self.product_tmpl_id.id,
            'product_id': self.product_tmpl_id.product_variant_id.id,
            'product_qty': 1.0,
            'type': 'normal',
            'code': f'LINE-{self.identity_key}',
            'bom_line_ids': [(0, 0, {
                'product_id': pid, 'product_qty': qty, 'product_uom_id': uid,
            }) for (pid, uid), qty in totals.items()],
        })
        self.write({'bom_id': bom.id, 'bom_incomplete': incomplete})
        return bom

<<<<<<< Updated upstream
    def _get_size_l_variant(self, product_tmpl):
        if not product_tmpl:
            return self.env['product.product']
        return product_tmpl.product_variant_ids.filtered(
            lambda p: 'L' in p.product_template_attribute_value_ids.mapped(
                'product_attribute_value_id.name')
        )[:1]
=======
    def _get_size_l_variant(self, product_tmpl=None):
        """Return the Size=L product.product variant of `product_tmpl`.
        If product_tmpl is None, use this line's own product_tmpl_id."""
        if product_tmpl is None:
            product_tmpl = self.product_tmpl_id
        return self._get_size_variant(product_tmpl, 'L')
>>>>>>> Stashed changes

    def record_usage(self):
        for line in self:
            line.write({'use_count': line.use_count + 1, 'last_used_date': fields.Datetime.now()})

    def manufacture_unit(self):
        """Create+confirm an MO for exactly 1 unit of this Line, return
        the resulting rm.rack.line.unit. Note: the unit is marked
        in_stock as soon as the MO is CONFIRMED, not when it's actually
        marked Done - this module tracks manufacturing intent/allocation,
        not shop-floor completion timing. Check mrp_production_id.state
        separately if that distinction matters."""
        self.ensure_one()
        self._ensure_product_and_bom()
        production = self.env['mrp.production'].create({
            'product_id': self.product_tmpl_id.product_variant_id.id,
            'product_qty': 1.0,
            'product_uom_id': self.product_tmpl_id.uom_id.id,
            'bom_id': self.bom_id.id,
            'origin': self.display_identity,
        })
        production.action_confirm()
        return self.env['rm.rack.line.unit'].create({
            'line_id': self.id,
            'state': 'in_stock',
            'mrp_production_id': production.id,
        })

    @staticmethod
    def _contains_contiguous(sequence, needed):
        n, m = len(sequence), len(needed)
        if m > n:
            return False
        for start in range(0, n - m + 1):
            if sequence[start:start + m] == needed:
                return True
        return False

    @api.model
    def find_best_stock_match(self, needed_award_ids):
        """needed_award_ids: ordered list of rm.prb ids for one row.
        Returns (line, unit): an exact-identity in-stock unit if one
        exists, otherwise the best contiguous-substring ("trim") match
        (least waste, then highest use_count, then most recently used).
        Returns (empty recordset, empty recordset) if nothing in stock
        can cover it."""
        needed = list(needed_award_ids)
        key = self._key_for_award_ids(needed)
        exact = self.search([('identity_key', '=', key)], limit=1)
        if exact:
            unit = self.env['rm.rack.line.unit'].search(
                [('line_id', '=', exact.id), ('state', '=', 'in_stock')], limit=1, order='id')
            if unit:
                return exact, unit

        candidates = self.search([('unit_ids.state', '=', 'in_stock')])
        best_line = self.browse()
        best_unit = self.env['rm.rack.line.unit'].browse()
        best_score = None
        epoch = fields.Datetime.from_string('1970-01-01 00:00:00')
        for candidate in candidates:
            sequence = candidate.item_ids.sorted('sequence').mapped('award_id').ids
            if not self._contains_contiguous(sequence, needed):
                continue
            unit = self.env['rm.rack.line.unit'].search(
                [('line_id', '=', candidate.id), ('state', '=', 'in_stock')], limit=1, order='id')
            if not unit:
                continue
            waste = len(sequence) - len(needed)
            last_used = candidate.last_used_date or epoch
            score = (waste, -candidate.use_count, -last_used.timestamp())
            if best_score is None or score < best_score:
                best_score, best_line, best_unit = score, candidate, unit
        return best_line, best_unit


class RmRackLineItem(models.Model):
    _name = 'rm.rack.line.item'
    _description = 'Rack Line - Ribbon in Sequence'
    _order = 'line_id, sequence'

    line_id = fields.Many2one('rm.rack.line', required=True, ondelete='cascade')
    sequence = fields.Integer(default=10)
    award_id = fields.Many2one('rm.prb', required=True, string='Ribbon (Award)')


class RmRackLineUnit(models.Model):
    _name = 'rm.rack.line.unit'
    _description = 'Rack Line - Stock Unit'
    _order = 'id'

    line_id = fields.Many2one('rm.rack.line', required=True, ondelete='cascade')
    state = fields.Selection(
        [('in_stock', 'In Stock'), ('consumed', 'Consumed')], default='in_stock', required=True)
    mrp_production_id = fields.Many2one('mrp.production', readonly=True)
    mo_state = fields.Selection(related='mrp_production_id.state', string='MO Status')
    consumed_note = fields.Char(
        readonly=True,
        help='What this unit was consumed for (e.g. used directly, or '
             'trimmed to fulfil a shorter Line requirement).')
