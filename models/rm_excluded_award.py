#-*- coding: utf-8 -*-
from odoo import api, fields, models
from datetime import date, datetime
from odoo.exceptions import ValidationError


class excludedAwards(models.Model):
    """Award record record."""
    _name = 'rm.excluded.awards'
    _description = 'awards excluded/withheld/revoked from a person are listed here'
    _rec_name = 'decoration_name'
    decoration_name = fields.Many2one('rm.decoration', string='Award Name')
    person_id = fields.Many2one('res.person', string='Person')
    exclusion_year = fields.Integer(string='Exclusion Year')
    reason = fields.Char(string='Reason')
    note = fields.Char(string='note')
    active = fields.Boolean(default=True)

    @api.constrains('exclusion_year')
    def _check_exclusion_year(self):
        current_year = date.today().year
        for record in self:
            if record.exclusion_year and (record.exclusion_year < 1900 or record.exclusion_year > current_year):
                raise ValidationError(f"The year must be between 1900 and {current_year}.")
