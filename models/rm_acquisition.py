# -*- coding: utf-8 -*-
from odoo import fields, models,  api,tools
from datetime import date, datetime
from odoo.exceptions import ValidationError

class postingMissions(models.Model):
    """Mission record record."""
    _name = 'rm.mission.posting'
    _description = 'all Special posting and missions are listed here'
    _rec_name = 'mission_id'
    mission_id = fields.Many2one('rm.prb',string='Award Name')
    person_id=fields.Many2one('res.person',string='Person')
    award_year = fields.Integer(string='Award Date')
    attachment_id = fields.Many2one('rm.attachment',string='Attachment')
    note = fields.Char(string='note')
    active = fields.Boolean(default=True)
    add_to_ribbon = fields.Boolean(string="Tunic ribbon",default=True)
    add_to_big_medal = fields.Boolean(string="Tunic Medal",default=True)
    add_to_mini_medal = fields.Boolean(string="Mini Medal",default=True)

    @api.constrains('award_year')
    def _check_award_year(self):
        current_year = date.today().year
        for record in self:
            if record.award_year and (record.award_year < 1900 or record.award_year > current_year):
                raise ValidationError(f"The year must be between 1900 and {current_year}.")

class personalAwards(models.Model):
    """Award record record."""
    _name = 'rm.personal.awards'
    _description = 'all achievement and award listed here'
    _rec_name = 'award_id'
    award_id = fields.Many2one('rm.prb',string='Award Name')
    person_id=fields.Many2one('res.person',string='Person')
    award_year = fields.Integer(string='Award Date')
    attachment_id = fields.Many2one('rm.attachment',string='Attachment')
    note = fields.Char(string='note')
    active = fields.Boolean(default=True)
    add_to_ribbon = fields.Boolean(string="Tunic ribbon",default=True)
    add_to_big_medal = fields.Boolean(string="Tunic Medal",default=True)
    add_to_mini_medal = fields.Boolean(string="Mini Medal",default=True)

    @api.constrains('award_year')
    def _check_award_year(self):
        current_year = date.today().year
        for record in self:
            if record.award_year and (record.award_year < 1900 or record.award_year > current_year):
                raise ValidationError(f"The year must be between 1900 and {current_year}.")

