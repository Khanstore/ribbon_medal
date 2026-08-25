/** @odoo-module **/

import { registry } from "@web/core/registry";
import { Component } from "@odoo/owl";
import { standardFieldProps } from "@web/views/fields/standard_field_props";

// Physical size of the mount: a fixed 12cm bar, cells nominally 3cm
// wide. Unlike the ribbon rack's 4-column grid, medals traditionally
// mount as a single row - when more than ROW_WIDTH_CM / CELL_WIDTH_CM
// (= 4) of them are worn, they overlap each other equally so the whole
// row still fits the fixed 12cm width, same as a real medal bar.
const ROW_WIDTH_CM = 12;
const CELL_WIDTH_CM = 3;

/**
 * Medal Rack widget.
 *
 * Sibling of ribbon_rack.js - same many2many `rack_ledger_ids` on
 * res.person, ordered by descending `sequence` (highest precedence on
 * the right, matching the ribbon rack's convention). The two real
 * differences: this rack only ever shows decorations that actually
 * have a medal (`is_medal`) - a person's ribbon rack often includes
 * ribbon-only decorations that never had a corresponding medal struck,
 * and those have no business appearing here - and it renders as a
 * single fixed-width row rather than a multi-row grid, overlapping
 * cells equally once there are more than 4 to fit them all within the
 * fixed 12cm width. Falls back to a text placeholder per cell when no
 * medal_image is set, same as ribbon_rack does for ribbon_image.
 */
export class MedalRackField extends Component {
    static template = "ribbon_medal.MedalRackField";
    static props = { ...standardFieldProps };

    /**
     * @returns {Array} medal-eligible records sorted by descending
     * sequence (highest sequence = highest precedence, first in array).
     */
    get sortedAwards() {
        const value = this.props.record.data[this.props.name];
        const records = (value && value.records) || [];
        return records
            .filter((r) => r.data.is_medal)
            .sort((a, b) => (b.data.sequence || 0) - (a.data.sequence || 0));
    }

    /**
     * @returns {Array} a single row, left-to-right, highest precedence
     * on the right (same visual convention as ribbon_rack's rows).
     */
    get row() {
        return [...this.sortedAwards].reverse();
    }

    /**
     * Equal negative margin-left applied to every cell but the first in
     * the row, so N cells of nominal CELL_WIDTH_CM each still total
     * exactly ROW_WIDTH_CM. Yields 0 (no overlap) whenever N <= 4,
     * since 4 cells already exactly fill 12cm on their own; only grows
     * once there are more than that to fit. Also stacks the leftmost
     * cell on top of the ones to its right (decreasing z-index
     * left-to-right) wherever they overlap.
     * @param {number} index - this cell's position in the row.
     * @param {number} count - total cells in the row.
     */
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
        if (!cell || !cell.data.medal_image) {
            return false;
        }
        return `/web/image/rm.acquisition/${cell.resId}/medal_image`;
    }

    getDeviceImageUrl(cell) {
        // Same device/attachment badge concept as the ribbon rack (e.g.
        // a repeat-award numeral or club worn on the medal's own
        // suspension ribbon) - sourced from this acquisition's
        // attachment_id.
        if (!cell || !cell.data.attachment_id) {
            return false;
        }
        const attachmentId = Array.isArray(cell.data.attachment_id)
            ? cell.data.attachment_id[0]
            : cell.data.attachment_id;
        return `/web/image/rm.attachment/${attachmentId}/image`;
    }
}

export const medalRackField = {
    component: MedalRackField,
    supportedTypes: ["many2many"],
    relatedFields: [
        { name: "name", type: "char" },
        { name: "sequence", type: "float" },
        { name: "is_ribbon", type: "boolean" },
        { name: "is_medal", type: "boolean" },
        { name: "medal_image", type: "binary" },
        { name: "attachment_id", type: "many2one" },
    ],
};

registry.category("fields").add("medal_rack", medalRackField);
