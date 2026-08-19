# -*- coding: utf-8 -*-
from odoo import _, api, fields, models
from odoo.exceptions import ValidationError


class RmSetTemplate(models.Model):
    """High-level template defining what a manufactured set (e.g. a
    Ribbon Rack) is made of, as a set of category-level rules rather
    than fixed products - see rm.set.template.component."""
    _name = 'rm.set.template'
    _description = 'Set Template'
    _order = 'name'

    name = fields.Char(required=True)
    category = fields.Selection([
        ('ribbon_rack', 'Ribbon Rack'),
        ('medal_set', 'Medal Set'),
    ], required=True, default='ribbon_rack')
    description = fields.Text()
    active = fields.Boolean(default=True)
    component_rule_ids = fields.One2many(
        'rm.set.template.component', 'template_id', string='Component Rules')


class RmSetTemplateComponent(models.Model):
    """One rule within a rm.set.template: 'this category of material is
    needed, at this scope, this much, optionally with a fixed default
    product, optionally left for the user to pick at calculation time.'
    """
    _name = 'rm.set.template.component'
    _description = 'Set Template Component Rule'
    _order = 'template_id, sequence, id'

    template_id = fields.Many2one('rm.set.template', required=True, ondelete='cascade')
    sequence = fields.Integer(default=10)
    category_id = fields.Many2one('rm.component.category', required=True, string='Category')
    default_product_id = fields.Many2one(
        'product.template', string='Default Product',
        help='Fixed product for non-varying items (e.g. a standard Safety '
             "Pin or a packaging box). Leave empty when the product "
             'varies and "User Picks Product" is checked.')
    scope = fields.Selection([
        ('per_cell', 'Per Cell'),
        ('per_rack', 'Per Rack'),
        ('per_attachment', 'Per Attachment'),
    ], required=True, default='per_cell',
        help='Per Cell: applied once for every acquired award on the '
             'rack. Per Rack: applied once for the whole rack, '
             'regardless of cell count. Per Attachment: applied once '
             'per cell, but only for cells that actually have an '
             'attachment/device.')
    quantity = fields.Float(required=True, default=1.0, string='Base Quantity')
    uom_id = fields.Many2one('uom.uom', string='Unit of Measure')
    is_user_selected = fields.Boolean(
        string='User Picks Product',
        help='Checked: the specific product is resolved at calculation '
             'time - automatically from the cell\'s own data for the '
             'RIBBON and ATTACHMENT categories, otherwise from an '
             'explicit selection captured on the Set Order. Unchecked: '
             'always use Default Product (e.g. standard gum).')

    @api.constrains('is_user_selected', 'default_product_id')
    def _check_default_product(self):
        for rule in self:
            if not rule.is_user_selected and not rule.default_product_id:
                raise ValidationError(_(
                    'The rule for category "%s" is not user-selected, so it needs a Default Product.'
                ) % rule.category_id.display_name)
