# -*- coding: utf-8 -*-
from odoo import _, api, fields, models
from odoo.exceptions import ValidationError


class RmDecoration(models.Model):
    _name = 'rm.decoration'
    _inherit = ['rm.product.sync.mixin']
    _description = 'Decoration (Ribbon / Medal)'
    _order = 'decoration_name'
    _rec_name = 'decoration_name'

    decoration_name = fields.Char(required=True, string='Award Name')
    attachment_id = fields.Many2one('rm.attachment', string='Attachment')
    is_ribbon = fields.Boolean(string='Is Ribbon')
    is_medal = fields.Boolean(string='Is Medal')
    ribbon_image = fields.Binary(
        string='Ribbon Image', compute='_compute_award_images', inverse='_inverse_ribbon_image')
    medal_image = fields.Binary(
        string='Medal Image', compute='_compute_award_images', inverse='_inverse_medal_image')
    mission_name = fields.Char(string='Mission Name')
    active = fields.Boolean(default=True)

    ribbon_product_tmpl_id = fields.Many2one(
        'product.template', string='Ribbon Product', readonly=True, copy=False,
        help='Sellable product auto-managed to match the "Is Ribbon" flag: '
             'created (with Small/Large size variants) the first time "Is '
             'Ribbon" is checked, archived when it is unchecked, and '
             're-activated if it is checked again later.')
    medal_product_tmpl_id = fields.Many2one(
        'product.template', string='Medal Product', readonly=True, copy=False,
        help='Sellable product auto-managed to match the "Is Medal" flag: '
             'created (with Small/Large size variants) the first time "Is '
             'Medal" is checked, archived when it is unchecked, and '
             're-activated if it is checked again later.')

    @api.constrains('is_ribbon', 'is_medal')
    def _check_award_type(self):
        for record in self:
            if not record.is_ribbon and not record.is_medal:
                raise ValidationError(
                    _('The award "%s" must be flagged as at least a Ribbon or a Medal.')
                    % record.decoration_name)

    def _compute_award_images(self):
        for record in self:
            record.ribbon_image = record.sudo().ribbon_product_tmpl_id.image_1920
            record.medal_image = record.sudo().medal_product_tmpl_id.image_1920

    def _inverse_ribbon_image(self):
        for record in self:
            tmpl = record.sudo().ribbon_product_tmpl_id
            if tmpl:
                tmpl.sudo().image_1920 = record.ribbon_image

    def _inverse_medal_image(self):
        for record in self:
            tmpl = record.sudo().medal_product_tmpl_id
            if tmpl:
                tmpl.sudo().image_1920 = record.medal_image

    def _sync_award_product(self, flag_field, tmpl_field, label, initial_image=None):
        """Create/reactivate or archive the product.template linked via
        `tmpl_field` to match the current value of `flag_field`.
        `initial_image` (keyed by record id) carries an image passed in
        the SAME create()/write() call that set the flag - the image
        field can't supply it via its own inverse yet, since the product
        doesn't exist until this method creates it. New Ribbon products
        use Meter as their Unit of Measure (ribbon material is bought
        and consumed by length); new Medal products use Unit (a discrete
        countable item) - this only applies at creation time, not
        retroactively to a product that already exists."""
        initial_image = initial_image or {}
        uom = self.env.ref(
            'uom.product_uom_meter' if label == 'Ribbon' else 'uom.product_uom_unit',
            raise_if_not_found=False)
        for record in self:
            record._sync_single_product(
                record[flag_field], tmpl_field,
                f'{record.decoration_name} - {label}',
                initial_image.get(record.id),
                uom_id=uom.id if uom else None)

    @api.model_create_multi
    def create(self, vals_list):
        records = super().create(vals_list)
        ribbon_images = {r.id: v.get('ribbon_image') for r, v in zip(records, vals_list) if v.get('ribbon_image')}
        medal_images = {r.id: v.get('medal_image') for r, v in zip(records, vals_list) if v.get('medal_image')}
        records._sync_award_product('is_ribbon', 'ribbon_product_tmpl_id', 'Ribbon', ribbon_images)
        records._sync_award_product('is_medal', 'medal_product_tmpl_id', 'Medal', medal_images)
        return records

    def write(self, vals):
        res = super().write(vals)
        if 'is_ribbon' in vals:
            image = {r.id: vals['ribbon_image'] for r in self} if vals.get('ribbon_image') else {}
            self._sync_award_product('is_ribbon', 'ribbon_product_tmpl_id', 'Ribbon', image)
        if 'is_medal' in vals:
            image = {r.id: vals['medal_image'] for r in self} if vals.get('medal_image') else {}
            self._sync_award_product('is_medal', 'medal_product_tmpl_id', 'Medal', image)
        return res

    def action_view_ribbon_product(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': 'Ribbon Product',
            'res_model': 'product.template',
            'view_mode': 'form',
            'res_id': self.ribbon_product_tmpl_id.id,
        }

    def action_view_medal_product(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': 'Medal Product',
            'res_model': 'product.template',
            'view_mode': 'form',
            'res_id': self.medal_product_tmpl_id.id,
        }
