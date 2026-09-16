/** @odoo-module **/

import { registry } from "@web/core/registry";
import { Component, useState, onWillUpdateProps } from "@odoo/owl";
import { standardFieldProps } from "@web/views/fields/standard_field_props";
import { useDebounced } from "@web/core/utils/timing";

/**
 * Char field that pushes its value to the record - and therefore
 * triggers the onchange that recomputes rm.sale.line.person.wizard's
 * result_person_ids - on every keystroke (debounced), instead of only
 * on blur/Enter like a plain Char field.
 *
 * Renders its own <input> and keeps local text state on each
 * keystroke so typing itself is never blocked waiting on the
 * server; the debounced RPC-triggering update follows ~300ms after
 * the person stops typing.
 */
export class RmLiveSearchField extends Component {
    static template = "ribbon_medal.RmLiveSearchField";
    static props = { ...standardFieldProps, placeholder: { type: String, optional: true } };

    setup() {
        this.state = useState({ value: this.props.record.data[this.props.name] || "" });
        this.commitToRecord = useDebounced((value) => {
            this.props.record.update({ [this.props.name]: value });
        }, 300);
        onWillUpdateProps((nextProps) => {
            const recordValue = nextProps.record.data[this.props.name] || "";
            if (recordValue !== this.state.value) {
                this.state.value = recordValue;
            }
        });
    }

    onInput(ev) {
        this.state.value = ev.target.value;
        this.commitToRecord(this.state.value);
    }
}

export const rmLiveSearchField = {
    component: RmLiveSearchField,
    displayName: "Live Search",
    supportedTypes: ["char"],
    extractProps: ({ attrs }) => ({
        placeholder: attrs && attrs.placeholder,
    }),
};

registry.category("fields").add("rm_live_search", rmLiveSearchField);
