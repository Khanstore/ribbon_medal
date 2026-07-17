#-*- coding: utf-8 -*-
from odoo import api, fields, models
from datetime import date, datetime


class bcsBatch(models.Model):
    """Bcs record record."""
    _name = 'rm.bcs.batch'
    _description = 'Bcs Batch joining date'
    _rec_name = 'name'
    name = fields.Char(string='Batch Name')
    description = fields.Char(string='Batch Description')
    total_person = fields.One2many('res.person','bcs_batch',string='Joining Date')
    joining_date = fields.Date(string='Joining Date')
