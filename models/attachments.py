# -*- coding: utf-8 -*-
from odoo import _, api, fields, models


class ribbonAttachments(models.Model):
    _name = 'rm.attachment'
    _inherit = ['rm.product.sync.mixin']
    _description = 'attachment club/numeric for Ribbon / Medal'
    _order = 'name'

    name = fields.Char(required=True, string='Name')
    image = fields.Binary(
        string='Image', compute='_compute_device_image', inverse='_inverse_device_image')
    active = fields.Boolean(default=True)

    force_id = fields.Many2one('rm.forces', string='Force', ondelete='restrict', index=True)

    device_product_tmpl_id = fields.Many2one(
        'product.template', string='Device Product', readonly=True, copy=False,
        help='Sellable product auto-managed to match this attachment: '
             'created (with Small/Large size variants) the first time the '
             'attachment is active, archived when the attachment is '
             'archived, and re-activated if it becomes active again later.')

    def _compute_device_image(self):
        for record in self:
            record.image = record.sudo().device_product_tmpl_id.image_1920

    def _inverse_device_image(self):
        for record in self:
            tmpl = record.sudo().device_product_tmpl_id
            if tmpl:
                tmpl.sudo().image_1920 = record.image

    def _sync_device_product(self, initial_image=None):
        """Create/reactivate or archive device_product_tmpl_id to match
        this attachment's own `active` state - the same lifecycle
        management rm.decoration applies to its ribbon/medal products.
        `initial_image` (keyed by record id) carries an image passed in
        the SAME create()/write() call, for the same reason
        rm.decoration needs it: the product doesn't exist yet at the
        point the image field's own inverse would normally fire."""
        initial_image = initial_image or {}
        for record in self:
            record._sync_single_product(
                record.active, 'device_product_tmpl_id',
                f'{record.name} - Device', initial_image.get(record.id))

    @api.model_create_multi
    def create(self, vals_list):
        records = super().create(vals_list)
        images = {r.id: v.get('image') for r, v in zip(records, vals_list) if v.get('image')}
        records._sync_device_product(images)
        return records

    def write(self, vals):
        res = super().write(vals)
        if 'active' in vals:
            self._sync_device_product()
        return res

    def action_view_device_product(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _('Device Product'),
            'res_model': 'product.template',
            'view_mode': 'form',
            'res_id': self.device_product_tmpl_id.id,
        }
