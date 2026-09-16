# -*- coding: utf-8 -*-
from odoo import fields, models


class RmAcquisitionCustom(models.Model):
    """A manually-editable COPY of a person's Acquisition Ledger entries.

    rm.acquisition is a live SQL view - it always reflects current data
    and can't be reordered/edited/trimmed per person. Some personnel want
    a customised list (reordered, with entries added/removed) that does
    NOT change automatically when the underlying data changes. This is a
    real, stored table for exactly that: a snapshot at a point in time,
    then freely editable afterwards.
    """
    _name = 'rm.acquisition.custom'
    _description = 'Customised Acquisition Ledger (manual copy, not auto-synced)'
    _order = 'person_id, sequence, id'
    _rec_name = 'award_id'

    person_id = fields.Many2one('res.partner', string='Person', required=True, ondelete='cascade',
                                 index=True, domain=[('is_person', '=', True)])
    award_id = fields.Many2one('rm.prb', string='Award', required=True)
    source = fields.Selection([
        ('personal', 'Personal Award'),
        ('mission', 'Mission'),
        ('seniority', 'Seniority'),
        ('batch', 'Batch'),
    ], string='Source')
    sequence = fields.Integer(string='Sequence', default=10)
    year = fields.Integer(string='Year')
    note = fields.Char(string='Note')
    attachment_id = fields.Many2one('rm.attachment', string='Attachment')

    # Per-row opt-in to each of the three racks. Deliberately NOT
    # defaulted to True (unlike rm.personal.awards / rm.mission.posting,
    # where they default True): this table is a manual customisation, so
    # a row only joins a customised rack once explicitly ticked here.
    # copy_from_ledger leaves them untouched for the same reason.
    add_to_ribbon = fields.Boolean(string='ribbon')
    add_to_big_medal = fields.Boolean(string='Tunic Medal')
    add_to_mini_medal = fields.Boolean(string='Mini/Meskit Medal')

    # Pass-through display fields so the customised rack widgets can
    # read everything they render straight off these rows, exactly as
    # the standard rack widgets read it off rm.acquisition.
    award_name = fields.Char(related='award_id.name', readonly=True, string='Award Name')
    prb_sequence = fields.Float(
        related='award_id.sequence', readonly=True, string='Precedence',
        help="The award type's own precedence. Note the customised racks "
             'order by this row\'s manual Sequence instead - that '
             'reordering is the point of this table.')
    is_ribbon = fields.Boolean(related='award_id.is_ribbon', readonly=True)
    is_medal = fields.Boolean(related='award_id.is_medal', readonly=True)
    ribbon_image = fields.Binary(related='award_id.ribbon_image', readonly=True)
    medal_image = fields.Binary(related='award_id.medal_image', readonly=True)

    def copy_from_ledger(self, person):
        """Snapshot `person`'s current rm.acquisition rows into this
        table. Only adds entries not already present here (matched on
        award_id + source) - never overwrites or removes anything
        already customised, so it's safe to call more than once (e.g. to
        pull in newly-earned awards without disturbing manual edits)."""
        existing = self.search([('person_id', '=', person.id)])
        existing_keys = {(row.award_id.id, row.source) for row in existing}
        ledger_rows = self.env['rm.acquisition'].search([('person_id', '=', person.id)])
        next_sequence = (max(existing.mapped('sequence')) + 10) if existing else 10

        to_create = []
        for row in ledger_rows:
            key = (row.award_id.id, row.source)
            if key in existing_keys:
                continue
            to_create.append({
                'person_id': person.id,
                'award_id': row.award_id.id,
                'source': row.source,
                'year': row.year,
                'note': row.note,
                'attachment_id': row.attachment_id.id,
                'sequence': next_sequence,
            })
            next_sequence += 10

        return self.create(to_create) if to_create else self.browse()
