/** @odoo-module **/

import { registry } from "@web/core/registry";
import { Component } from "@odoo/owl";
import { standardFieldProps } from "@web/views/fields/standard_field_props";
import {
    computeMergedLedger, useRackLedgerContext, RACK_LEDGER_FIELD_DEPENDENCIES,
    getO2mRows, getServiceConfirmationDate, getReferencedPrbIds, many2oneId,
} from "./rack_ledger";

// 4-per-row grid; the LAST (most recent) row can be shorter, matching
// how ribbon racks are actually worn - a partial top row, not a
// partial bottom row.
const RACK_COLUMNS = 4;

/**
 * Ribbon Rack widget.
 *
 * Renders `rack_ledger_ids` (a many2many onto rm.acquisition, the
 * consolidated award ledger) as a grid of ribbon cells, 4 per row,
 * ordered by descending `sequence` (highest precedence first) then
 * laid out left-to-right with the top row holding the remainder so
 * only the LAST row is ever partial.
 *
 * As of this version, the actual ledger shown is computed INSTANTLY
 * client-side (see rack_ledger.js) from the form's own live Personal
 * Award / Mission rows, rather than solely from the server-computed
 * rack_ledger_ids - so adding/editing/removing an award updates this
 * rack immediately, without saving. rack_ledger_ids itself is still
 * read, as a same-shape fallback for the very first paint before the
 * one small RPC this needs (for Seniority/Batch rules and exclusions)
 * has resolved.
 */
export class RibbonRackField extends Component {
    static template = "ribbon_medal.RibbonRackField";
    static props = { ...standardFieldProps };
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
     * @returns {Array} instant, client-computed ledger rows - see
     * rack_ledger.js. Falls back to the server-computed
     * rack_ledger_ids many2many (this field's own bound value) only
     * before the RPC context has resolved (e.g. right after opening
     * the form), so the rack isn't just empty on first paint.
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

    /**
     * @returns {Array} all ledger rows sorted by descending sequence
     * (highest sequence = highest precedence, first in array).
     */
    get sortedAwards() {
        return [...this._ledgerRows].sort((a, b) => (b.sequence || 0) - (a.sequence || 0));
    }

    /**
     * @returns {Array<Array>} rows of up to RACK_COLUMNS cells each,
     * left-to-right, highest precedence on the right of each row -
     * only the FIRST (topmost) row is ever partial.
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
        // A small badge for a repeat-award device (e.g. a numeral worn
        // on the ribbon bar), sourced from this acquisition's own
        // attachment_id (falling back to the award type's default -
        // already resolved into attachment_id by this point).
        if (!cell || !cell.attachment_id) {
            return false;
        }
        return `/web/image/rm.attachment/${cell.attachment_id}/image`;
    }
}

export const ribbonRackField = {
    component: RibbonRackField,
    supportedTypes: ["many2many"],
    relatedFields: [
        { name: "award_id", type: "many2one" },
        { name: "name", type: "char" },
        { name: "sequence", type: "float" },
        { name: "is_ribbon", type: "boolean" },
        { name: "is_medal", type: "boolean" },
        { name: "ribbon_image", type: "binary" },
        { name: "medal_image", type: "binary" },
        { name: "attachment_id", type: "many2one" },
    ],
};

registry.category("fields").add("ribbon_rack", ribbonRackField);
