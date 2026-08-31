# -*- coding: utf-8 -*-
from odoo import _, api, fields, models
from odoo.exceptions import UserError
from odoo.osv import expression
from datetime import date, datetime


class ResPerson(models.Model):
    """Personnel record.

    Uses delegation inheritance (`_inherits`) rather than classical
    inheritance (`_name` + `_inherit` on the same parent) on purpose:
    `res.partner` carries many2many fields (e.g. `channel_ids` from the
    `mail`/`discuss` modules) that are declared with an explicit, fixed
    relation table name. Classical inheritance blindly copies those field
    definitions onto the new model, so both `res.partner` and `res.person`
    would end up pointing at the exact same relation table/columns, which
    Odoo rejects at registry setup time ("use the same table and columns").

    Delegation inheritance avoids this entirely: partner fields are
    accessed by reference through `partner_id`, never redeclared as new
    columns on `res.person`, so there is no collision risk.

    We additionally mix in `mail.thread` / `mail.activity.mixin` directly
    (rather than relying on the delegated, partner-owned chatter fields) so
    that personnel records have their own independent message/activity
    stream. This is safe to combine with `_inherits`: these mixins only add
    domain-filtered One2many fields (`message_ids`, `message_follower_ids`,
    `activity_ids`), not fixed-relation-table many2many fields, so there is
    no naming/table collision with the delegated partner fields.
    """
    _name = 'res.person'
    _inherits = {'res.partner': 'partner_id'}
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _description = 'Personnel Record'
    _order = 'name'

    partner_id = fields.Many2one(
        'res.partner', string='Related Partner', required=True,
        ondelete='cascade', auto_join=True, index=True)

    _sql_constraints = [
        ('partner_id_uniq', 'unique(partner_id)',
         'A Personnel record already exists for this Contact - open that '
         'one instead of creating another.'),
    ]

    def copy(self, default=None):
        """Duplicating a Person must not point the copy at the same
        Contact - that would collide with the uniqueness constraint
        above. Give the copy its own duplicated Contact instead, the
        same way res.users handles this for its own partner_id."""
        self.ensure_one()
        default = dict(default or {})
        if 'partner_id' not in default:
            default['partner_id'] = self.partner_id.copy().id
        return super().copy(default)

    id_number = fields.Char(string='ID Number', index=True)
    rank_id = fields.Many2one('rm.ranks', string='Rank', ondelete='restrict')
    rank_seniority_level = fields.Integer(
        string='Rank Seniority Level', related='rank_id.seniority_level',
        store=True, readonly=True,
        help='Mirrors the seniority_level of the selected rank; used to '
             "restrict Current Workplace choices to units whose chief's "
             'rank is senior enough.')

    @api.model
    def _name_search(self, name='', domain=None, operator='ilike', limit=None, order=None):
        """Extend the default (name-only) search used by every Many2one
        field/search widget for this model - e.g. the "Selected Person"
        field on the Order Ribbon Rack wizard - to also match on ID
        Number, Phone, Mobile, and Email, not just Name."""
        domain = list(domain or [])
        if name:
            name_domain = ['|', '|', '|', '|',
                            ('name', operator, name),
                            ('id_number', operator, name),
                            ('phone', operator, name),
                            ('mobile', operator, name),
                            ('email', operator, name)]
            domain = expression.AND([domain, name_domain])
            return self._search(domain, limit=limit, order=order)
        return super()._name_search(name=name, domain=domain, operator=operator, limit=limit, order=order)

    current_workplace = fields.Many2one(
        'rm.unit', string='Current Workplace', ondelete='restrict',
        domain="[('level', '>=', rank_seniority_level)]",
        help='Restricted to units whose chief has a seniority level at or '
             "above this person's own rank, so personnel cannot be posted "
             "somewhere their rank outranks the unit's chief.")
    bcs_batch = fields.Many2one('rm.bcs.batch',string='BCS Batch')
    service_confirmation_date = fields.Date(string='Service Confirmation Date')

    obtained_awards_ids = fields.Many2many(
        'rm.prb', string='Obtained Awards', compute='_compute_obtained_awards_ids')
    rack_ledger_ids = fields.Many2many(
        'rm.acquisition', string='Ribbon Rack Ledger', compute='_compute_rack_ledger_ids',
        help='Same acquisitions as obtained_awards_ids, but keeping each '
             "row's own attachment_id (the specific device received at "
             'that acquisition) for the Ribbon Rack widget to display.')
    award_count = fields.Integer(compute='_compute_award_count')
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
        for person in self:
            if person.birth_date:
                person.age = today.year - person.birth_date.year - (
                    (today.month, today.day) < (person.birth_date.month, person.birth_date.day))
            else:
                person.age = 0

    @api.depends('service_confirmation_date')
    def _compute_service_age(self):
        today = fields.Date.today()
        for person in self:
            if person.service_confirmation_date:
                person.service_age = today.year - person.service_confirmation_date.year - (
                    (today.month, today.day) < (person.service_confirmation_date.month, person.service_confirmation_date.day))
            else:
                person.service_age = 0

    @api.depends('retirement_date')
    def _compute_is_retired(self):
        today = fields.Date.today()
        for person in self:
            person.is_retired = bool(person.retirement_date and person.retirement_date <= today)

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
        # Counts from the consolidated Acquisition Ledger (Personal Awards +
        # Missions + Seniority, minus Excluded) rather than just
        # obtained_awards_ids, since that ledger is the actual source of
        # truth for "what has this person acquired" now. The ledger itself
        # is a SQL view (rm.acquisition) so it's always re-queried fresh on
        # read; @api.depends above is what tells Odoo WHEN that re-query is
        # actually needed (see the class-level comment).
        Acquisition = self.env['rm.acquisition']
        for person in self:
            person.award_count = Acquisition.search_count([('person_id', '=', person.id)])

    @api.depends(*_LEDGER_DEPENDS)
    def _compute_obtained_awards_ids(self):
        # Derived live from the Acquisition Ledger (same source as
        # award_count above), not a separately-maintained many2many - so
        # the Ribbon Rack always reflects what's actually in the ledger
        # (Personal Awards + Missions + Seniority + Batch, minus Excluded)
        # instead of requiring duplicate manual assignment.
        Acquisition = self.env['rm.acquisition']
        for person in self:
            acquisitions = Acquisition.search([('person_id', '=', person.id)])
            person.obtained_awards_ids = acquisitions.mapped('award_id')

    @api.depends(*_LEDGER_DEPENDS)
    def _compute_rack_ledger_ids(self):
        # Same underlying data as obtained_awards_ids, but keeps the full
        # rm.acquisition rows (not just the distinct award_id set) - the
        # Ribbon Rack widget needs this so it can show each acquisition's
        # OWN attachment_id (the specific device this person received),
        # rather than rm.prb's static, award-type-level attachment.
        Acquisition = self.env['rm.acquisition']
        for person in self:
            person.rack_ledger_ids = Acquisition.search([('person_id', '=', person.id)])

    @api.depends(*_LEDGER_DEPENDS)
    def _compute_rack_total_price(self):
        Acquisition = self.env['rm.acquisition']
        for person in self:
            acquisitions = Acquisition.search([('person_id', '=', person.id)])
            person.rack_total_price = (
                sum(acquisitions.mapped('ribbon_list_price'))
                + sum(acquisitions.mapped('attachment_list_price'))
            )

    @api.depends(*_LEDGER_DEPENDS)
    def _compute_medal_rack_prices(self):
        Acquisition = self.env['rm.acquisition']
        for person in self:
            medal_acquisitions = Acquisition.search([
                ('person_id', '=', person.id), ('is_medal', '=', True),
            ])
            tunic = medal_acquisitions.filtered('add_to_big_medal')
            meskit = medal_acquisitions.filtered('add_to_mini_medal')
            person.tunic_medal_rack_price = (
                    sum(tunic.mapped('medal_list_price')) + sum(tunic.mapped('attachment_list_price'))
            )
            person.meskit_medal_rack_price = (
                    sum(meskit.mapped('medal_list_price')) + sum(meskit.mapped('attachment_list_price'))
            )

    @api.model
    def get_rack_widget_context(self, person_id, force_id, prb_ids):
        """RPC endpoint for the Ribbon/Medal Rack widgets' client-side
        (JavaScript) INSTANT ledger computation - see
        static/src/js/rack_ledger.js.

        rm.acquisition is a read-only SQL VIEW, so it only ever
        reflects committed data - editing the Award/Mission tabs on an
        open, unsaved form has no effect on it until the record is
        actually saved. To give instant feedback without a Save, the
        JS widgets replicate rm.acquisition's own merge/filter logic
        themselves, fed by the form's own live (possibly unsaved)
        Personal Award / Mission rows. This method supplies the two
        ingredients that can't be read off the open form at all:

        - The Seniority/Batch `rm.prb` rules for `force_id` (these
          aren't edited via any one2many on this form - they're
          derived purely from force_id + service_confirmation_date).
        - This person's currently active award exclusions, as
          decoration ids (`rm.excluded.awards` isn't edited on this
          form either).

        Also returns the display/eligibility attributes for every
        given `prb_ids` (the awards actually referenced by the
        Personal Award / Mission rows on the open form right now), so
        the widgets don't need a second RPC just to resolve those.

        MAINTENANCE WARNING: kept in sync with rm.acquisition's SQL
        view BY HAND - if that view's logic changes, this must change
        too. See rm.acquisition's own docstring for the authoritative
        rules being mirrored here.
        """
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
            # Correct approach using env.ref()
            # Ensure you check if the record exists to avoid errors if the module is uninstalled
            force_id_record = self.env.ref('ribbon_medal.force_police', raise_if_not_found=False)

            if record.id_number and len(record.id_number) == 10 and record.force_id == force_id_record:
                current_yr = int(datetime.now().strftime('%y'))
                birth_yr_str = record.id_number[0:2]
                joining_yr_str = record.id_number[2:4]

                # Logic to determine full year
                birth_year_val = int(birth_yr_str)
                joining_year_val = int(joining_yr_str)
                birth_year = (2000 + birth_year_val) if (0 <= birth_year_val <= current_yr) else (1900 + birth_year_val)
                joinng_year = (2000 + joining_year_val) if (0 <= joining_year_val <= current_yr) else (1900 + joining_year_val)


                # Set birth_date to Jan 1st of that year
                record.birth_date = date(birth_year, 1, 1)
                record.service_confirmation_date = date(joinng_year, 1, 1)
            else:
                record.birth_date = False
                record.service_confirmation_date  = False

    def get_sorted_awards(self):
        """Return obtained awards sorted for Ribbon Rack display: lowest
        `sequence` first (highest precedence, destined for the
        bottom-right position)."""
        self.ensure_one()
        return self.obtained_awards_ids.sorted(key=lambda decoration: decoration.sequence)

    def action_view_awards(self):
        """Smart-button action: open this person's consolidated Acquisition
        Ledger entries (Personal Awards + Missions + Seniority, minus
        Excluded) - not the full rm.decoration decoration catalog."""
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': 'Awards',
            'res_model': 'rm.acquisition',
            'view_mode': 'list',
            'domain': [('person_id', '=', self.id)],
        }

    def action_generate_ribbon_rack(self):
        """Find or create this person's rm.set.order, then open the wizard
        to pick a quantity and generate the Manufacturing Order. This is
        the manual/direct path - always builds a fresh generic Ribbon
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
        Ribbon Rack widget's own layout exactly (see the `rows` getter in
        static/src/js/ribbon_rack.js): sorted by descending `sequence`
        (highest precedence first), split into a top partial row (the
        remainder) then full rows of RACK_COLUMNS, each already
        left-to-right. Returns a list of rm.prb recordsets, top row
        first - these are exactly the "Lines" a Rack is made of."""
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
        Medal Rack size ('l' = Tunic, 's' = Meskit), as an ORDERED
        rm.prb recordset - highest precedence (descending sequence)
        first, same ordering rule _get_rack_rows uses before splitting
        into rows. Unlike Ribbon Rack, there's no row-splitting here:
        medals mount individually (see rm.medal.part's docstring), so
        this flat, ordered list of awards IS the rack's identity.

        Only acquisitions flagged is_medal AND the size-appropriate
        add_to_big_medal/add_to_mini_medal flag are included."""
        self.ensure_one()
        flag_field = 'add_to_big_medal' if size == 'l' else 'add_to_mini_medal'
        acquisitions = self.env['rm.acquisition'].search([
            ('person_id', '=', self.id),
            ('is_medal', '=', True),
            (flag_field, '=', True),
        ])
        sorted_acquisitions = acquisitions.sorted(key=lambda a: a.sequence, reverse=True)
        return sorted_acquisitions.mapped('award_id')

    def action_issue_ribbon_rack(self):
        """UI button: run the cascade and show a notification describing
        what happened. See _issue_ribbon_rack_unit() for the underlying
        logic and its return value, used programmatically elsewhere
        (e.g. by sale.order.action_confirm())."""
        self.ensure_one()
        unit, message = self._issue_ribbon_rack_unit()
        return self._issue_notification(message)

    def action_issue_tunic_medal_rack(self):
        """UI button: same idea as action_issue_ribbon_rack, for the
        Tunic (large-size) Medal Rack. See _issue_medal_rack_unit()."""
        self.ensure_one()
        unit, message = self._issue_medal_rack_unit('l')
        return self._issue_notification(message, title=_('Tunic Medal Rack Issued'))

    def action_issue_meskit_medal_rack(self):
        """UI button: same idea as action_issue_ribbon_rack, for the
        Meskit (small-size) Medal Rack. See _issue_medal_rack_unit()."""
        self.ensure_one()
        unit, message = self._issue_medal_rack_unit('s')
        return self._issue_notification(message, title=_('Meskit Medal Rack Issued'))

    def _issue_ribbon_rack_unit(self):
        """Full stock-aware resolution cascade for handing this person a
        Ribbon Rack:

        1. Exact-match unreserved Rack Product stock already assembled
           for this exact combination of rows -> hand it straight over,
           nothing else happens.
        2. Otherwise, resolve each row (Line) independently: exact Line
           stock -> trim-substitute from a longer in-stock Line (fully
           consuming it) -> create a brand new Line and manufacture it
           from raw materials.
        3. Assemble/manufacture exactly one unit of the (now identified,
           and if new, permanently identity-locked) Rack Product,
           reserved for this person - assembling rows into a rack is a
           real step even when every row came straight from stock, so
           this only skips entirely when step 1 already found a
           fully pre-built rack.

        Returns (rm.rack.unit, message) - the resulting/handed-over unit
        (already delivered in the step-1 case, still reserved/pending
        delivery otherwise) and a human-readable description of what
        happened.
        """
        self.ensure_one()
        RackLine = self.env['rm.rack.line']
        RackProduct = self.env['rm.rack.product']
        rows = self._get_rack_rows()
        if not rows:
            raise UserError(_(
                '%s has no acquisitions on the Acquisition Ledger to build a ribbon rack for.'
            ) % self.display_name)

        # Step 1: is there already a Rack Product for this EXACT
        # combination of already-known Lines, with unreserved stock?
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
                available_unit = self.env['rm.rack.unit'].search([
                    ('rack_id', '=', rack.id),
                    ('state', '=', 'in_stock'),
                    ('reserved_person_id', '=', False),
                ], limit=1)
                if available_unit:
                    available_unit.action_deliver(self.id)
                    rack.record_usage()
                    return available_unit, _(
                        'Handed over an existing Rack Product #%(id)s from stock (%(identity)s).'
                    ) % {'id': rack.id, 'identity': rack.display_identity}

        # Step 2: resolve each row independently.
        resolved_line_ids = []
        for row in rows:
            award_ids = row.ids
            match_line, match_unit = RackLine.find_best_stock_match(award_ids)
            exact_line = RackLine.get_or_create(award_ids)
            if match_line and match_unit:
                match_unit.write({
                    'state': 'consumed',
                    'consumed_note': _('Used for %s') % self.display_name,
                })
            else:
                new_unit = exact_line.manufacture_unit()
                new_unit.write({
                    'state': 'consumed',
                    'consumed_note': _('Used for %s') % self.display_name,
                })
            exact_line.record_usage()
            resolved_line_ids.append(exact_line.id)

        # Step 3: assemble/manufacture the rack itself, reserved for this person.
        rack = RackProduct.get_or_create(resolved_line_ids)
        new_rack_unit = rack.manufacture_unit(reserved_person_id=self.id)
        rack.record_usage()
        return new_rack_unit, _(
            'No ready-made rack matched exactly - assembled and reserved a new '
            'unit of Rack Product #%(id)s for %(name)s.'
        ) % {'id': rack.id, 'name': self.display_name}

    def _medal_rack_label(self, size):
        return _('Tunic Medal Rack') if size == 'l' else _('Meskit Medal Rack')

    def _issue_medal_rack_unit(self, size):
        """Full stock-aware resolution cascade for handing this person a
        Medal Rack (size 'l' = Tunic, 's' = Meskit). Unlike Ribbon
        Rack's cascade, which resolves several Lines (one per row) and
        then combines them into a Rack, there is only ONE Medal Part
        to resolve here - it already covers this person's whole
        medal-eligible combination (see rm.medal.part's docstring) -
        so this is a simpler 2-step version of the same idea:

        1. If a complete Medal Rack is in stock for this exact combination
           → allocate it, no MOs created.
        2. If not:
           a. Resolve the one Medal Part for this combination (stock-aware:
              use what's in stock, manufacture only the shortage)
           b. Manufacture the Rack assembly (unless a complete rack was found)
        """
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

        # Step 1: Check for a complete rack in stock (exact combination/size match)
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

        # Step 2: No complete rack in stock - resolve the one Medal Part
        # (stock-aware: use what's in stock, manufacture only the shortage)
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

        # Step 3: Assemble the rack around this Part
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

        # No rack in stock - manufacture it
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
                'sticky': True,
            },
        }

    def action_copy_ledger_to_custom(self):
        """Snapshot this person's current Acquisition Ledger into their
        Customised Ledger (rm.acquisition.custom) - a real, editable copy
        that won't change on its own afterwards. Safe to click more than
        once: it only adds rows not already present, never touches
        existing customisations."""
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
