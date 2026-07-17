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
        # domain="[('level_id.chief_id.seniority_level', '>=', rank_seniority_level)]",
        help='Restricted to units whose category chief has a seniority '
             "level at or above this person's own rank, so personnel "
             "cannot be posted somewhere their rank outranks the unit's "
             'designated chief.')
    bcs_batch = fields.Many2one('rm.bcs.batch',string='BCS Batch')
    service_confirmation_date = fields.Date(string='Service Confirmation Date')

    obtained_awards_ids = fields.Many2many(
        'rm.prb', 'rm_prb_res_person_rel', 'person_id', 'prb_id',
        string='Obtained Awards')
    award_count = fields.Integer(compute='_compute_award_count', store=True)
    force_id = fields.Many2one(
        'rm.forces', string='Force', related='rank_id.force_id', store=True, readonly=True)
    birth_date = fields.Date(string="Birth Date")
    retirement_date = fields.Date(string="Retirement Date")

    @api.depends('obtained_awards_ids')
    def _compute_award_count(self):
        for person in self:
            person.award_count = len(person.obtained_awards_ids)

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
        return self.obtained_awards_ids.sorted(key=lambda prb: prb.seniority_sequence, reverse=True)

    def action_view_awards(self):
        """Smart-button action: open this person's obtained awards in a
        standalone list/form, filtered by domain."""
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': 'Awards',
            'res_model': 'rm.prb',
            'view_mode': 'list,form',
            'domain': [('id', 'in', self.obtained_awards_ids.ids)],
            'context': {'default_person_ids': [(4, self.id)]},
        }
