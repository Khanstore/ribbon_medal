#-*- coding: utf-8 -*-
from odoo import api, fields, models
from datetime import date, datetime
from odoo.exceptions import ValidationError


# class personalAwards(models.Model):
#     """Award record record."""
#     _name = 'rm.personal.awards'
#     _description = 'all achievement and award listed here'
#     _rec_name = 'prb_id'
#     prb_id = fields.Many2one('rm.prb',string='Award Name')
#     person_id=fields.Many2one('res.person',string='Person')
#     award_year = fields.Integer(string='Award Date')
#     note = fields.Char(string='note')
#     active = fields.Boolean(default=True)
#     add_to_ribbon = fields.Boolean(string="Tunic ribbon",default=True)
#     add_to_big_medal = fields.Boolean(string="Tunic Medal",default=True)
#     add_to_mini_medal = fields.Boolean(string="Mini Medal",default=True)
#
#     @api.constrains('award_year')
#     def _check_award_year(self):
#         current_year = date.today().year
#         for record in self:
#             if record.award_year and (record.award_year < 1900 or record.award_year > current_year):
#                 raise ValidationError(f"The year must be between 1900 and {current_year}.")