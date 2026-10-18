# -*- coding: utf-8 -*-
from odoo import _, api, fields, models
from odoo.exceptions import ValidationError


class RmPRB(models.Model):
    _name = 'rm.prb'
    _description = 'PRB of decorations'
    _order = 'sequence, name'

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
    device_image = fields.Binary(
        string='Device Image', compute='_compute_award_images', inverse='_inverse_device_image')
    mission_name = fields.Char(string='Mission Name')
    active = fields.Boolean(default=True)

    force_id = fields.Many2one('rm.forces', string='Force', ondelete='restrict', index=True)
    rule_category_id = fields.Many2one(
        'rm.rules.category', string='Rules Category', ondelete='restrict')

    def _compute_award_images(self):
        for record in self:
            record.ribbon_image = record.sudo().ribbon_id.ribbon_product_tmpl_id.image_1920
            record.medal_image = record.sudo().medal_id.medal_product_tmpl_id.image_1920
            record.device_image = record.sudo().attachment_id.device_product_tmpl_id.image_1920

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

    def _inverse_device_image(self):
        for record in self:
            tmpl = record.sudo().attachment_id.device_product_tmpl_id
            if tmpl:
                tmpl.sudo().image_1920 = record.device_image

    def action_regenerate_rack_images(self):
        """Rebuild the stored composite picture (image_variant_1920) of
        every ALREADY-BUILT Ribbon Rack / Medal Rack that includes this
        decoration, using its CURRENT ribbon/medal/device images.

        Building that composite only happens once per unique row/
        combination, the first time it's needed (rm.rack.product's and
        rm.medal.rack's identity is locked permanently via
        get_or_create - see those models). So editing this decoration's
        images afterwards does NOT, by itself, touch any Rack already
        built from it - only a fresh combination that happens to need
        building for the first time would pick up the new image.

        Call this once, right after changing an image here, to push
        that change out to every Rack that already exists instead of
        waiting for each to eventually get rebuilt on its own (which,
        for an existing combination, never happens automatically).
        """
        self.ensure_one()
        racks = self.env['rm.rack.product'].search([
            ('rack_line_ids.line_id.item_ids.award_id', '=', self.id),
            ('product_id', '!=', False),
        ])
        medal_racks = self.env['rm.medal.rack'].search([
            ('part_award_ids.award_id', '=', self.id),
            ('product_id', '!=', False),
        ])
        for rack in racks:
            rack._generate_rack_image()
        for medal_rack in medal_racks:
            medal_rack._generate_rack_image()
        message = _('Regenerated %(ribbon_count)s Ribbon Rack image(s) and '
                    '%(medal_count)s Medal Rack image(s).')
        message = message % {'ribbon_count': len(racks), 'medal_count': len(medal_racks)}
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('Rack Images Updated'),
                'message': message,
                'type': 'success',
                'sticky': False,
            },
        }

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