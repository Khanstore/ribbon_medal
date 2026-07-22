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

    person_id = fields.Many2one('res.person', string='Person', required=True, ondelete='cascade', index=True)
    award_id = fields.Many2one('rm.decoration', string='Award', required=True)
    source = fields.Selection([
        ('personal', 'Personal Award'),
        ('mission', 'Mission'),
        ('seniority', 'Seniority'),
        ('batch', 'Batch'),
    ], string='Source')
    sequence = fields.Integer(string='Sequence', default=10)
    year = fields.Integer(string='Year')
    note = fields.Char(string='Note')

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
                'sequence': next_sequence,
            })
            next_sequence += 10

        return self.create(to_create) if to_create else self.browse()
