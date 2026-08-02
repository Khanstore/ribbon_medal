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
 * decorations are ordered by descending `sequence` (highest sequence =
 * highest precedence).
 *
 * Filling pattern: the decoration with the highest sequence is placed in
 * the bottom-right cell of the rack; subsequent decorations are placed
 * moving right-to-left along the bottom row, then continuing on the row
 * above, until the decoration with the lowest sequence ends up as far
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
     * @returns {Array} records sorted by descending sequence (highest
     * sequence = highest precedence, first in the array).
     */
    get sortedAwards() {
        const value = this.props.record.data[this.props.name];
        const records = (value && value.records) || [];
        return [...records].sort((a, b) => {
            const seqA = a.data.sequence || 0;
            const seqB = b.data.sequence || 0;
            return seqB - seqA;
        });
    }

    /**
     * @returns {Array<Array>} array of rows, top row first. Each row is a
     * left-to-right array of items (ascending precedence within the row,
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
        // Ascending precedence (index 0 = lowest precedence overall), so
        // slicing from the start naturally builds rows top (lowest
        // precedence) to bottom (highest precedence), each already in
        // left-to-right order.
        const ascending = [...items].reverse();
        const remainder = count % RACK_COLUMNS;
        const topRowSize = remainder === 0 ? RACK_COLUMNS : remainder;

        const rows = [ascending.slice(0, topRowSize)];
        for (let i = topRowSize; i < ascending.length; i += RACK_COLUMNS) {
            rows.push(ascending.slice(i, i + RACK_COLUMNS));
        }
        return rows;
    }

    getImageUrl(cell) {
        if (!cell) {
            return false;
        }
        // Deliberately ribbon_image only (not medal_image) - this is
        // specifically the Ribbon Rack, so it should always show the
        // ribbon's product image, never fall back to the medal's.
        // ribbon_image itself is still fetched (see relatedFields below)
        // just to know whether one exists; the actual <img> src is
        // served straight from the rm.prb record via Odoo's image
        // controller, which serves whatever format was actually
        // uploaded (a hand-built base64 data URI hardcoded to PNG can
        // fail to render if the source image is JPEG/GIF/etc).
        if (!cell.data.ribbon_image) {
            return false;
        }
        return `/web/image/rm.prb/${cell.resId}/ribbon_image`;
    }

    getDeviceImageUrl(cell) {
        // Small device/attachment badge (e.g. a repeat-award numeral or
        // club) worn on top of the ribbon - sourced from this PRB's own
        // attachment_id, same served-by-Odoo approach as getImageUrl.
        if (!cell || !cell.data.device_image) {
            return false;
        }
        return `/web/image/rm.prb/${cell.resId}/device_image`;
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
        { name: "device_image", type: "binary" },
    ],
};

registry.category("fields").add("ribbon_rack", ribbonRackField);