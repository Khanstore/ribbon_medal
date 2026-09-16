# -*- coding: utf-8 -*-
from odoo import _, api, fields, models
from odoo.exceptions import UserError
from odoo.osv import expression


class RmSaleLinePersonWizard(models.TransientModel):
    _name = 'rm.sale.line.person.wizard'
    _description = 'Select Person for a Rack Order Line'

    # Either line_id is set (re-price/re-note an existing rack line) or
    # order_id is set (create a brand-new rack line on that order, of
    # the type given by rack_type, fully priced and noted, in one step).
    line_id = fields.Many2one('sale.order.line')
    order_id = fields.Many2one('sale.order')
    rack_type = fields.Selection(
        [('ribbon', 'Ribbon Rack'), ('tunic_medal', 'Tunic Medal Rack'), ('meskit_medal', 'Meskit Medal Rack')],
        default='ribbon', required=True,
        help='Which rack product this wizard is picking a Person for - '
             'set by the button/line that opened it.')
    search_term = fields.Char(string='Search')
    result_person_ids = fields.Many2many(
        'res.partner', string='Matches', compute='_compute_results')
    person_id = fields.Many2one(
        'res.partner', string='Person', required=True, domain=[('is_person', '=', True)],
        help='Pick the matching person from the results below, or type '
             'a name/ID/phone/mobile/email directly into this field to '
             'search.')
    available_award_ids = fields.Many2many(
        'rm.prb', string='Medal-Eligible Awards', compute='_compute_available_award_ids',
        help='This person\'s medal-eligible awards for this rack type\'s '
             "size - the pool deposited_award_ids can pick from. Empty "
             "for a Ribbon Rack line (no medal in it).")
    deposited_award_ids = fields.Many2many(
        'rm.prb', string='Customer-Deposited Medals',
        help="Tick any awards whose medal the customer is supplying "
             "themselves for this line, instead of the shop providing "
             "one from stock - their cost is left out of the price "
             "below, and manufacturing won't require that medal from "
             "stock for this unit.")
    rack_total_price = fields.Float(
        string='Estimated Price', compute='_compute_rack_total_price', readonly=True)
    rack_preview_image = fields.Image(
        string='Rack Preview', compute='_compute_rack_preview_image',
        help='Live preview of the actual Ribbon/Medal Rack product image '
             "for the selected Person and this line's rack type - the same "
             'image that would end up on the sale order line once '
             'confirmed. Resolves (and, the first time this exact '
             'combination is seen, generates) the real product/variant via '
             "_resolve_rack_variant, same as action_confirm - so opening "
             "this wizard on a Person can create that variant/image even "
             "before Confirm is pressed.")

    @api.depends('person_id', 'rack_type')
    def _compute_rack_preview_image(self):
        for wizard in self:
            image = False
            if wizard.person_id and wizard.rack_type:
                variant = wizard.person_id._resolve_rack_variant(wizard.rack_type)
                if variant:
                    image = variant.image_variant_1920 or variant.image_1920
            wizard.rack_preview_image = image

    @api.depends('person_id', 'rack_type')
    def _compute_available_award_ids(self):
        for wizard in self:
            if wizard.person_id and wizard.rack_type in ('tunic_medal', 'meskit_medal'):
                size = 'l' if wizard.rack_type == 'tunic_medal' else 's'
                wizard.available_award_ids = wizard.person_id._get_medal_rack_awards(size)
            else:
                wizard.available_award_ids = self.env['rm.prb']

    @api.depends('search_term')
    def _compute_results(self):
        Person = self.env['res.partner']
        for wizard in self:
            term = wizard.search_term
            if not term:
                wizard.result_person_ids = Person
                continue
            or_clauses = [
                [('name', 'ilike', term)],
                [('id_number', 'ilike', term)],
                [('phone', 'ilike', term)],
                [('mobile', 'ilike', term)],
                [('email', 'ilike', term)],
                [('rank_id.name', 'ilike', term)],
                [('current_workplace.name', 'ilike', term)],
            ]
            domain = expression.AND([[('is_person', '=', True)], expression.OR(or_clauses)])
            wizard.result_person_ids = Person.search(domain, limit=20)

    @api.depends('person_id', 'rack_type', 'deposited_award_ids')
    def _compute_rack_total_price(self):
        for wizard in self:
            wizard.rack_total_price = (
                wizard.person_id._rack_price(wizard.rack_type, excluded_award_ids=wizard.deposited_award_ids.ids)
                if (wizard.person_id and wizard.rack_type) else 0.0)

    def action_confirm(self):
        self.ensure_one()
        config = self.env['sale.order']._get_rack_kind_config()
        cfg = config.get(self.rack_type)
        if not cfg:
            raise UserError(_('Unknown rack type.'))

        if self.line_id:
            if not self.line_id.exists():
                raise UserError(_(
                    'This order line no longer exists - reopen the order and try again.'))
            self.line_id.deposited_award_ids = [(6, 0, self.deposited_award_ids.ids)]
            self.line_id.person_id = self.person_id
            self.line_id._apply_rack_person()
        elif self.order_id:
            if not self.order_id.exists():
                raise UserError(_(
                    'This order no longer exists - reopen it and try again.'))
            variant = self.person_id._resolve_rack_variant(self.rack_type)
            if not variant:
                raise UserError(_(
                    '%(person)s has no acquisitions on the Acquisition Ledger yet '
                    'to build a %(label)s for.'
                ) % {'person': self.person_id.display_name, 'label': cfg['label']})
            price = self.person_id._rack_price(self.rack_type, excluded_award_ids=self.deposited_award_ids.ids)
            name_lines = [variant.name, _('(For: %s)') % self.person_id.rm_rack_label()]
            if self.deposited_award_ids:
                name_lines.append(_('(Deposited: %s)') % ', '.join(self.deposited_award_ids.mapped('name')))
            self.env['sale.order.line'].create({
                'order_id': self.order_id.id,
                'product_id': variant.id,
                'rack_type': self.rack_type,
                'product_uom_qty': 1,
                'price_unit': price,
                'person_id': self.person_id.id,
                'deposited_award_ids': [(6, 0, self.deposited_award_ids.ids)],
                'name': '\n'.join(name_lines),
            })
            # Adding a brand-new rack line via this wizard also sets the
            # order-level Person to whoever was just picked - only on
            # this add-new-line path, never when this same wizard is
            # instead re-pricing/re-noting an existing line (line_id set
            # above), so editing one line's Person for a multi-person
            # order never clobbers the order's own Person.
            self.order_id.person_id = self.person_id.id
        else:
            raise UserError(_('Nothing to apply this to - reopen the order and try again.'))
        return {'type': 'ir.actions.client', 'tag': 'soft_reload'}
