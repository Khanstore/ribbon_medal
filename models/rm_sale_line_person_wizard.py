# -*- coding: utf-8 -*-
from odoo import _, api, fields, models
from odoo.exceptions import UserError, ValidationError
from odoo.osv import expression
import json


class RmSaleLinePersonWizard(models.TransientModel):
    _name = 'rm.sale.line.person.wizard'
    _description = 'Select Person for a Rack Order Line'

    # Either line_id is set (re-price/re-note an existing rack line) or
    # order_id is set (create a brand-new rack line on that order, of
    # the type given by rack_type, fully priced and noted, in one step).
    line_id = fields.Many2one('sale.order.line')
    order_id = fields.Many2one('sale.order')
    rack_quantity = fields.Float(
        string='Rack Qty', default=1.0, required=True,
        help='Number of identical rack units on this Sale Order line. Deposited medal quantities are per rack unit.'
    )
    rack_type = fields.Selection(
        [('ribbon', 'Ribbon Rack'), ('tunic_medal', 'Tunic Medal Rack'), ('meskit_medal', 'Meskit Medal Rack')],
        default='ribbon', required=True,
        help='Which rack product this wizard is picking a Person for - '
             'set by the button/line that opened it.')
    search_term = fields.Char(string='Search')
    initial_deposit_quantities = fields.Text(
        string='Existing deposit quantities', default='{}',
        help='Internal JSON snapshot used to restore quantities when editing an order line.')
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
    deposit_line_ids = fields.One2many(
        'rm.sale.line.person.wizard.deposit', 'wizard_id',
        string='Customer-Deposited Medals', copy=False)
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

    @api.model
    def default_get(self, fields_list):
        values = super().default_get(fields_list)

        # On the edit path, the persisted order line is the source of truth.
        # Do not rely only on context defaults: view/action customizations can
        # omit or override them and silently open a wizard with stale values.
        line_id = values.get('line_id') or self.env.context.get('default_line_id')
        line = self.env['sale.order.line'].browse(line_id).exists() if line_id else self.env['sale.order.line']
        if line:
            if 'person_id' in fields_list:
                values['person_id'] = line.person_id.id
            if 'rack_type' in fields_list:
                values['rack_type'] = line.rack_type
            if 'rack_quantity' in fields_list:
                values['rack_quantity'] = line.product_uom_qty or 1.0
            if 'line_id' in fields_list:
                values['line_id'] = line.id
            if 'initial_deposit_quantities' in fields_list:
                values['initial_deposit_quantities'] = line.deposited_award_quantities or '{}'

        person_id = values.get('person_id') or self.env.context.get('default_person_id')
        rack_type = values.get('rack_type') or self.env.context.get('default_rack_type')
        raw = (values.get('initial_deposit_quantities')
               or (line.deposited_award_quantities if line else False)
               or self.env.context.get('default_initial_deposit_quantities') or '{}')
        try:
            old = {int(key): max(0, int(value)) for key, value in json.loads(raw).items()}
        except (ValueError, TypeError, AttributeError):
            old = {}

        if person_id and rack_type in ('tunic_medal', 'meskit_medal') and 'deposit_line_ids' in fields_list:
            person = self.env['res.partner'].browse(person_id).exists()
            if person:
                size = 'l' if rack_type == 'tunic_medal' else 's'
                values['deposit_line_ids'] = [(0, 0, {
                    'award_id': award.id,
                    'quantity': min(old.get(award.id, 0), self._award_count_for_person(person, award.id, size) * (values.get('rack_quantity') or 1.0)),
                }) for award in person._get_medal_rack_awards(size)]
        return values

    @api.model
    def _award_count_for_person(self, person, award_id, size):
        custom = person._custom_medal_rows(size)
        if custom:
            return len(custom.filtered(lambda row: row.award_id.id == award_id))
        flag = 'add_to_big_medal' if size == 'l' else 'add_to_mini_medal'
        return self.env['rm.acquisition'].search_count([
            ('person_id', '=', person.id), ('is_medal', '=', True),
            (flag, '=', True), ('award_id', '=', award_id)])

    @api.depends('person_id', 'rack_type', 'line_id', 'line_id.product_id')
    def _compute_rack_preview_image(self):
        """Show the actual selected rack product image, with a safe fallback.

        Prefer the existing order-line product image when editing. Otherwise
        use the person's resolved variant when available, then the configured
        standard rack product image. Do not require a variant just to preview.
        """
        config = self.env['sale.order']._get_rack_kind_config()
        for wizard in self:
            image = False
            if wizard.line_id and wizard.line_id.product_id:
                product = wizard.line_id.product_id
                image = product.image_1920 or product.product_tmpl_id.image_1920
            if not image and wizard.person_id and wizard.rack_type:
                variant = wizard.person_id._resolve_rack_variant(wizard.rack_type)
                if variant:
                    image = variant.image_variant_1920 or variant.image_1920 or variant.product_tmpl_id.image_1920
            if not image and wizard.rack_type in config:
                template = self.env.ref(config[wizard.rack_type]['product_xmlid'], raise_if_not_found=False)
                if template:
                    image = template.image_1920
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

    def _deposit_quantities(self):
        self.ensure_one()
        return {str(line.award_id.id): int(line.quantity or 0)
                for line in self.deposit_line_ids if line.award_id and line.quantity > 0}

    @api.onchange('person_id', 'rack_type')
    def _onchange_deposit_award_rows(self):
        for wizard in self:
            if not wizard.person_id or wizard.rack_type not in ('tunic_medal', 'meskit_medal'):
                wizard.deposit_line_ids = [(5, 0, 0)]
                continue
            old = {line.award_id.id: line.quantity for line in wizard.deposit_line_ids if line.award_id}
            if not old and wizard.initial_deposit_quantities:
                try:
                    import json
                    old = {int(key): int(value) for key, value in json.loads(wizard.initial_deposit_quantities or '{}').items()}
                except (ValueError, TypeError, AttributeError):
                    old = {}
            size = 'l' if wizard.rack_type == 'tunic_medal' else 's'
            wizard.deposit_line_ids = [(5, 0, 0)] + [
                (0, 0, {'award_id': award.id, 'quantity': min(old.get(award.id, 0), wizard._award_max_deposit_quantity(award.id, size))})
                for award in wizard.person_id._get_medal_rack_awards(size)]

    def _award_acquisition_count(self, award_id, size):
        self.ensure_one()
        return self._award_count_for_person(self.person_id, award_id, size)

    def _award_max_deposit_quantity(self, award_id, size):
        self.ensure_one()
        # A customer can supply at most the person's acquired quantity for
        # each identical rack unit.  Rack Qty therefore multiplies the pool.
        return self._award_acquisition_count(award_id, size) * (self.rack_quantity or 1.0)

    @api.depends('person_id', 'rack_type', 'deposit_line_ids.quantity', 'deposit_line_ids.award_id')
    def _compute_rack_total_price(self):
        for wizard in self:
            quantities = wizard._deposit_quantities() if wizard.person_id else {}
            wizard.rack_total_price = (
                wizard.person_id._rack_price(wizard.rack_type, deposited_award_quantities=quantities)
                if (wizard.person_id and wizard.rack_type) else 0.0)

    def action_confirm(self):
        self.ensure_one()
        config = self.env['sale.order']._get_rack_kind_config()
        cfg = config.get(self.rack_type)
        if not cfg:
            raise UserError(_('Unknown rack type.'))

        if self.rack_quantity <= 0:
            raise UserError(_('Rack Qty must be greater than zero.'))

        if self.line_id:
            if not self.line_id.exists():
                raise UserError(_(
                    'This order line no longer exists - reopen the order and try again.'))
            quantities = self._deposit_quantities()
            self.line_id.deposited_award_quantities = json.dumps(quantities)
            self.line_id.person_id = self.person_id
            self.line_id.product_uom_qty = self.rack_quantity
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
            quantities = self._deposit_quantities()
            price = self.person_id._rack_price(self.rack_type, deposited_award_quantities=quantities)
            name_lines = [variant.name, _('(For: %s)') % self.person_id.rm_rack_label()]
            deposit_names = self.deposit_line_ids.filtered(lambda row: row.quantity > 0)
            if deposit_names:
                name_lines.append(_('(Deposited: %s)') % ', '.join('%s × %s' % (row.award_id.display_name, row.quantity) for row in deposit_names))
            self.env['sale.order.line'].create({
                'order_id': self.order_id.id,
                'product_id': variant.id,
                'rack_type': self.rack_type,
                'product_uom_qty': self.rack_quantity,
                'price_unit': price,
                'person_id': self.person_id.id,
                'deposited_award_quantities': json.dumps(quantities),
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


class RmSaleLinePersonWizardDeposit(models.TransientModel):
    _name = 'rm.sale.line.person.wizard.deposit'
    _description = 'Customer-Deposited Medal Quantity (Wizard)'
    _order = 'id'

    wizard_id = fields.Many2one('rm.sale.line.person.wizard', required=True, ondelete='cascade')
    award_id = fields.Many2one('rm.prb', string='Medal / Award', required=True, readonly=True)
    quantity = fields.Integer(string='Qty Deposited', default=0)
    max_quantity = fields.Float(compute='_compute_max_quantity', string='Max Depositable Qty')

    @api.depends('wizard_id.person_id', 'wizard_id.rack_type', 'wizard_id.rack_quantity', 'award_id')
    def _compute_max_quantity(self):
        for line in self:
            wizard = line.wizard_id
            if wizard.person_id and line.award_id and wizard.rack_type in ('tunic_medal', 'meskit_medal'):
                size = 'l' if wizard.rack_type == 'tunic_medal' else 's'
                line.max_quantity = wizard._award_max_deposit_quantity(line.award_id.id, size)
            else:
                line.max_quantity = 0

    @api.constrains('quantity', 'max_quantity')
    def _check_quantity(self):
        for line in self:
            if line.quantity < 0 or line.quantity > line.max_quantity:
                raise ValidationError(_(
                    'Deposited quantity must be between 0 and the '
                    'number of acquired medals multiplied by Rack Qty (%s).'
                ) % line.max_quantity)
