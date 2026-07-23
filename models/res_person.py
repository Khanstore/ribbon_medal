# -*- coding: utf-8 -*-
from odoo import api, fields, models
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

    id_number = fields.Char(string='ID Number', index=True)
    rank_id = fields.Many2one('rm.ranks', string='Rank', ondelete='restrict')
    rank_seniority_level = fields.Integer(
        string='Rank Seniority Level', related='rank_id.seniority_level',
        store=True, readonly=True,
        help='Mirrors the seniority_level of the selected rank; used to '
             "restrict Current Workplace choices to units whose chief's "
             'rank is senior enough.')
    current_workplace = fields.Many2one(
        'rm.unit', string='Current Workplace', ondelete='restrict',
        domain="[('level', '>=', rank_seniority_level)]",
        help='Restricted to units whose chief has a seniority level at or '
             "above this person's own rank, so personnel cannot be posted "
             "somewhere their rank outranks the unit's chief.")
    bcs_batch = fields.Many2one('rm.bcs.batch',string='BCS Batch')
    service_confirmation_date = fields.Date(string='Service Confirmation Date')

    obtained_awards_ids = fields.Many2many(
        'rm.prb', 'rm_prb_res_person_rel', 'person_id', 'prb_id',
        string='Obtained Awards')
    award_count = fields.Integer(compute='_compute_award_count')
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

    def _compute_award_count(self):
        # Counts from the consolidated Acquisition Ledger (Personal Awards +
        # Missions + Seniority, minus Excluded) rather than just
        # obtained_awards_ids, since that ledger is the actual source of
        # truth for "what has this person acquired" now. Not stored: it's
        # backed by a SQL view (rm.acquisition), so compute dependencies
        # can't track it - it's cheap enough to recompute on read.
        # Acquisition = self.env['rm.acquisition']
        for person in self:
            person.award_count =6 # Acquisition.search_count([('person_id', '=', person.id)])

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
        """Return obtained awards sorted for Ribbon Rack display: highest
        seniority_sequence first (destined for the bottom-right position)."""
        self.ensure_one()
        return self.obtained_awards_ids.sorted(key=lambda decoration: decoration.seniority_sequence, reverse=True)

    def action_view_awards(self):
        """Smart-button action: open this person's consolidated Acquisition
        Ledger entries (Personal Awards + Missions + Seniority, minus
        Excluded) - not the full rm.decoration decoration catalog."""
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': 'Awards',
            'res_model': 'rm.personal.awards',
            'view_mode': 'list',
            'domain': [('person_id', '=', self.id)],
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
