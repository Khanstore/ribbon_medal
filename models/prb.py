# -*- coding: utf-8 -*-
from odoo import _, api, fields, models
from odoo.exceptions import ValidationError


class RmPRB(models.Model):
    _name = 'rm.prb'
    _description = 'PRB of decorations'
    _order = 'seniority_sequence desc, name'

    name = fields.Char(required=True, string='PRB Name')
    medal_id = fields.Many2one('rm.decoration', string='Medal')
    ribbon_id = fields.Many2one('rm.decoration', string='Ribbon')
    seniority_sequence=fields.Integer("seniority")
    sequence = fields.Float(string='Sequence')
    starting_date = fields.Date(string='Starting Date')
    is_ribbon = fields.Boolean(string='Is Ribbon')
    is_medal = fields.Boolean(string='Is Medal')
    service_age=fields.Integer(string='Service Age')
    attachment_id = fields.Many2one('rm.attachment', string='Attachment')
    ribbon_image = fields.Binary(
        string='Ribbon Image', compute='_compute_award_images', inverse='_inverse_ribbon_image')
    medal_image = fields.Binary(
        string='Medal Image', compute='_compute_award_images', inverse='_inverse_medal_image')
    mission_name = fields.Char(string='Mission Name')
    active = fields.Boolean(default=True)

    force_id = fields.Many2one('rm.forces', string='Force', ondelete='restrict', index=True)
    rule_category_id = fields.Many2one(
        'rm.rules.category', string='Rules Category', ondelete='restrict')

    def _compute_award_images(self):
        for record in self:
            record.ribbon_image = record.sudo().ribbon_id.ribbon_product_tmpl_id.image_1920
            record.medal_image = record.sudo().medal_id.medal_product_tmpl_id.image_1920

    def _inverse_ribbon_image(self):
        for record in self:
            tmpl = record.sudo().ribbon_id.ribbon_product_tmpl_id
            if tmpl:
                tmpl.sudo().image_1920 = record.ribbon_image

    def _inverse_medal_image(self):
        for record in self:
            tmpl = record.sudo().medal_id.medal_product_tmpl_id
            if tmpl:
                tmpl.sudo().image_1920 = record.medal_image

    @api.model
    def copy(self, default=None):
        # 1. Initialize the default dictionary if it's not provided
        default = dict(default or {})

        # 2. Add the suffix to the name field
        if self.name:
            default['name'] = f"{self.name} (copy)"

        # 3. Clear out the field value (set it to False)
        default['mission_name'] = False

        # 4. Call the super method to finalize creation
        return super(RmPRB, self).copy(default=default)