class RmAcquisition(models.Model):
    """Read-only, consolidated ledger of every award a person has actually
    acquired, combining four sources:

    * Personal Awards (`rm.personal.awards`) - individually entered.
    * Missions (`rm.mission.posting`) - individually entered.
    * Seniority (derived): any `rm.prb` whose `rule_category_id` is
      'seniority', for the person's own force, where the PRB's required
      `service_age` is at or below the person's actual years of service
      (computed from `service_confirmation_date`).
    * Batch (derived): any `rm.prb` whose `rule_category_id` is 'batch',
      for the person's own force, whose `starting_date` is after the
      person's own `service_confirmation_date`.

    `award_id` always points at the `rm.prb` record - that is true for
    Personal Awards and Missions (which are entered directly against a
    `rm.prb`) and for the two derived legs (the `rm.prb` record that
    satisfied the rule *is* the award). Exclusions in
    `rm.excluded.awards`, however, are keyed on `rm.decoration`
    (`decoration_name`), not `rm.prb`, so a PRB row is treated as
    excluded when its `medal_id` or `ribbon_id` matches an active
    exclusion for that person - this covers all four sources uniformly.

    `attachment_id` carries the SPECIFIC device attached at that
    acquisition (e.g. a repeat-award numeral), sourced from the source
    row for Personal Awards and Missions. When that's blank - always the
    case for Seniority and Batch, which have no per-instance row to hold
    one, and optionally for Personal Awards/Missions left unset - it
    falls back to the award type's own default (`rm.prb.attachment_id`).

    This is backed by a PostgreSQL VIEW (`_auto = False`) rather than a
    real table, so it always reflects live data with no sync/duplication
    work needed, and is inherently read-only.
    """
    _name = 'rm.acquisition'
    _description = 'Consolidated Award Acquisition Ledger'
    _auto = False
    _order = 'person_id asc, source asc, year desc'

    person_id = fields.Many2one('res.person', string='Person', readonly=True)
    award_id = fields.Many2one('rm.prb', string='Award', readonly=True)
    source = fields.Selection([
        ('personal', 'Personal Award'),
        ('mission', 'Mission'),
        ('seniority', 'Seniority'),
        ('batch', 'Batch'),
    ], string='Source', readonly=True)
    year = fields.Integer(string='Year', readonly=True)
    note = fields.Char(string='Note', readonly=True)
    attachment_id = fields.Many2one('rm.attachment', string='Attachment', readonly=True)

    # Pass-through display fields for the Ribbon Rack widget: it reads
    # everything from rm.acquisition rows (not rm.prb directly) so that
    # attachment_id above - this specific acquisition's device, falling
    # back to rm.prb's default only when unset - is what the rack shows.
    name = fields.Char(related='award_id.name', readonly=True)
    sequence = fields.Float(related='award_id.sequence', readonly=True)
    is_ribbon = fields.Boolean(related='award_id.is_ribbon', readonly=True)
    is_medal = fields.Boolean(related='award_id.is_medal', readonly=True)
    ribbon_image = fields.Binary(related='award_id.ribbon_image', readonly=True)
    ribbon_list_price = fields.Float(
        related='award_id.ribbon_id.ribbon_product_tmpl_id.list_price', readonly=True,
        string='Ribbon Price')
    attachment_list_price = fields.Float(
        related='attachment_id.device_product_tmpl_id.list_price', readonly=True,
        string='Attachment Price')

    def init(self):
        tools.drop_view_if_exists(self.env.cr, self._table)
        self.env.cr.execute("""
            CREATE OR REPLACE VIEW %(table)s AS (
                SELECT
                    row_number() OVER () AS id,
                    src.person_id AS person_id,
                    src.award_id AS award_id,
                    src.source AS source,
                    src.year AS year,
                    src.note AS note,
                    -- Fall back to the award type's own default
                    -- attachment (rm_prb.attachment_id) whenever this
                    -- specific acquisition didn't record its own -
                    -- covers Personal Awards/Missions left blank, and
                    -- Seniority/Batch which never have a per-instance one.
                    COALESCE(src.attachment_id, award_prb.attachment_id) AS attachment_id
                FROM (

                    -- Personal Awards (individually entered).
                    SELECT
                        pa.person_id AS person_id,
                        pa.award_id AS award_id,
                        'personal' AS source,
                        pa.award_year AS year,
                        pa.note AS note,
                        pa.attachment_id AS attachment_id
                    FROM rm_personal_awards pa
                    WHERE pa.person_id IS NOT NULL
                      AND pa.award_id IS NOT NULL
                      AND pa.active IS TRUE

                    UNION ALL

                    -- Missions (individually entered).
                    SELECT
                        mp.person_id AS person_id,
                        mp.mission_id AS award_id,
                        'mission' AS source,
                        mp.award_year AS year,
                        mp.note AS note,
                        mp.attachment_id AS attachment_id
                    FROM rm_mission_posting mp
                    WHERE mp.person_id IS NOT NULL
                      AND mp.mission_id IS NOT NULL
                      AND mp.active IS TRUE

                    UNION ALL

                    -- Seniority (derived): PRB's required service_age
                    -- reached by the person's actual years of service,
                    -- within their own force.
                    SELECT
                        rp.id AS person_id,
                        prb.id AS award_id,
                        'seniority' AS source,
                        NULL::integer AS year,
                        NULL::varchar AS note,
                        NULL::integer AS attachment_id
                    FROM rm_prb prb
                    JOIN rm_rules_category rule
                        ON rule.id = prb.rule_category_id AND rule.name = 'seniority'
                    JOIN res_person rp
                        ON rp.force_id = prb.force_id
                    WHERE prb.active IS TRUE
                      AND prb.service_age IS NOT NULL
                      AND rp.service_confirmation_date IS NOT NULL
                      AND EXTRACT(YEAR FROM age(CURRENT_DATE, rp.service_confirmation_date)) >= prb.service_age

                    UNION ALL

                    -- Batch (derived): person's service_confirmation_date
                    -- is before the PRB's starting_date, within their own force.
                    SELECT
                        rp.id AS person_id,
                        prb.id AS award_id,
                        'batch' AS source,
                        NULL::integer AS year,
                        NULL::varchar AS note,
                        NULL::integer AS attachment_id
                    FROM rm_prb prb
                    JOIN rm_rules_category rule
                        ON rule.id = prb.rule_category_id AND rule.name = 'batch'
                    JOIN res_person rp
                        ON rp.force_id = prb.force_id
                    WHERE prb.active IS TRUE
                      AND prb.starting_date IS NOT NULL
                      AND rp.service_confirmation_date IS NOT NULL
                      AND rp.service_confirmation_date < prb.starting_date

                ) src
                JOIN rm_prb award_prb
                    ON award_prb.id = src.award_id
                -- Deduct anything excluded for that person/decoration pair,
                -- across ALL four sources at once. Exclusions are keyed on
                -- rm.decoration, so match through the PRB's medal/ribbon.
                WHERE NOT EXISTS (
                    SELECT 1
                    FROM rm_excluded_awards ex
                    JOIN rm_prb ex_prb
                        ON ex_prb.id = src.award_id
                       AND (ex_prb.medal_id = ex.decoration_name
                            OR ex_prb.ribbon_id = ex.decoration_name)
                    WHERE ex.person_id = src.person_id
                      AND ex.active IS TRUE
                )
            )
        """ % {'table': self._table})