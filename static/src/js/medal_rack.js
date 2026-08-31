/** @odoo-module **/

import { registry } from "@web/core/registry";
import { Component } from "@odoo/owl";
import { standardFieldProps } from "@web/views/fields/standard_field_props";
<<<<<<< HEAD
import {
    computeMergedLedger, useRackLedgerContext, RACK_LEDGER_FIELD_DEPENDENCIES,
    getO2mRows, getServiceConfirmationDate, getReferencedPrbIds, many2oneId,
} from "./rack_ledger";
=======
>>>>>>> bb3a35d8c0f0303a5d80a0b497603fa7185d7356

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
<<<<<<< HEAD
 * Sibling of ribbon_rack.js - same underlying ledger (see
 * rack_ledger.js), ordered by descending `sequence` (highest
 * precedence on the right, matching the ribbon rack's convention).
 * The two real differences: this rack only ever shows decorations
 * that actually have a medal (`is_medal`) - a person's ribbon rack
 * often includes ribbon-only decorations that never had a
 * corresponding medal struck, and those have no business appearing
 * here - and it renders as a single fixed-width row rather than a
 * multi-row grid, overlapping cells equally once there are more than
 * 4 to fit them all within the fixed 12cm width. Falls back to a text
 * placeholder per cell when no medal image is set, same as
 * ribbon_rack does for its own images.
=======
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
>>>>>>> bb3a35d8c0f0303a5d80a0b497603fa7185d7356
 */
export class MedalRackField extends Component {
    static template = "ribbon_medal.MedalRackField";
    static props = { ...standardFieldProps };
<<<<<<< HEAD
    static fieldDependencies = RACK_LEDGER_FIELD_DEPENDENCIES;

    setup() {
        const { state, ensureFresh } = useRackLedgerContext(
            () => this.props.record.resId,
            () => many2oneId(this.props.record.data.force_id),
            () => getReferencedPrbIds(this._personalRows, this._missionRows)
        );
        this._ledgerState = state;
        this._ensureFresh = ensureFresh;
    }

    get _personalRows() {
        return getO2mRows(this.props.record, "personal_award_ledger_ids");
    }

    get _missionRows() {
        return getO2mRows(this.props.record, "mission_ledger_ids");
    }

    /**
     * @returns {Array} instant, client-computed ledger rows, medal
     * decorations only - see rack_ledger.js and ribbon_rack.js's own
     * _ledgerRows for the fallback-before-RPC-resolves rationale.
     */
    get _ledgerRows() {
        this._ensureFresh();
        const { prbAttrs, seniorityRules, batchRules } = this._ledgerState;
        if (!Object.keys(prbAttrs).length && !seniorityRules.length && !batchRules.length) {
            const value = this.props.record.data[this.props.name];
            return ((value && value.records) || []).map((r) => ({
                award_id: many2oneId(r.data.award_id) || false,
                name: r.data.name,
                sequence: r.data.sequence,
                is_ribbon: r.data.is_ribbon,
                is_medal: r.data.is_medal,
                has_ribbon_image: !!r.data.ribbon_image,
                has_medal_image: !!r.data.medal_image,
                attachment_id: many2oneId(r.data.attachment_id),
            }));
        }
        return computeMergedLedger({
            personalRows: this._personalRows,
            missionRows: this._missionRows,
            prbAttrs,
            seniorityRules,
            batchRules,
            excludedDecorationIds: this._ledgerState.excludedDecorationIds,
            serviceConfirmationDate: getServiceConfirmationDate(this.props.record),
        });
    }
=======
>>>>>>> bb3a35d8c0f0303a5d80a0b497603fa7185d7356

    /**
     * @returns {Array} medal-eligible records sorted by descending
     * sequence (highest sequence = highest precedence, first in array).
     */
    get sortedAwards() {
<<<<<<< HEAD
        return this._ledgerRows
            .filter((r) => r.is_medal)
            .sort((a, b) => (b.sequence || 0) - (a.sequence || 0));
=======
        const value = this.props.record.data[this.props.name];
        const records = (value && value.records) || [];
        return records
            .filter((r) => r.data.is_medal)
            .sort((a, b) => (b.data.sequence || 0) - (a.data.sequence || 0));
>>>>>>> bb3a35d8c0f0303a5d80a0b497603fa7185d7356
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
<<<<<<< HEAD
        if (!cell || !cell.has_medal_image || !cell.award_id) {
            return false;
        }
        return `/web/image/rm.prb/${cell.award_id}/medal_image`;
=======
        if (!cell || !cell.data.medal_image) {
            return false;
        }
        return `/web/image/rm.acquisition/${cell.resId}/medal_image`;
>>>>>>> bb3a35d8c0f0303a5d80a0b497603fa7185d7356
    }

    getDeviceImageUrl(cell) {
        // Same device/attachment badge concept as the ribbon rack (e.g.
<<<<<<< HEAD
        // a repeat-award numeral or clasp worn on the medal's own
        // suspension ribbon) - sourced from this acquisition's
        // attachment_id.
        if (!cell || !cell.attachment_id) {
            return false;
        }
        return `/web/image/rm.attachment/${cell.attachment_id}/image`;
=======
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
>>>>>>> bb3a35d8c0f0303a5d80a0b497603fa7185d7356
    }
}

export const medalRackField = {
    component: MedalRackField,
    supportedTypes: ["many2many"],
    relatedFields: [
<<<<<<< HEAD
        { name: "award_id", type: "many2one" },
=======
>>>>>>> bb3a35d8c0f0303a5d80a0b497603fa7185d7356
        { name: "name", type: "char" },
        { name: "sequence", type: "float" },
        { name: "is_ribbon", type: "boolean" },
        { name: "is_medal", type: "boolean" },
        { name: "medal_image", type: "binary" },
<<<<<<< HEAD
        { name: "ribbon_image", type: "binary" },
=======
>>>>>>> bb3a35d8c0f0303a5d80a0b497603fa7185d7356
        { name: "attachment_id", type: "many2one" },
    ],
};

registry.category("fields").add("medal_rack", medalRackField);
