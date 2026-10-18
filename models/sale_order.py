# -*- coding: utf-8 -*-
import json

from odoo import _, api, fields, models
from odoo.exceptions import UserError


class SaleOrder(models.Model):
    _inherit = 'sale.order'

    person_id = fields.Many2one(
        'res.partner', string='Person', index=True, domain=[('is_person', '=', True)],
        help='Legacy/fallback only - prefer setting Person directly on '
             'each rack order line instead, since one order can have '
             'rack lines (Ribbon Rack, Tunic Medal Rack, Meskit Medal '
             'Rack) for several different people. This is only used '
             'for a rack line that has no Person of its own set.')
    rack_unit_id = fields.Many2one(
        'rm.rack.unit', string='Ribbon Rack Unit', readonly=True, copy=False,
        help='Set to the first Ribbon Rack Unit issued for this order, for '
             'quick reference - see each Ribbon Rack line for its own '
             'specific unit when there is more than one.')
    rack_unit_id_state = fields.Selection(related='rack_unit_id.state', string='Ribbon Rack Unit Status')
    tunic_medal_rack_unit_id = fields.Many2one(
        'rm.medal.rack.unit', string='Tunic Medal Rack Unit', readonly=True, copy=False,
        help='Set to the first Tunic Medal Rack Unit issued for this order, '
             'for quick reference - see each line for its own specific unit '
             'when there is more than one.')
    tunic_medal_rack_unit_id_state = fields.Selection(
        related='tunic_medal_rack_unit_id.state', string='Tunic Medal Rack Unit Status')
    meskit_medal_rack_unit_id = fields.Many2one(
        'rm.medal.rack.unit', string='Meskit Medal Rack Unit', readonly=True, copy=False,
        help='Set to the first Meskit Medal Rack Unit issued for this order, '
             'for quick reference - see each line for its own specific unit '
             'when there is more than one.')
    meskit_medal_rack_unit_id_state = fields.Selection(
        related='meskit_medal_rack_unit_id.state', string='Meskit Medal Rack Unit Status')

    @api.onchange('partner_id')
    def _onchange_partner_id_person(self):
        """If the Customer for this order is themselves marked as
        Personnel (is_person), default the order's Person field to
        them directly - only when Person isn't already set, so this
        never clobbers a Person the user (or the rack-line wizard)
        already chose. There's no separate lookup needed anymore:
        Person and Contact are the same record now, so "is this
        Customer also a Person" is just checking is_person."""
        if self.partner_id and self.partner_id.is_person and not self.person_id:
            self.person_id = self.partner_id

    @api.model
    def _get_rack_kind_config(self):
        """Central config for the three sale-order "rack" product
        types: Ribbon Rack, Tunic Medal Rack, Meskit Medal Rack. Keyed
        by rack_type, used throughout sale.order / sale.order.line /
        rm.sale.line.person.wizard, so adding a future rack type is a
        one-entry change here instead of touching every method.

        unit_field is the SAME field name on both sale.order and
        sale.order.line (each pointing at the matching unit model:
        rm.rack.unit for 'ribbon', rm.medal.rack.unit for the medal
        kinds) so it can be read/written generically with line[field].
        """
        return {
            'ribbon': {
                'product_xmlid': 'ribbon_medal.product_ribbon_rack',
                'label': _('Ribbon Rack'),
                'unit_field': 'rack_unit_id',
                'price_field': 'rack_total_price',
                'issue_method': '_issue_ribbon_rack_unit',
                'issue_args': (),
            },
            'tunic_medal': {
                'product_xmlid': 'ribbon_medal.product_tunic_medal_rack',
                'label': _('Tunic Medal Rack'),
                'unit_field': 'tunic_medal_rack_unit_id',
                'price_field': 'tunic_medal_rack_price',
                'issue_method': '_issue_medal_rack_unit',
                'issue_args': ('l',),
            },
            'meskit_medal': {
                'product_xmlid': 'ribbon_medal.product_meskit_medal_rack',
                'label': _('Meskit Medal Rack'),
                'unit_field': 'meskit_medal_rack_unit_id',
                'price_field': 'meskit_medal_rack_price',
                'issue_method': '_issue_medal_rack_unit',
                'issue_args': ('s',),
            },
        }

    def action_confirm(self):
        config = self._get_rack_kind_config()

        for order in self:
            for line in order.order_line:
                if line.rack_type and not (line.person_id or order.person_id):
                    raise UserError(_(
                        'Line "%(product)s" on "%(order)s" is a %(label)s line with no '
                        'Person set - select one on that line before confirming.'
                    ) % {
                        'product': line.product_id.display_name,
                        'order': order.name,
                        'label': config[line.rack_type]['label'],
                    })

        res = super().action_confirm()

        for order in self:
            for line in order.order_line:
                rack_type = line.rack_type
                if not rack_type:
                    continue
                person = line.person_id or order.person_id
                if not person:
                    continue
                cfg = config[rack_type]
                unit_field = cfg['unit_field']
                if line[unit_field]:
                    continue
                # Re-resolve now, right before committing stock/MOs -
                # the person's combination may have changed (a new
                # award, say) since this line was created, and the
                # actual manufactured/delivered product must match
                # whatever product_id ends up showing on the line.
                variant = person._resolve_rack_variant(rack_type)
                if variant and variant != line.product_id:
                    line.product_id = variant.id
                issue_method = getattr(person, cfg['issue_method'])
                unit, message = issue_method(
                    *cfg['issue_args'], deposited_award_ids=line._rm_deposit_quantities())
                line[unit_field] = unit.id
                if not order[unit_field]:
                    order[unit_field] = unit.id
                order.message_post(body=message)
        return res

    def _rm_order_line_action_views(self):
        """Same fallback-to-standard-list-view approach as
        res.partner._rack_line_action_views - kept as its own copy here
        (rather than a shared mixin) since it's a 2-line helper and
        SaleOrder/res.partner don't otherwise share a base."""
        list_view = self.env.ref('sale.view_order_line_tree', raise_if_not_found=False)
        return [(list_view.id if list_view else False, 'list'), (False, 'form')]

    def action_view_rack_units(self):
        """Combined replacement for the 3 separate "X Rack Unit"
        buttons - opens this order's own lines that have had a unit
        issued (any of the 3 types, delivered or not); the actual
        rm.rack.unit / rm.medal.rack.unit record is reachable from
        there via that line's Ribbon/Tunic/Meskit Rack Unit field."""
        self.ensure_one()
        Line = self.env['sale.order.line']
        return {
            'type': 'ir.actions.act_window',
            'name': _('Rack Units'),
            'res_model': 'sale.order.line',
            'views': self._rm_order_line_action_views(),
            'domain': [('order_id', '=', self.id)] + Line._rm_issued_domain_leaf(),
        }

    def action_open_rack_unit(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _('Ribbon Rack Unit'),
            'res_model': 'rm.rack.unit',
            'view_mode': 'form',
            'res_id': self.rack_unit_id.id,
        }

    def action_open_tunic_rack_unit(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _('Tunic Medal Rack Unit'),
            'res_model': 'rm.medal.rack.unit',
            'view_mode': 'form',
            'res_id': self.tunic_medal_rack_unit_id.id,
        }

    def action_open_meskit_rack_unit(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _('Meskit Medal Rack Unit'),
            'res_model': 'rm.medal.rack.unit',
            'view_mode': 'form',
            'res_id': self.meskit_medal_rack_unit_id.id,
        }

    def _action_open_rack_line_wizard(self, rack_type):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _('Select a Person'),
            'res_model': 'rm.sale.line.person.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {
                'default_order_id': self.id,
                'default_rack_type': rack_type,
                # Pre-fill the wizard's Person from the order's own
                # Person, if it already has one - see
                # rm.sale.line.person.wizard.action_confirm for the
                # reverse direction (wizard -> order) on this same path.
                'default_person_id': self.person_id.id,
            },
        }

    def action_add_ribbon_rack_line(self):
        """Pops the Person-picker wizard and, on confirm, creates a
        brand-new Ribbon Rack line already priced and noted - so there's
        no need to manually pick the Ribbon Rack product from the line's
        product dropdown at all."""
        return self._action_open_rack_line_wizard('ribbon')

    def action_add_tunic_medal_rack_line(self):
        """Same idea as action_add_ribbon_rack_line, for a Tunic (large
        size) Medal Rack line."""
        return self._action_open_rack_line_wizard('tunic_medal')

    def action_add_meskit_medal_rack_line(self):
        """Same idea as action_add_ribbon_rack_line, for a Meskit
        (small size) Medal Rack line."""
        return self._action_open_rack_line_wizard('meskit_medal')


