/** @odoo-module **/

import { registry } from "@web/core/registry";
import { Component } from "@odoo/owl";
import { standardFieldProps } from "@web/views/fields/standard_field_props";

const RACK_COLUMNS = 4;

/**
 * Ribbon Rack widget.
 *
 * Displays the many2many `obtained_awards_ids` of a res.person as a
 * military-style "ribbon rack": a grid of RACK_COLUMNS columns where
 * decorations are ordered by ascending `sequence` (lowest sequence =
 * highest precedence, matching Odoo's usual "sequence" convention).
 *
 * Filling pattern: the decoration with the lowest sequence is placed in
 * the bottom-right cell of the rack; subsequent decorations are placed
 * moving right-to-left along the bottom row, then continuing on the row
 * above, until the decoration with the highest sequence ends up as far
 * toward the top-left as the rack requires. Rows are rendered one below
 * another (bottom row = highest precedence, full RACK_COLUMNS row; rows
 * above hold the remaining, lower-precedence decorations). Unlike a fixed
 * grid, a row that isn't full (the topmost one, when count isn't a
 * multiple of RACK_COLUMNS) is horizontally centered rather than padded
 * with blank cells.
 */
export class RibbonRackField extends Component {
    static template = "ribbon_medal.RibbonRackField";
    static props = { ...standardFieldProps };

    /**
     * @returns {Array} records sorted by ascending sequence
     */
    get sortedAwards() {
        const value = this.props.record.data[this.props.name];
        const records = (value && value.records) || [];
        return [...records].sort((a, b) => {
            const seqA = a.data.sequence || 0;
            const seqB = b.data.sequence || 0;
            return seqA - seqB;
        });
    }

    /**
     * @returns {Array<Array>} array of rows, top row first. Each row is a
     * left-to-right array of items (descending precedence within the row,
     * highest precedence on the right) with no blank placeholders - the
     * topmost row simply has fewer cells when count isn't a multiple of
     * RACK_COLUMNS, and is centered via CSS instead of padded.
     */
    get rows() {
        const items = this.sortedAwards;
        const count = items.length;
        if (!count) {
            return [];
        }
        // Descending precedence (index 0 = lowest precedence overall), so
        // slicing from the start naturally builds rows top (lowest
        // precedence) to bottom (highest precedence), each already in
        // left-to-right order.
        const descending = [...items].reverse();
        const remainder = count % RACK_COLUMNS;
        const topRowSize = remainder === 0 ? RACK_COLUMNS : remainder;

        const rows = [descending.slice(0, topRowSize)];
        for (let i = topRowSize; i < descending.length; i += RACK_COLUMNS) {
            rows.push(descending.slice(i, i + RACK_COLUMNS));
        }
        return rows;
    }

    getImageUrl(cell) {
        if (!cell) {
            return false;
        }
        const data = cell.data;
        const image = data.ribbon_image || data.medal_image;
        if (!image) {
            return false;
        }
        return `data:image/png;base64,${image}`;
    }
}

export const ribbonRackField = {
    component: RibbonRackField,
    supportedTypes: ["many2many"],
    relatedFields: [
        { name: "name", type: "char" },
        { name: "sequence", type: "float" },
        { name: "is_ribbon", type: "boolean" },
        { name: "is_medal", type: "boolean" },
        { name: "ribbon_image", type: "binary" },
        { name: "medal_image", type: "binary" },
    ],
};

registry.category("fields").add("ribbon_rack", ribbonRackField);