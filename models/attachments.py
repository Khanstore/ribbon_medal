# -*- coding: utf-8 -*-
from odoo import _, api, fields, models
from odoo.exceptions import ValidationError


class ribbonAttachments(models.Model):
    _name = 'rm.attachment'
    _description = 'attachment club/numeric for Ribbon / Medal'
    _order = 'name'

    name = fields.Char(required=True, string='Name')
    image = fields.Binary(string='Image', attachment=True)
    force_name = fields.Many2one('rm.forces',string='Force')
    active = fields.Boolean(default=True)

    force_id = fields.Many2one('rm.forces', string='Force', ondelete='restrict', index=True)