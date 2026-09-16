/** @odoo-module **/

import { registry } from "@web/core/registry";
import { Component, onWillUnmount } from "@odoo/owl";
import { standardFieldProps } from "@web/views/fields/standard_field_props";

/**
 * A plain Char input that pushes every keystroke to the record
 * (debounced ~300ms), instead of only on blur like the standard Char
 * field. Used for rm.sale.line.person.wizard's Search field, so
 * result_person_ids (a compute field depending on this one via
 * @api.depends) refreshes live as the user types, rather than only
 * after they click away from the field.
 */
export class RmLiveSearchCharField extends Component {
    static template = "ribbon_medal.RmLiveSearchCharField";
    static props = { ...standardFieldProps };

    setup() {
        this._debounceTimer = null;
        onWillUnmount(() => {
            if (this._debounceTimer) {
                clearTimeout(this._debounceTimer);
            }
        });
    }

    get value() {
        return this.props.record.data[this.props.name] || "";
    }

    onInput(ev) {
        const value = ev.target.value;
        if (this._debounceTimer) {
            clearTimeout(this._debounceTimer);
        }
        this._debounceTimer = setTimeout(() => {
            this.props.record.update({ [this.props.name]: value });
        }, 300);
    }
}

export const rmLiveSearchCharField = {
    component: RmLiveSearchCharField,
    supportedTypes: ["char"],
};

registry.category("fields").add("rm_live_search", rmLiveSearchCharField);
