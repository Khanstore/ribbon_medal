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
        for person in self:
            person.rank_seniority_level = person.rank_id.seniority_level or 0

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
    rack_total_price = fields.Float(
        string='Ribbon Rack Price', compute='_compute_rack_total_price',
        help='Sum of each acquired ribbon product\'s list price, plus '
             "each acquisition's attachment device product's list price "
             '(when one is set).')
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
                        (today.month, today.day) < (person.service_confirmation_date.month,
                                                    person.service_confirmation_date.day))
            else:
                person.service_age = 0

    @api.depends('retirement_date')
    def _compute_is_retired(self):
        today = fields.Date.today()
        for person in self:
            person.is_retired = bool(person.retirement_date and person.retirement_date <= today)

    def _compute_award_count(self):
        # Counts from the consolidated Acquisition Ledger (Personal Awards +
        # Missions + Seniority, minus Excluded) rather than just
        # obtained_awards_ids, since that ledger is the actual source of
        # truth for "what has this person acquired" now. Not stored: it's
        # backed by a SQL view (rm.acquisition), so compute dependencies
        # can't track it - it's cheap enough to recompute on read.
        Acquisition = self.env['rm.acquisition']
        for person in self:
            person.award_count = Acquisition.search_count([('person_id', '=', person.id)])

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

    def _compute_rack_ledger_ids(self):
        # Same underlying data as obtained_awards_ids, but keeps the full
        # rm.acquisition rows (not just the distinct award_id set) - the
        # Ribbon Rack widget needs this so it can show each acquisition's
        # OWN attachment_id (the specific device this person received),
        # rather than rm.prb's static, award-type-level attachment.
        Acquisition = self.env['rm.acquisition']
        for person in self:
            person.rack_ledger_ids = Acquisition.search([('person_id', '=', person.id)])

    def _compute_rack_total_price(self):
        Acquisition = self.env['rm.acquisition']
        for person in self:
            acquisitions = Acquisition.search([('person_id', '=', person.id)])
            person.rack_total_price = (
                    sum(acquisitions.mapped('ribbon_list_price'))
                    + sum(acquisitions.mapped('attachment_list_price'))
            )

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
                joinng_year = (2000 + joining_year_val) if (0 <= joining_year_val <= current_yr) else (
                            1900 + joining_year_val)

                # Set birth_date to Jan 1st of that year
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

    def action_issue_ribbon_rack(self):
        """UI button: run the cascade and show a notification describing
        what happened. See _issue_ribbon_rack_unit() for the underlying
        logic and its return value, used programmatically elsewhere
        (e.g. by sale.order.action_confirm())."""
        self.ensure_one()
        unit, message = self._issue_ribbon_rack_unit()
        return self._issue_notification(message)

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

        # Step 1: Check for complete rack in stock (actual product stock)
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
                # Check actual product stock for this rack
                rack._ensure_product()  # Ensure product exists before checking stock
                available_quantity = rack.get_available_stock_quantity()
                if available_quantity >= 1:
                    # Complete rack found in stock - just allocate it
                    available_unit = rack.get_stock_units(1)
                    if available_unit:
                        available_unit.action_deliver(self.id)
                        rack.record_usage()
                        return available_unit, _(
                            'Handed over an existing Rack Product #%(id)s from stock (%(identity)s). '
                            'No manufacturing orders were created.'
                        ) % {'id': rack.id, 'identity': rack.display_identity}

        # Step 2: No complete rack in stock - resolve each line with quantity awareness
        resolved_line_ids = []
        total_lines_manufactured = 0

        for row in rows:
            award_ids = row.ids
            exact_line = RackLine.get_or_create(award_ids)

            # Ensure the line has a product
            exact_line._ensure_product()

            # Check how many units we need (1 for each row/line)
            needed = 1

            # Get available stock for this exact line (actual product stock)
            available_quantity = exact_line.get_available_stock_quantity()

            if available_quantity >= needed:
                # We have enough stock - use it
                exact_line.consume_stock_units(needed, self.display_name)
            else:
                # Not enough stock - use what we have and manufacture the rest
                if available_quantity > 0:
                    # Use existing stock first
                    exact_line.consume_stock_units(int(available_quantity), self.display_name)

                # Manufacture the shortage
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

        # Step 3: Assemble the rack
        rack = RackProduct.get_or_create(resolved_line_ids)

        # Ensure rack has a product
        rack._ensure_product()

        # Check if we have a rack in stock (actual product stock)
        available_rack_quantity = rack.get_available_stock_quantity()
        if available_rack_quantity >= 1:
            # Found a rack in stock - allocate it
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

        # No rack in stock - manufacture it
        new_rack_unit = rack.manufacture_unit(reserved_person_id=self.id)
        rack.record_usage()

        # Build a detailed message
        if total_lines_manufactured == 0:
            # All lines came from stock, but no complete rack existed
            return new_rack_unit, _(
                'Used all required lines from stock and manufactured a new Rack Product #%(id)s for %(name)s. '
                'Only the rack assembly MO was created (no line MOs).'
            ) % {'id': rack.id, 'name': self.display_name}
        else:
            return new_rack_unit, _(
                'Manufactured %(count)d line unit(s) (shortage from stock) and assembled a new Rack Product #%(id)s for %(name)s. '
                'Created MOs for %(count)d line(s) and the rack assembly.'
            ) % {'count': total_lines_manufactured, 'id': rack.id, 'name': self.display_name}

    def _issue_notification(self, message):
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('Ribbon Rack Issued'),
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

    def action_select_for_rack_wizard(self):
        """Row button on rm.sale.line.person.wizard's result list -
        writes this Person back onto whichever wizard opened it (passed
        via context) and reopens that same wizard so the pick shows
        immediately. UI glue only, not meant to be called elsewhere."""
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