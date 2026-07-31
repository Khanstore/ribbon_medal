# -*- coding: utf-8 -*-
import re

from odoo import _, api, fields, models
from odoo.exceptions import UserError, ValidationError


class RmDecoration(models.Model):
    _name = 'rm.decoration'
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

    def _zero_value_for_field(self, field):
        """A conservative, inoffensive default for a field we don't
        actually care about, just to satisfy a NOT NULL constraint."""
        if field.type == 'boolean':
            return False
        if field.type in ('integer', 'float', 'monetary'):
            return 0
        if field.type in ('char', 'text', 'html'):
            return ''
        if field.type == 'date':
            return fields.Date.today()
        if field.type == 'datetime':
            return fields.Datetime.now()
        if field.type == 'selection':
            try:
                options = field.get_description(self.env)['selection']
                for key, _label in options:
                    if key:
                        return key
                return options[0][0] if options else False
            except Exception:
                return False
        return False

    def _create_product_resilient(self, vals):
        """Create a product.template, automatically supplying a default
        for any field THIS environment's installed modules happen to
        require at the DB level with no ORM-level default of their own
        (seen in practice: stock's 'tracking', a customization's
        'base_unit_count' - the exact set depends on which third-party
        modules are installed, so rather than hardcoding a fixed list
        this discovers them one at a time from the DB error and retries)."""
        Product = self.env['product.template'].sudo()
        vals = dict(vals)
        patched_fields = set()
        for _attempt in range(10):
            try:
                with self.env.cr.savepoint():
                    new_tmpl = Product.create(vals)
                    # Force immediate flush so any NOT NULL violation
                    # surfaces right here (and can be retried) instead of
                    # much later, deep in an unrelated flush.
                    self.env.flush_all()
                    return new_tmpl
            except Exception as exc:
                match = re.search(r'column "(\w+)"', str(exc))
                field_name = match.group(1) if match else None
                field = Product._fields.get(field_name) if field_name else None
                if not field or field_name in patched_fields:
                    raise
                patched_fields.add(field_name)
                vals[field_name] = self._zero_value_for_field(field)
        raise UserError(_(
            'Could not create product "%s" - repeatedly hit new required fields (%s).'
        ) % (vals.get('name'), ', '.join(sorted(patched_fields))))

    def _sync_award_product(self, flag_field, tmpl_field, label, initial_image=None):
        """Create/reactivate or archive the product.template linked via
        `tmpl_field` to match the current value of `flag_field`. Runs as
        sudo so editing a decoration doesn't require product-module
        access rights. `initial_image` (keyed by record id) carries an
        image passed in the SAME create()/write() call that set the
        flag - the image field can't supply it via its own inverse yet,
        since the product doesn't exist until this method creates it."""
        initial_image = initial_image or {}
        for record in self:
            tmpl = record[tmpl_field]
            if record[flag_field]:
                if tmpl:
                    if not tmpl.active:
                        tmpl.sudo().active = True
                else:
                    vals = record._prepare_award_product_vals(label)
                    image = initial_image.get(record.id)
                    if image:
                        vals['image_1920'] = image
                    new_tmpl = self._create_product_resilient(vals)
                    # Note: _create_product_resilient() already flushes
                    # immediately after creating, so this template's
                    # variants (Size S/L) are fully materialized to the
                    # DB before the loop moves on to the next decoration
                    # - important when bulk-creating ~100+ decorations
                    # (each spawning 2 products x 2 size variants) in a
                    # single create() call.
                    record.sudo().write({tmpl_field: new_tmpl.id})
            else:
                if tmpl and tmpl.active:
                    tmpl.sudo().active = False

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
