# -*- coding: utf-8 -*-
from odoo import _, api, fields, models
from odoo.exceptions import ValidationError


class RmDecoration(models.Model):
    _name = 'rm.decoration'
    _description = 'Decoration (Ribbon / Medal)'
    _order = 'decoration_name'
    _rec_name = 'decoration_name'

    decoration_name = fields.Char(required=True, string='Award Name')
    attachment_id = fields.Many2one('rm.attachment', string='Attachment')
    is_ribbon = fields.Boolean(string='Is Ribbon')
    is_medal = fields.Boolean(string='Is Medal')
    ribbon_image = fields.Binary(string='Ribbon Image', attachment=True)
    medal_image = fields.Binary(string='Medal Image', attachment=True)
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

    def _get_size_attribute_and_values(self):
        """Return the shared 'Size' product.attribute and its S/L values,
        used on every auto-created ribbon/medal product. Falls back to
        finding-or-creating them if the module's data record is missing
        (e.g. deleted manually), instead of failing outright."""
        attribute = self.env.ref(
            'ribbon_medal.product_attribute_size', raise_if_not_found=False)
        if not attribute:
            attribute = self.env['product.attribute'].search(
                [('name', '=', 'Size')], limit=1)
            if not attribute:
                attribute = self.env['product.attribute'].create({
                    'name': 'Size',
                    'create_variant': 'always',
                })
        values = attribute.value_ids.filtered(lambda v: v.name in ('S', 'L'))
        missing = [name for name in ('S', 'L') if name not in values.mapped('name')]
        if missing:
            values |= self.env['product.attribute.value'].create([
                {'name': name, 'attribute_id': attribute.id} for name in missing
            ])
        return attribute, values

    def _prepare_award_product_vals(self, label):
        self.ensure_one()
        attribute, values = self._get_size_attribute_and_values()
        vals = {
            'name': f'{self.decoration_name} - {label}',
            'type': 'consu',
            'sale_ok': True,
            'purchase_ok': False,
            'attribute_line_ids': [(0, 0, {
                'attribute_id': attribute.id,
                'value_ids': [(6, 0, values.ids)],
            })],
        }
        # 'tracking' only exists when the stock module happens to be
        # installed (we don't depend on it - installing this module
        # shouldn't also pull in the Inventory app). When it is present,
        # it's NOT NULL with no DB-level default, so set it explicitly.
        if 'tracking' in self.env['product.template']._fields:
            vals['tracking'] = 'none'
        return vals

    def _sync_award_product(self, flag_field, tmpl_field, label):
        """Create/reactivate or archive the product.template linked via
        `tmpl_field` to match the current value of `flag_field`. Runs as
        sudo so editing a decoration doesn't require product-module
        access rights."""
        Product = self.env['product.template'].sudo()
        for record in self:
            tmpl = record[tmpl_field]
            if record[flag_field]:
                if tmpl:
                    if not tmpl.active:
                        tmpl.sudo().active = True
                else:
                    new_tmpl = Product.create(
                        record._prepare_award_product_vals(label))
                    record.sudo().write({tmpl_field: new_tmpl.id})
            else:
                if tmpl and tmpl.active:
                    tmpl.sudo().active = False

    @api.model_create_multi
    def create(self, vals_list):
        records = super().create(vals_list)
        records._sync_award_product('is_ribbon', 'ribbon_product_tmpl_id', 'Ribbon')
        records._sync_award_product('is_medal', 'medal_product_tmpl_id', 'Medal')
        return records

    def write(self, vals):
        res = super().write(vals)
        if 'is_ribbon' in vals:
            self._sync_award_product('is_ribbon', 'ribbon_product_tmpl_id', 'Ribbon')
        if 'is_medal' in vals:
            self._sync_award_product('is_medal', 'medal_product_tmpl_id', 'Medal')
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