class SaleOrderLine(models.Model):
    _inherit = 'sale.order.line'

    order_date = fields.Datetime(
        related='order_id.date_order', string='Order Date', store=True, readonly=True,
        help="The order's own Order Date, exposed here (stored, so it's "
             "groupable/sortable) for list views like the Person form's "
             "Ordered Racks / Racks Not Delivered smart buttons.")
    person_id = fields.Many2one(
        'res.partner', string='Person', domain=[('is_person', '=', True)],
        help="Whose rack this line is for (Ribbon Rack, Tunic Medal Rack, "
             "or Meskit Medal Rack - see rack_type). Selecting them prices "
             "the line at their current estimated price for that rack type "
             "and, on order confirmation, runs that rack type's Issue "
             "cascade for them (reuses ready stock where possible, "
             "manufactures and reserves a new unit otherwise).")
    rack_unit_id = fields.Many2one(
        'rm.rack.unit', string='Ribbon Rack Unit', readonly=True, copy=False,
        help='The specific Ribbon Rack Product unit produced or handed '
             'over for this line.')
    tunic_medal_rack_unit_id = fields.Many2one(
        'rm.medal.rack.unit', string='Tunic Medal Rack Unit', readonly=True, copy=False,
        help='The specific Tunic Medal Rack unit produced or handed over '
             'for this line.')
    meskit_medal_rack_unit_id = fields.Many2one(
        'rm.medal.rack.unit', string='Meskit Medal Rack Unit', readonly=True, copy=False,
        help='The specific Meskit Medal Rack unit produced or handed over '
             'for this line.')

    @api.model
    def _rm_issued_domain_leaf(self):
        """Domain fragment: this line has had a unit issued for at
        least one of the 3 rack types (regardless of delivered state).
        Shared by the Sale Order form's combined "Rack Unit" button."""
        return [
            '|', '|',
            ('rack_unit_id', '!=', False),
            ('tunic_medal_rack_unit_id', '!=', False),
            ('meskit_medal_rack_unit_id', '!=', False),
        ]

    rack_type = fields.Selection(
        [('ribbon', 'Ribbon Rack'), ('tunic_medal', 'Tunic Medal Rack'), ('meskit_medal', 'Meskit Medal Rack')],
        help='Which of the three rack product types this line is, if any - '
             'drives which Person-picker button/field shows on the line. '
             'A real, stored decision (set once, when the line is '
             'created) rather than derived from product_id - since '
             "product_id is now the person's own specific rack variant, "
             'not a fixed generic product it could otherwise be matched '
             'against.')
    is_rack_line = fields.Boolean(
        string='Is Rack Line',
        compute='_compute_is_rack_line',
        help='Technical flag used by the Sale Order line editor button.'
    )

    @api.depends('rack_type', 'product_id', 'product_id.product_tmpl_id.rm_is_finished_rack')
    def _compute_is_rack_line(self):
        for line in self:
            line.is_rack_line = bool(
                line.rack_type or
                (line.product_id and line.product_id.product_tmpl_id.rm_is_finished_rack)
            )

    def _infer_rack_type_from_product(self):
        self.ensure_one()
        if self.rack_type:
            return self.rack_type
        if not self.product_id:
            return False
        config = self.env['sale.order']._get_rack_kind_config()
        product_tmpl = self.product_id.product_tmpl_id
        for rack_type, cfg in config.items():
            tmpl = self.env.ref(cfg['product_xmlid'], raise_if_not_found=False)
            if tmpl and tmpl == product_tmpl:
                return rack_type
        return False

    deposited_award_quantities = fields.Text(
        string='Customer-Deposited Medal Quantities', copy=True,
        help='JSON map of award record IDs to quantities deposited by the customer. '
             'This records quantities for order pricing and manufacturing only; '
             'it does not create inventory receipts or stock moves.')

    def _rm_deposit_quantities(self):
        self.ensure_one()
        try:
            data = json.loads(self.deposited_award_quantities or '{}')
            return {int(key): max(0, int(value)) for key, value in data.items() if int(value) > 0}
        except (ValueError, TypeError, AttributeError):
            return {}

    @api.onchange('product_id')
    def _onchange_product_id_rack_prompt(self):
        """Picking one of the three generic rack products directly
        (rather than via the "Add Ribbon/Tunic/Meskit" buttons, which
        set rack_type explicitly themselves) is a one-time trigger:
        detect rack_type from it here, then prompt for the Person it's
        for. Once a Person is picked, _apply_rack_person() replaces
        product_id with that person's actual specific rack variant -
        the generic product only ever exists on a line transiently,
        as this detection trigger, on this manual-entry path."""
        if not self.rack_type:
            config = self.env['sale.order']._get_rack_kind_config()
            for rack_type, cfg in config.items():
                tmpl = self.env.ref(cfg['product_xmlid'], raise_if_not_found=False)
                if tmpl and tmpl.product_variant_id == self.product_id:
                    self.rack_type = rack_type
                    break
        if not self.rack_type:
            return
        if self.person_id:
            self._apply_rack_person()
        else:
            label = self.env['sale.order']._get_rack_kind_config()[self.rack_type]['label']
            return {'warning': {
                'title': _('Select a Person'),
                'message': _(
                    "This is the %s product - use the Select Person button "
                    "on this line (save the order first if needed) so it "
                    "can be priced at their rack's current estimated price."
                ) % label,
            }}

    @api.onchange('person_id')
    def _onchange_person_id_rack(self):
        if self.rack_type:
            self._apply_rack_person()

    def action_open_person_wizard(self):
        """Open the Person/deposited-medal editor for this rack line.

        Older/imported lines may have an empty stored rack_type even though
        their product is a finished rack. Repair that value before opening
        the same editor used for newly-created rack lines.
        """
        self.ensure_one()
        rack_type = self._infer_rack_type_from_product()
        if not rack_type:
            raise UserError(_('This Sale Order line is not a recognised rack line.'))
        if not self.rack_type:
            self.rack_type = rack_type
        return {
            'type': 'ir.actions.act_window',
            'name': _('Edit Rack Configuration'),
            'res_model': 'rm.sale.line.person.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {
                'default_line_id': self.id,
                'default_person_id': self.person_id.id,
                'default_rack_type': rack_type,
                'default_initial_deposit_quantities': self.deposited_award_quantities or '{}',
            },
        }

    def _apply_rack_person(self):
        """Price this line at the Person's current estimated price for
        this line's rack_type (minus any customer-deposited medals'
        own cost - see deposited_award_ids), set product_id to their
        CURRENT actual specific rack variant (re-resolved every call,
        so this stays correct even if their combination changed since
        the line was last touched), and add a small note right after
        the product name in the line description, e.g. 'Rack #6 /
        (For: John Doe)'."""
        self.ensure_one()
        if self.person_id and self.rack_type:
            self.price_unit = self.person_id._rack_price(
                self.rack_type, deposited_award_quantities=self._rm_deposit_quantities())
            variant = self.person_id._resolve_rack_variant(self.rack_type)
            if variant:
                self.product_id = variant.id
        else:
            self.price_unit = 0.0
        # Always rebuild the description's first line from the CURRENT
        # product_id (rather than reusing whatever text was already
        # there) - product_id may have just changed above, and the
        # description should track it, not a stale snapshot.
        rest = [l for l in (self.name or '').split('\n')[1:]
                if not l.strip().startswith('(For:') and not l.strip().startswith('(Deposited:')]
        new_lines = [self.product_id.name or '']
        if self.person_id:
            new_lines.append(_('(For: %s)') % self.person_id.rm_rack_label())
        quantities = self._rm_deposit_quantities()
        if quantities:
            awards = self.env['rm.prb'].browse(list(quantities)).exists()
            new_lines.append(_('(Deposited: %s)') % ', '.join('%s × %s' % (award.display_name, quantities[award.id]) for award in awards))
        new_lines.extend(rest)
        self.name = '\n'.join(new_lines)
