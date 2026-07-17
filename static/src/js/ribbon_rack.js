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
 * decorations are ordered by descending `seniority_sequence`.
 *
 * Filling pattern: the decoration with the highest seniority_sequence is
 * placed in the bottom-right cell of the grid; subsequent decorations are
 * placed moving right-to-left along the bottom row, then continuing on the
 * row above, until the decoration with the lowest seniority_sequence ends
 * up as far toward the top-left as the grid requires. Any unfilled cells
 * (when the count isn't a multiple of RACK_COLUMNS) are left empty at the
 * start (top-left) of the top row.
 */
export class RibbonRackField extends Component {
    static template = "ribbon_medal.RibbonRackField";
    static props = { ...standardFieldProps };

    /**
     * @returns {Array} records sorted by descending seniority_sequence
     */
    get sortedAwards() {
        const value = this.props.record.data[this.props.name];
        const records = (value && value.records) || [];
        return [...records].sort((a, b) => {
            const seqA = a.data.seniority_sequence || 0;
            const seqB = b.data.seniority_sequence || 0;
            return seqB - seqA;
        });
    }

    /**
     * @returns {Array} flat array of length rows * RACK_COLUMNS, top-left
     * to bottom-right reading order, with `null` for empty cells.
     */
    get gridCells() {
        const items = this.sortedAwards;
        const count = items.length;
        if (!count) {
            return [];
        }
        const rows = Math.ceil(count / RACK_COLUMNS);
        const totalCells = rows * RACK_COLUMNS;
        const grid = new Array(totalCells).fill(null);

        for (let i = 0; i < count; i++) {
            // i = 0 is the highest-seniority item, destined for the
            // bottom-right-most cell; increasing i moves left, then up.
            const rowFromBottom = Math.floor(i / RACK_COLUMNS);
            const colFromRight = i % RACK_COLUMNS;
            const row = rows - 1 - rowFromBottom;
            const col = RACK_COLUMNS - 1 - colFromRight;
            grid[row * RACK_COLUMNS + col] = items[i];
        }
        return grid;
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
        { name: "award_name", type: "char" },
        { name: "seniority_sequence", type: "integer" },
        { name: "is_ribbon", type: "boolean" },
        { name: "is_medal", type: "boolean" },
        { name: "ribbon_image", type: "binary" },
        { name: "medal_image", type: "binary" },
    ],
};

registry.category("fields").add("ribbon_rack", ribbonRackField);
