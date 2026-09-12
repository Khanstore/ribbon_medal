# -*- coding: utf-8 -*-
from odoo import _, api, fields, models
from odoo.exceptions import UserError, ValidationError
from datetime import date, datetime


class ResPartner(models.Model):
    """Personnel attributes, merged directly onto res.partner (classical
    inheritance) - replacing the earlier res.person model, which used
    delegation inheritance (`_inherits`) to a separate table.

    A "Person" is now just any res.partner with is_person=True: there is
    no separate table, no separate id, and no separate record to keep in
    sync with its backing Contact - Personnel IS Contacts, filtered.

    See migrations/18.0.2.0.0/ for how existing res.person data - and
    every foreign key and chatter record that used to point at it - gets
    moved onto the corresponding res.partner row on upgrade.
    """
    _inherit = 'res.partner'

    is_person = fields.Boolean(
        string='Is Personnel', default=False, index=True,
        help='Tick to treat this Contact as a Personnel record (adds ID '
             "Number, Rank, Force, and the Decorations/Awards tracking "
             "below). An ID Number is required once this is ticked.")

    id_number = fields.Char(string='ID Number', index=True)
    rank_id = fields.Many2one('rm.ranks', string='Rank', ondelete='restrict')

    _sql_constraints = [
        ('id_number_force_uniq', 'unique(force_id, id_number)',
         'This ID Number is already used by another Personnel record in '
         'the same Force.'),
    ]

    @api.constrains('is_person', 'id_number')
    def _check_id_number_required_for_person(self):
        for partner in self:
            if partner.is_person and not partner.id_number:
                raise ValidationError(_(
                    'ID Number is required once "Is Personnel" is ticked '
                    '(%s).') % partner.display_name)

    def copy(self, default=None):
        """Duplicating a Personnel record must not carry over its ID
        Number - that would immediately collide with the (Force, ID
        Number) uniqueness constraint above on save."""
        default = dict(default or {})
        if self.is_person and 'id_number' not in default:
            default['id_number'] = False
        return super().copy(default)

    # Compute rank seniority level on the fly instead of storing it
    # This avoids registry issues during module loading
    rank_seniority_level = fields.Integer(
        string='Rank Seniority Level',
        compute='_compute_rank_seniority_level',
        store=False,
        help='Mirrors the seniority_level of the selected rank; used to '
             "restrict Current Workplace choices to units whose chief's "
             'rank is senior enough.')

    @api.depends('rank_id.seniority_level')
    def _compute_rank_seniority_level(self):
        for partner in self:
            partner.rank_seniority_level = partner.rank_id.seniority_level or 0

    current_workplace = fields.Many2one(
        'rm.unit', string='Current Workplace', ondelete='restrict',
        domain="[('level', '>=', rank_seniority_level)]",
        help='Restricted to units whose chief has a seniority level at or '
             "above this person's own rank, so personnel cannot be posted "
             "somewhere their rank outranks the unit's chief.")
    bcs_batch = fields.Many2one('rm.bcs.batch', string='BCS Batch')
    service_confirmation_date = fields.Date(string='Service Confirmation Date')

    obtained_awards_ids = fields.Many2many(
        'rm.prb', string='Obtained Awards', compute='_compute_obtained_awards_ids')
    rack_ledger_ids = fields.Many2many(
        'rm.acquisition', string='Ribbon Rack Ledger', compute='_compute_rack_ledger_ids',
        help='Same acquisitions as obtained_awards_ids, but keeping each '
             "row's own attachment_id (the specific device received at "
             'that acquisition) for the Ribbon Rack widget to display.')
    award_count = fields.Integer(compute='_compute_award_count')
    ordered_rack_count = fields.Integer(
        compute='_compute_ordered_rack_count',
        help='Number of sale order lines (any of the 3 rack types) for this person.')
    undelivered_rack_count = fields.Integer(
        compute='_compute_undelivered_rack_count',
        help="Number of this person's own sale orders' outgoing stock "
             "deliveries that aren't Done yet - the real stock.picking "
             "record, not an approximation.")
    rack_total_price = fields.Float(
        string='Ribbon Rack Price', compute='_compute_rack_total_price',
        help='Sum of each acquired ribbon product\'s list price, plus '
             "each acquisition's attachment device product's list price "
             '(when one is set).')
    tunic_medal_rack_price = fields.Float(
        string='Tunic Medal Rack Price', compute='_compute_medal_rack_prices',
        help='Sum of the list price of every Medal + attachment device product '
             "for this person's Tunic (large-size) medal-eligible acquisitions.")
    meskit_medal_rack_price = fields.Float(
        string='Meskit Medal Rack Price', compute='_compute_medal_rack_prices',
        help='Sum of the list price of every Medal + attachment device product '
             "for this person's Meskit (small-size) medal-eligible acquisitions.")
    force_id = fields.Many2one(
        'rm.forces', string='Force', related='rank_id.force_id', store=True, readonly=True)
    name_eng = fields.Char(string='Name (English)', help='Nameplate spelling in English.')
    name_bng = fields.Char(string='Name (Bengali)', help='Nameplate spelling in Bengali.')
    birth_date = fields.Date(string="Birth Date")
    retirement_date = fields.Date(string="Retirement Date")
    age = fields.Integer(string='Age', compute='_compute_age')
    service_age = fields.Integer(string='Service Age', compute='_compute_service_age')
    is_retired = fields.Boolean(string='Retired', compute='_compute_is_retired')

    # Read-only views into the consolidated Acquisition Ledger, split by
    # source, for the three notebook pages on the form. rm.acquisition is
    # a SQL view (not a real table) but One2many works fine against it -
    # it's just a filtered search(), not a real foreign key.
    personal_award_ledger_ids = fields.One2many(
        'rm.personal.awards', 'person_id', string='Personal Awards',
    )
    service_ledger_ids = fields.One2many(
        'rm.acquisition', 'person_id', string='Service',
        domain=[('source', '=', 'batch')])
    mission_ledger_ids = fields.One2many(
        'rm.mission.posting', 'person_id', string='Mision'
    )
    seniority_ledger_ids = fields.One2many(
        'rm.acquisition', 'person_id', string='Seniority',
        domain=[('source', '=', 'seniority')])
    custom_ledger_ids = fields.One2many(
        'rm.acquisition.custom', 'person_id', string='Customised Ledger')

    @api.depends('birth_date')
    def _compute_age(self):
        today = fields.Date.today()
        for partner in self:
            if partner.birth_date:
                partner.age = today.year - partner.birth_date.year - (
                        (today.month, today.day) < (partner.birth_date.month, partner.birth_date.day))
            else:
                partner.age = 0

    @api.depends('service_confirmation_date')
    def _compute_service_age(self):
        today = fields.Date.today()
        for partner in self:
            if partner.service_confirmation_date:
                partner.service_age = today.year - partner.service_confirmation_date.year - (
                        (today.month, today.day) < (partner.service_confirmation_date.month,
                                                    partner.service_confirmation_date.day))
            else:
                partner.service_age = 0

    @api.depends('retirement_date')
    def _compute_is_retired(self):
        today = fields.Date.today()
        for partner in self:
            partner.is_retired = bool(partner.retirement_date and partner.retirement_date <= today)

    # Every compute below derives from the consolidated Acquisition Ledger
    # (rm.acquisition, a SQL view unioning Personal Awards + Missions +
    # the Seniority/Batch rules derived from force_id/service_confirmation_date).
    # The view itself can't be depended on directly, but the REAL fields that
    # feed it can be - depending on those is what makes Odoo actually
    # recompute (and the Ribbon/Medal Rack widgets refresh) whenever an
    # award is added/removed/edited, instead of only after a full reload.
    _LEDGER_DEPENDS = (
        'personal_award_ledger_ids', 'personal_award_ledger_ids.award_id',
        'personal_award_ledger_ids.active', 'personal_award_ledger_ids.attachment_id',
        'personal_award_ledger_ids.add_to_ribbon', 'personal_award_ledger_ids.add_to_big_medal',
        'personal_award_ledger_ids.add_to_mini_medal',
        'mission_ledger_ids', 'mission_ledger_ids.mission_id',
        'mission_ledger_ids.active', 'mission_ledger_ids.attachment_id',
        'mission_ledger_ids.add_to_ribbon', 'mission_ledger_ids.add_to_big_medal',
        'mission_ledger_ids.add_to_mini_medal',
        'force_id', 'service_confirmation_date',
    )

    @api.depends(*_LEDGER_DEPENDS)
    def _compute_award_count(self):
        Acquisition = self.env['rm.acquisition']
        for partner in self:
            partner.award_count = Acquisition.search_count([('person_id', '=', partner.id)])

    @api.depends()
    def _compute_ordered_rack_count(self):
        Line = self.env['sale.order.line']
        for partner in self:
            partner.ordered_rack_count = Line.search_count([
                ('person_id', '=', partner.id),
                ('rack_type', '!=', False),
            ])

    @api.depends()
    def _compute_undelivered_rack_count(self):
        Picking = self.env['stock.picking']
        for partner in self:
            partner.undelivered_rack_count = Picking.search_count(
                self._undelivered_picking_domain(partner.id))

    @api.model
    def _undelivered_picking_domain(self, person_id):
        """Real, not-yet-done outgoing stock.picking records for this
        Person's own sale orders (matched via stock.picking.sale_id ->
        sale.order.person_id, not by partner delivery-address, since a
        delivery address can differ from the Person themselves) - this
        is the actual delivery record, not an approximation."""
        return [
            ('sale_id.person_id', '=', person_id),
            ('picking_type_id.code', '=', 'outgoing'),
            ('state', 'not in', ('done', 'cancel')),
        ]

    def _rack_line_action_views(self):
        """Reuse the standard sale.order.line list view (used by the
        product form's own "Sold" stat button) if it's available on
        this instance's sale module, so these buttons show a proper
        list instead of an auto-generated fallback; degrade gracefully
        if it isn't there."""
        list_view = self.env.ref('sale.view_order_line_tree', raise_if_not_found=False)
        return [(list_view.id if list_view else False, 'list'), (False, 'form')]

    def action_view_ordered_racks(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _('Ordered Racks'),
            'res_model': 'sale.order.line',
            'views': self._rack_line_action_views(),
            'domain': [
                ('person_id', '=', self.id),
                ('rack_type', '!=', False),
            ],
            'context': {'group_by': ['order_id']},
        }

    def action_save_and_refresh(self):
        """Save whatever's pending on this form and hard-reload the
        page afterward - the simplest reliable fix for the Ribbon/Medal
        Rack ledger widgets not always re-rendering after a change made
        elsewhere."""
        self.ensure_one()
        return {'type': 'ir.actions.client', 'tag': 'reload'}

    def action_view_undelivered_racks(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _('Not Delivered'),
            'res_model': 'stock.picking',
            'view_mode': 'list,form',
            'domain': self._undelivered_picking_domain(self.id),
        }

    @api.depends(*_LEDGER_DEPENDS)
    def _compute_obtained_awards_ids(self):
        Acquisition = self.env['rm.acquisition']
        for partner in self:
            acquisitions = Acquisition.search([('person_id', '=', partner.id)])
            partner.obtained_awards_ids = acquisitions.mapped('award_id')

    @api.depends(*_LEDGER_DEPENDS)
    def _compute_rack_ledger_ids(self):
        Acquisition = self.env['rm.acquisition']
        for partner in self:
            partner.rack_ledger_ids = Acquisition.search([('person_id', '=', partner.id)])

    @api.depends(*_LEDGER_DEPENDS)
    def _compute_rack_total_price(self):
        Acquisition = self.env['rm.acquisition']
        for partner in self:
            acquisitions = Acquisition.search([('person_id', '=', partner.id)])
            partner.rack_total_price = (
                    sum(acquisitions.mapped('ribbon_list_price'))
                    + sum(acquisitions.mapped('attachment_list_price'))
            )

    @api.depends(*_LEDGER_DEPENDS)
    def _compute_medal_rack_prices(self):
        Acquisition = self.env['rm.acquisition']
        for partner in self:
            medal_acquisitions = Acquisition.search([
                ('person_id', '=', partner.id), ('is_medal', '=', True),
            ])
            tunic = medal_acquisitions.filtered('add_to_big_medal')
            meskit = medal_acquisitions.filtered('add_to_mini_medal')
            partner.tunic_medal_rack_price = (
                    sum(tunic.mapped('medal_list_price')) + sum(tunic.mapped('attachment_list_price'))
            )
            partner.meskit_medal_rack_price = (
                    sum(meskit.mapped('medal_list_price')) + sum(meskit.mapped('attachment_list_price'))
            )

    @api.model
    def get_rack_widget_context(self, person_id, force_id, prb_ids):
        """RPC endpoint for the Ribbon/Medal Rack widgets' client-side
        (JavaScript) INSTANT ledger computation - see
        static/src/js/rack_ledger.js. MAINTENANCE WARNING: kept in sync
        with rm.acquisition's SQL view BY HAND."""
        Prb = self.env['rm.prb']
        seniority_batch_rules = self.env['rm.prb']
        if force_id:
            seniority_batch_rules = Prb.search([
                ('force_id', '=', force_id),
                ('active', '=', True),
                ('rule_category_id.name', 'in', ('seniority', 'batch')),
            ])

        requested = Prb.browse(prb_ids).exists() if prb_ids else Prb.browse()
        all_prbs = requested | seniority_batch_rules

        def _attrs(prb):
            return {
                'id': prb.id,
                'name': prb.name,
                'sequence': prb.sequence,
                'is_ribbon': prb.is_ribbon,
                'is_medal': prb.is_medal,
                'has_ribbon_image': bool(prb.ribbon_id.ribbon_product_tmpl_id.image_1920),
                'has_medal_image': bool(prb.medal_id.medal_product_tmpl_id.image_1920),
                'ribbon_decoration_id': prb.ribbon_id.id or False,
                'medal_decoration_id': prb.medal_id.id or False,
                'default_attachment_id': prb.attachment_id.id or False,
            }

        prb_attrs = {prb.id: _attrs(prb) for prb in all_prbs}

        seniority_rules = []
        batch_rules = []
        for prb in seniority_batch_rules:
            category = prb.rule_category_id.name
            if category == 'seniority':
                if not prb.service_age:
                    continue
                row = dict(prb_attrs[prb.id])
                row['service_age'] = prb.service_age
                seniority_rules.append(row)
            elif category == 'batch':
                if not prb.starting_date:
                    continue
                row = dict(prb_attrs[prb.id])
                row['starting_date'] = prb.starting_date.isoformat()
                batch_rules.append(row)

        excluded_decoration_ids = []
        if person_id:
            exclusions = self.env['rm.excluded.awards'].search([
                ('person_id', '=', person_id), ('active', '=', True),
            ])
            excluded_decoration_ids = exclusions.mapped('decoration_name').ids

        return {
            'prb_attrs': prb_attrs,
            'seniority_rules': seniority_rules,
            'batch_rules': batch_rules,
            'excluded_decoration_ids': excluded_decoration_ids,
        }

    @api.onchange('id_number')
    def extract_years_from_id_number(self):
        for record in self:
            force_id_record = self.env.ref('ribbon_medal.force_police', raise_if_not_found=False)

            if record.id_number and len(record.id_number) == 10 and record.force_id == force_id_record:
                current_yr = int(datetime.now().strftime('%y'))
                birth_yr_str = record.id_number[0:2]
                joining_yr_str = record.id_number[2:4]

                birth_year_val = int(birth_yr_str)
                joining_year_val = int(joining_yr_str)
                birth_year = (2000 + birth_year_val) if (0 <= birth_year_val <= current_yr) else (1900 + birth_year_val)
                joinng_year = (2000 + joining_year_val) if (0 <= joining_year_val <= current_yr) else (
                            1900 + joining_year_val)

                record.birth_date = date(birth_year, 1, 1)
                record.service_confirmation_date = date(joinng_year, 1, 1)
            else:
                record.birth_date = False
                record.service_confirmation_date = False

    def get_sorted_awards(self):
        """Return obtained awards sorted for Ribbon Rack display: lowest
        `sequence` first (highest precedence, destined for the
        bottom-right position)."""
        self.ensure_one()
        return self.obtained_awards_ids.sorted(key=lambda decoration: decoration.sequence)

    def action_view_awards(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': 'Awards',
            'res_model': 'rm.acquisition',
            'view_mode': 'list',
            'domain': [('person_id', '=', self.id)],
        }

    def action_generate_ribbon_rack(self):
        """Manual/direct path - always builds a fresh generic Ribbon
        Rack from raw materials, ignoring any Rack/Line stock. See
        action_issue_ribbon_rack for the stock-aware cascade."""
        self.ensure_one()
        SetOrder = self.env['rm.set.order']
        order = SetOrder.search([('person_id', '=', self.id)], limit=1)
        if not order:
            order = SetOrder.create({'person_id': self.id})
        return order.action_open_mo_wizard()

    RACK_COLUMNS = 4

    def _get_rack_rows(self):
        """Split this person's acquired ribbons into rows, mirroring the
        Ribbon Rack widget's own layout exactly."""
        self.ensure_one()
        acquisitions = self.env['rm.acquisition'].search([('person_id', '=', self.id)])
        sorted_acquisitions = acquisitions.sorted(key=lambda a: a.sequence, reverse=True)
        awards = sorted_acquisitions.mapped('award_id')
        count = len(awards)
        if not count:
            return []
        ascending = awards[::-1]
        remainder = count % self.RACK_COLUMNS
        top_row_size = remainder or self.RACK_COLUMNS
        rows = [ascending[:top_row_size]]
        i = top_row_size
        while i < count:
            rows.append(ascending[i:i + self.RACK_COLUMNS])
            i += self.RACK_COLUMNS
        return rows

    def _get_medal_rack_awards(self, size):
        """Return this person's medal-eligible acquisitions for the given
        Medal Rack size ('l' = Tunic, 's' = Meskit), ordered highest
        precedence first."""
        self.ensure_one()
        flag_field = 'add_to_big_medal' if size == 'l' else 'add_to_mini_medal'
        acquisitions = self.env['rm.acquisition'].search([
            ('person_id', '=', self.id),
            ('is_medal', '=', True),
            (flag_field, '=', True),
        ])
        sorted_acquisitions = acquisitions.sorted(key=lambda a: a.sequence, reverse=True)
        return sorted_acquisitions.mapped('award_id')

    def _resolve_rack_variant(self, rack_type):
        """Resolve (find-or-create identity + product ONLY - no stock
        check, no manufacturing, nothing committed) this person's
        CURRENT specific product.product for the given rack_type,
        based on their live Acquisition Ledger right now. This is what
        puts the real, specific rack product directly on a sale order
        line - both when the line is first created, and again at order
        confirmation in case the person's combination changed in
        between (a new award, say) - rather than the generic,
        undifferentiated "Ribbon Rack"/"Tunic Medal Rack"/"Meskit Medal
        Rack" product every such line used to carry regardless of who
        it was for.

        Deliberately calls the exact same get_or_create/_ensure_product
        methods _issue_ribbon_rack_unit/_issue_medal_rack_unit use
        internally, just without their stock-check/consume/manufacture
        steps - so "just resolve" and "resolve and commit" can never
        disagree about which specific product a given combination maps
        to.

        Returns a (possibly empty) product.product - empty when the
        person has no acquisitions yet for this rack_type, in which
        case callers should fall back to a generic/placeholder state
        rather than error."""
        self.ensure_one()
        if rack_type == 'ribbon':
            rows = self._get_rack_rows()
            if not rows:
                return self.env['product.product']
            RackLine = self.env['rm.rack.line']
            RackProduct = self.env['rm.rack.product']
            line_ids = []
            for row in rows:
                line = RackLine.get_or_create(row.ids)
                line._ensure_product()
                line_ids.append(line.id)
            rack = RackProduct.get_or_create(line_ids)
            rack._ensure_product()
            return rack.product_id
        if rack_type in ('tunic_medal', 'meskit_medal'):
            size = 'l' if rack_type == 'tunic_medal' else 's'
            awards = self._get_medal_rack_awards(size)
            if not awards:
                return self.env['product.product']
            MedalPart = self.env['rm.medal.part']
            MedalRack = self.env['rm.medal.rack']
            part = MedalPart.get_or_create(awards.ids, size)
            part._ensure_product()
            rack = MedalRack.get_or_create(part.id)
            rack._ensure_product()
            return rack.product_id
        return self.env['product.product']

    def action_issue_ribbon_rack(self):
        self.ensure_one()
        unit, message = self._issue_ribbon_rack_unit()
        return self._issue_notification(message)

    def action_issue_tunic_medal_rack(self):
        self.ensure_one()
        unit, message = self._issue_medal_rack_unit('l')
        return self._issue_notification(message, title=_('Tunic Medal Rack Issued'))

    def action_issue_meskit_medal_rack(self):
        self.ensure_one()
        unit, message = self._issue_medal_rack_unit('s')
        return self._issue_notification(message, title=_('Meskit Medal Rack Issued'))

    def _issue_ribbon_rack_unit(self):
        """Full stock-aware resolution cascade for handing this person a Ribbon Rack:

        1. If a complete Rack is in stock (actual product stock) → allocate it, no MOs created.
        2. If no complete Rack in stock:
           a. For each Line (row), check actual product stock quantity
           b. If stock < needed, manufacture ONLY the shortage
           c. If stock >= needed, use stock (no MO)
           d. Always manufacture the Rack assembly (unless a complete rack was found)
        """
        self.ensure_one()
        RackLine = self.env['rm.rack.line']
        RackProduct = self.env['rm.rack.product']
        rows = self._get_rack_rows()
        if not rows:
            raise UserError(_(
                '%s has no acquisitions on the Acquisition Ledger to build a ribbon rack for.'
            ) % self.display_name)

        exact_line_ids = []
        for row in rows:
            key = RackLine._key_for_award_ids(row.ids)
            line = RackLine.search([('identity_key', '=', key)], limit=1)
            if not line:
                exact_line_ids = None
                break
            exact_line_ids.append(line.id)

        if exact_line_ids:
            rack_key = RackProduct._key_for_line_ids(exact_line_ids)
            rack = RackProduct.search([('identity_key', '=', rack_key)], limit=1)
            if rack:
                rack._ensure_product()
                available_quantity = rack.get_available_stock_quantity()
                if available_quantity >= 1:
                    available_unit = rack.get_stock_units(1)
                    if available_unit:
                        available_unit.action_deliver(self.id)
                        rack.record_usage()
                        return available_unit, _(
                            'Handed over an existing Rack Product #%(id)s from stock (%(identity)s). '
                            'No manufacturing orders were created.'
                        ) % {'id': rack.id, 'identity': rack.display_identity}

        resolved_line_ids = []
        total_lines_manufactured = 0

        for row in rows:
            award_ids = row.ids
            exact_line = RackLine.get_or_create(award_ids)
            exact_line._ensure_product()
            needed = 1
            available_quantity = exact_line.get_available_stock_quantity()

            if available_quantity >= needed:
                exact_line.consume_stock_units(needed, self.display_name)
            else:
                if available_quantity > 0:
                    exact_line.consume_stock_units(int(available_quantity), self.display_name)
                shortage = needed - int(available_quantity)
                if shortage > 0:
                    new_units = exact_line.manufacture_units(shortage)
                    for unit in new_units:
                        unit.write({
                            'state': 'consumed',
                            'consumed_note': _('Used for %s') % self.display_name,
                        })
                    total_lines_manufactured += shortage

            exact_line.record_usage()
            resolved_line_ids.append(exact_line.id)

        rack = RackProduct.get_or_create(resolved_line_ids)
        rack._ensure_product()

        available_rack_quantity = rack.get_available_stock_quantity()
        if available_rack_quantity >= 1:
            available_unit = rack.get_stock_units(1)
            if available_unit:
                available_unit.action_deliver(self.id)
                rack.record_usage()

                if total_lines_manufactured == 0:
                    return available_unit, _(
                        'Used existing lines from stock and allocated an existing Rack Product #%(id)s from stock. '
                        'No manufacturing orders were created.'
                    ) % {'id': rack.id}
                else:
                    return available_unit, _(
                        'Manufactured %(count)d line unit(s) and allocated an existing Rack Product #%(id)s from stock.'
                    ) % {'count': total_lines_manufactured, 'id': rack.id}

        new_rack_unit = rack.manufacture_unit(reserved_person_id=self.id)
        rack.record_usage()

        if total_lines_manufactured == 0:
            return new_rack_unit, _(
                'Used all required lines from stock and manufactured a new Rack Product #%(id)s for %(name)s. '
                'Only the rack assembly MO was created (no line MOs).'
            ) % {'id': rack.id, 'name': self.display_name}
        else:
            return new_rack_unit, _(
                'Manufactured %(count)d line unit(s) (shortage from stock) and assembled a new Rack Product #%(id)s for %(name)s. '
                'Created MOs for %(count)d line(s) and the rack assembly.'
            ) % {'count': total_lines_manufactured, 'id': rack.id, 'name': self.display_name}

    def _medal_rack_label(self, size):
        return _('Tunic Medal Rack') if size == 'l' else _('Meskit Medal Rack')

    def _issue_medal_rack_unit(self, size):
        """Full stock-aware resolution cascade for handing this person a
        Medal Rack (size 'l' = Tunic, 's' = Meskit)."""
        self.ensure_one()
        MedalPart = self.env['rm.medal.part']
        MedalRack = self.env['rm.medal.rack']
        label = self._medal_rack_label(size)
        awards = self._get_medal_rack_awards(size)
        if not awards:
            raise UserError(_(
                '%(person)s has no medal-eligible acquisitions on the Acquisition '
                'Ledger flagged for a %(label)s.'
            ) % {'person': self.display_name, 'label': label})
        award_ids = awards.ids

        part_key = MedalPart._key_for_award_ids(award_ids, size)
        existing_part = MedalPart.search([('identity_key', '=', part_key)], limit=1)
        if existing_part:
            rack = MedalRack.search([('identity_key', '=', existing_part.identity_key)], limit=1)
            if rack:
                rack._ensure_product()
                available_quantity = rack.get_available_stock_quantity()
                if available_quantity >= 1:
                    available_unit = rack.get_stock_units(1)
                    if available_unit:
                        available_unit.action_deliver(self.id)
                        rack.record_usage()
                        return available_unit, _(
                            'Handed over an existing %(label)s #%(id)s from stock (%(identity)s). '
                            'No manufacturing orders were created.'
                        ) % {'label': label, 'id': rack.id, 'identity': rack.display_identity}

        part = MedalPart.get_or_create(award_ids, size)
        part._ensure_product()

        needed = 1
        part_manufactured = 0
        available_quantity = part.get_available_stock_quantity()
        if available_quantity >= needed:
            part.consume_stock_units(needed, self.display_name)
        else:
            if available_quantity > 0:
                part.consume_stock_units(int(available_quantity), self.display_name)
            shortage = needed - int(available_quantity)
            if shortage > 0:
                new_units = part.manufacture_units(shortage)
                for unit in new_units:
                    unit.write({
                        'state': 'consumed',
                        'consumed_note': _('Used for %s') % self.display_name,
                    })
                part_manufactured = shortage
        part.record_usage()

        rack = MedalRack.get_or_create(part.id)
        rack._ensure_product()

        available_rack_quantity = rack.get_available_stock_quantity()
        if available_rack_quantity >= 1:
            available_unit = rack.get_stock_units(1)
            if available_unit:
                available_unit.action_deliver(self.id)
                rack.record_usage()

                if part_manufactured == 0:
                    return available_unit, _(
                        'Used the existing medal part from stock and allocated an existing '
                        '%(label)s #%(id)s from stock. No manufacturing orders were created.'
                    ) % {'label': label, 'id': rack.id}
                else:
                    return available_unit, _(
                        'Manufactured a new medal part and allocated an existing '
                        '%(label)s #%(id)s from stock.'
                    ) % {'label': label, 'id': rack.id}

        new_rack_unit = rack.manufacture_unit(reserved_person_id=self.id)
        rack.record_usage()

        if part_manufactured == 0:
            return new_rack_unit, _(
                'Used the existing medal part from stock and manufactured a new %(label)s '
                '#%(id)s for %(name)s. Only the rack assembly MO was created (no part MO).'
            ) % {'label': label, 'id': rack.id, 'name': self.display_name}
        else:
            return new_rack_unit, _(
                'Manufactured a new medal part (shortage from stock) and assembled a new '
                '%(label)s #%(id)s for %(name)s. Created MOs for the part and the rack assembly.'
            ) % {'label': label, 'id': rack.id, 'name': self.display_name}

    def _issue_notification(self, message, title=None):
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': title or _('Ribbon Rack Issued'),
                'message': message,
                'type': 'success',
                'sticky': False,
            },
        }

    def action_copy_ledger_to_custom(self):
        """Snapshot this person's current Acquisition Ledger into their
        Customised Ledger (rm.acquisition.custom) - a real, editable copy
        that won't change on its own afterwards."""
        self.ensure_one()
        self.env['rm.acquisition.custom'].copy_from_ledger(self)
        return {
            'type': 'ir.actions.act_window',
            'name': 'Customised Ledger',
            'res_model': 'rm.acquisition.custom',
            'view_mode': 'list,form',
            'domain': [('person_id', '=', self.id)],
            'context': {'default_person_id': self.id},
        }

    def rm_rack_label(self):
        """"Person" text used in every rack sale-order-line's own
        description (e.g. "(For: Md. Karim - 9901234563)") - includes
        ID Number, when set, so two people sharing a name are still
        distinguishable on the order/quotation printout."""
        self.ensure_one()
        if self.id_number:
            return _('%s - %s') % (self.display_name, self.id_number)
        return self.display_name

    def action_select_for_rack_wizard(self):
        """Row button on rm.sale.line.person.wizard's result list -
        writes this Person back onto whichever wizard opened it and
        reopens that same wizard so the pick shows immediately."""
        self.ensure_one()
        wizard_id = self.env.context.get('rack_wizard_id')
        wizard = self.env['rm.sale.line.person.wizard'].browse(wizard_id) if wizard_id else None
        if wizard and wizard.exists():
            wizard.person_id = self.id
        return {
            'type': 'ir.actions.act_window',
            'res_model': 'rm.sale.line.person.wizard',
            'res_id': wizard_id,
            'view_mode': 'form',
            'target': 'new',
        }
