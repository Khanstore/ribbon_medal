/** @odoo-module **/

import { registry } from "@web/core/registry";
import { Component } from "@odoo/owl";
import { standardFieldProps } from "@web/views/fields/standard_field_props";
import { many2oneId } from "./rack_ledger";

// Same geometry constants the standard racks use - see ribbon_rack.js
// and medal_rack.js, whose templates these widgets deliberately reuse
// so a customised rack is visually identical to the standard one it
// sits beside on the Compare page.
const RACK_COLUMNS = 4;
const ROW_WIDTH_CM = 12;
const CELL_WIDTH_CM = 3;

/**
 * Fields read off each rm.acquisition.custom row. Declared as
 * relatedFields so they're loaded even though the view's <list> for
 * custom_ledger_ids doesn't (and shouldn't) show all of them.
 */
const CUSTOM_RACK_RELATED_FIELDS = [
    { name: "award_id", type: "many2one", relation: "rm.prb" },
    { name: "sequence", type: "integer" },
    { name: "award_name", type: "char" },
    { name: "is_ribbon", type: "boolean" },
    { name: "is_medal", type: "boolean" },
    { name: "ribbon_image", type: "binary" },
    { name: "medal_image", type: "binary" },
    { name: "attachment_id", type: "many2one", relation: "rm.attachment" },
    { name: "add_to_ribbon", type: "boolean" },
    { name: "add_to_big_medal", type: "boolean" },
    { name: "add_to_mini_medal", type: "boolean" },
];

/**
 * Maps the live (possibly unsaved) rows of a custom_ledger_ids
 * one2many into the cell shape both rack templates expect, keeping
 * only rows whose opt-in flag for THIS rack is ticked.
 *
 * Ordering: by the row's own manual `sequence` - the handle-reordered
 * position in the Customisation list - NOT by the award type's
 * precedence. Being able to reorder freely is the entire reason this
 * table exists, so the customised rack must honour it. Index 0 is the
 * highest-precedence cell, matching what the standard racks' own
 * descending-sequence sort produces.
 *
 * @param {Object} record - the form record.
 * @param {string} fieldName - the bound one2many field name.
 * @param {string} flagField - add_to_ribbon | add_to_big_medal | add_to_mini_medal.
 * @returns {Array} cells, highest precedence first.
 */
function getCustomRackCells(record, fieldName, flagField) {
    const value = record.data[fieldName];
    const records = (value && value.records) || [];
    return records
        .map((r) => r.data)
        .filter((data) => data[flagField] === true && many2oneId(data.award_id))
        .sort((a, b) => (a.sequence || 0) - (b.sequence || 0))
        .map((data) => ({
            award_id: many2oneId(data.award_id),
            name: data.award_name,
            sequence: data.sequence,
            is_ribbon: data.is_ribbon,
            is_medal: data.is_medal,
            has_ribbon_image: !!data.ribbon_image,
            has_medal_image: !!data.medal_image,
            attachment_id: many2oneId(data.attachment_id),
        }));
}

/**
 * Customised Ribbon Rack.
 *
 * Renders `custom_ledger_ids` rows ticked "ribbon" using the standard
 * Ribbon Rack template. Needs no ledger RPC at all (unlike
 * ribbon_rack.js): every row is already an explicit, stored
 * acquisition on the open form, so there is nothing to derive.
 * Updates instantly as rows are ticked, reordered, added or removed,
 * since it reads the form's own live one2many records.
 */
export class CustomRibbonRackField extends Component {
    static template = "ribbon_medal.RibbonRackField";
    static props = { ...standardFieldProps };

    get sortedAwards() {
        return getCustomRackCells(this.props.record, this.props.name, "add_to_ribbon");
    }

    /**
     * Same 4-per-row layout rule as the standard ribbon rack: only the
     * FIRST (topmost) row is ever partial.
     */
    get rows() {
        const items = this.sortedAwards;
        const count = items.length;
        if (!count) {
            return [];
        }
        const ascending = [...items].reverse();
        const remainder = count % RACK_COLUMNS;
        const topRowSize = remainder === 0 ? RACK_COLUMNS : remainder;
        const rackRows = [ascending.slice(0, topRowSize)];
        for (let i = topRowSize; i < ascending.length; i += RACK_COLUMNS) {
            rackRows.push(ascending.slice(i, i + RACK_COLUMNS));
        }
        return rackRows;
    }

    getImageUrl(cell) {
        if (!cell || !cell.has_ribbon_image || !cell.award_id) {
            return false;
        }
        return `/web/image/rm.prb/${cell.award_id}/ribbon_image`;
    }

    getDeviceImageUrl(cell) {
        if (!cell || !cell.attachment_id) {
            return false;
        }
        return `/web/image/rm.attachment/${cell.attachment_id}/image`;
    }
}

/**
 * Customised Medal Rack - Tunic or Mini/Meskit depending on the
 * `medal_type` option ("big" | "mini"), which selects which opt-in
 * flag on each row is honoured. Reuses the standard Medal Rack
 * template, including its fixed-12cm-bar overlap behaviour.
 */
export class CustomMedalRackField extends Component {
    static template = "ribbon_medal.MedalRackField";
    static props = {
        ...standardFieldProps,
        medalType: { type: String, optional: true },
    };

    get _flagField() {
        return this.props.medalType === "mini" ? "add_to_mini_medal" : "add_to_big_medal";
    }

    get sortedAwards() {
        return getCustomRackCells(
            this.props.record, this.props.name, this._flagField
        ).filter((cell) => cell.is_medal);
    }

    /** Single row, highest precedence on the right. */
    get row() {
        return [...this.sortedAwards].reverse();
    }

    getCellStyle(index, count) {
        const styles = [`z-index: ${count - index}`];
        if (index > 0 && count > 1) {
            const overlapCm = Math.max(
                0,
                CELL_WIDTH_CM - (ROW_WIDTH_CM - CELL_WIDTH_CM) / (count - 1)
            );
            if (overlapCm) {
                styles.push(`margin-left: -${overlapCm.toFixed(3)}cm`);
            }
        }
        return styles.join("; ");
    }

    getImageUrl(cell) {
        if (!cell || !cell.has_medal_image || !cell.award_id) {
            return false;
        }
        return `/web/image/rm.prb/${cell.award_id}/medal_image`;
    }

    getDeviceImageUrl(cell) {
        if (!cell || !cell.attachment_id) {
            return false;
        }
        return `/web/image/rm.attachment/${cell.attachment_id}/image`;
    }
}

export const customRibbonRackField = {
    component: CustomRibbonRackField,
    supportedTypes: ["one2many"],
    relatedFields: CUSTOM_RACK_RELATED_FIELDS,
};

export const customMedalRackField = {
    component: CustomMedalRackField,
    supportedTypes: ["one2many"],
    relatedFields: CUSTOM_RACK_RELATED_FIELDS,
    extractProps: ({ options }) => ({
        medalType: (options && options.medal_type) || "big",
    }),
};

registry.category("fields").add("custom_ribbon_rack", customRibbonRackField);
registry.category("fields").add("custom_medal_rack", customMedalRackField);
