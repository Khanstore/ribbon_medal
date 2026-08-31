/** @odoo-module **/

import { useState } from "@odoo/owl";
import { useService } from "@web/core/utils/hooks";

/**
 * Shared INSTANT, client-side replica of rm.acquisition's SQL view -
 * see that model's own docstring in rm_acquisition.py for the
 * authoritative rules being mirrored here. Used by both the Ribbon
 * Rack and Medal Rack widgets so a change to a Personal Award,
 * Mission, the person's Force, or their Service Confirmation Date is
 * reflected on both racks immediately - no Save needed.
 *
 * WHY THIS EXISTS: rm.acquisition is a read-only PostgreSQL VIEW, so
 * its rows only ever reflect committed data - editing the Award/
 * Mission tabs on an open, unsaved form has no effect on it until the
 * record is actually saved. To get instant feedback, the same merge/
 * filter/sort logic that view's SQL implements is replicated here in
 * JavaScript, fed by the form's own live (possibly unsaved) Personal
 * Award / Mission rows plus a small RPC (res.person.
 * get_rack_widget_context) for the two pieces that can't be read off
 * the open form: the Seniority/Batch rm.prb rules for this person's
 * Force, and this person's active award exclusions.
 *
 * MAINTENANCE WARNING: kept in sync with rm.acquisition's SQL view BY
 * HAND. If that view's logic changes (models/rm_acquisition.py), this
 * must change too.
 */

/**
 * Full elapsed years between `dateStr` (YYYY-MM-DD) and today, using
 * the same calendar-based (not 365-day) rule Postgres' age() function
 * - and this module's own res.person._compute_service_age - both use.
 * @param {string|false} dateStr
 * @returns {number|null} null when dateStr is falsy.
 */
export function fullYearsSince(dateStr) {
    if (!dateStr) {
        return null;
    }
    const start = new Date(dateStr);
    const now = new Date();
    let years = now.getFullYear() - start.getFullYear();
    const nowMonthDay = now.getMonth() * 100 + now.getDate();
    const startMonthDay = start.getMonth() * 100 + start.getDate();
    if (nowMonthDay < startMonthDay) {
        years -= 1;
    }
    return years;
}

/** Many2one values on record.data are [id, label] or falsy - unwrap. */
export function many2oneId(value) {
    if (!value) {
        return false;
    }
    return Array.isArray(value) ? value[0] : value;
}

/**
 * Builds the merged, exclusion-filtered ledger - NOT sorted, and NOT
 * filtered by is_ribbon/is_medal (each widget does that itself, same
 * as before this change). Mirrors rm.acquisition's UNION ALL of
 * Personal Awards + Missions + Seniority + Batch, then its exclusion
 * NOT EXISTS filter.
 *
 * @param {Object} params
 * @param {Array} params.personalRows - raw .data of each
 *   personal_award_ledger_ids record (award_id, award_year,
 *   attachment_id, active, add_to_big_medal, add_to_mini_medal).
 * @param {Array} params.missionRows - same shape, keyed by mission_id
 *   instead of award_id.
 * @param {Object} params.prbAttrs - {prbId: {...display attrs...}},
 *   from get_rack_widget_context.
 * @param {Array} params.seniorityRules - from get_rack_widget_context.
 * @param {Array} params.batchRules - from get_rack_widget_context.
 * @param {Array} params.excludedDecorationIds - from
 *   get_rack_widget_context.
 * @param {string|false} params.serviceConfirmationDate - YYYY-MM-DD.
 * @returns {Array} of {source, award_id, year, note, attachment_id,
 *   add_to_big_medal, add_to_mini_medal, name, sequence, is_ribbon,
 *   is_medal, has_ribbon_image, has_medal_image}.
 */
export function computeMergedLedger({
    personalRows, missionRows, prbAttrs, seniorityRules, batchRules,
    excludedDecorationIds, serviceConfirmationDate,
}) {
    const excluded = new Set(excludedDecorationIds || []);
    const isExcluded = (attrs) =>
        !!attrs && (
            (attrs.ribbon_decoration_id && excluded.has(attrs.ribbon_decoration_id)) ||
            (attrs.medal_decoration_id && excluded.has(attrs.medal_decoration_id))
        );

    const rows = [];

    const pushDirectRows = (sourceRows, awardField, source) => {
        for (const row of sourceRows || []) {
            if (row.active === false) {
                continue; // WHERE pa.active IS TRUE / mp.active IS TRUE
            }
            const awardId = many2oneId(row[awardField]);
            if (!awardId) {
                continue; // WHERE pa.award_id IS NOT NULL / mp.mission_id IS NOT NULL
            }
            const attrs = prbAttrs[awardId];
            if (!attrs || isExcluded(attrs)) {
                continue;
            }
            rows.push({
                source,
                year: row.award_year || false,
                note: row.note || false,
                attachment_id: many2oneId(row.attachment_id) || attrs.default_attachment_id || false,
                // COALESCE(..., TRUE): an unset/false value still defaults to TRUE.
                add_to_big_medal: row.add_to_big_medal !== false,
                add_to_mini_medal: row.add_to_mini_medal !== false,
                ...attrs,
                award_id: awardId,
            });
        }
    };
    pushDirectRows(personalRows, "award_id", "personal");
    pushDirectRows(missionRows, "mission_id", "mission");

    const years = fullYearsSince(serviceConfirmationDate);
    if (years !== null) {
        for (const rule of seniorityRules || []) {
            if (years < rule.service_age || isExcluded(rule)) {
                continue;
            }
            rows.push({
                source: "seniority", year: false, note: false,
                attachment_id: rule.default_attachment_id || false,
                add_to_big_medal: true, add_to_mini_medal: true,
                ...rule, award_id: rule.id,
            });
        }
        for (const rule of batchRules || []) {
            if (serviceConfirmationDate >= rule.starting_date || isExcluded(rule)) {
                continue;
            }
            rows.push({
                source: "batch", year: false, note: false,
                attachment_id: rule.default_attachment_id || false,
                add_to_big_medal: true, add_to_mini_medal: true,
                ...rule, award_id: rule.id,
            });
        }
    }

    return rows;
}

/**
 * OWL hook: fetches (and keeps fresh) the RPC-only ingredients -
 * Seniority/Batch rules for the person's Force, this person's award
 * exclusions, and rm.prb display attributes for every award actually
 * referenced right now - and exposes them as reactive state.
 *
 * Call once per widget in setup(). Re-fetches automatically, deduped
 * by a cache key, only when the Force or the SET of referenced awards
 * actually changes - not on every unrelated re-render.
 *
 * @param {() => number|false} getPersonId
 * @param {() => number|false} getForceId
 * @param {() => Set<number>} getPrbIds
 * @returns {{state: Object, ensureFresh: () => void}}
 */
export function useRackLedgerContext(getPersonId, getForceId, getPrbIds) {
    const orm = useService("orm");
    const state = useState({
        prbAttrs: {}, seniorityRules: [], batchRules: [], excludedDecorationIds: [],
    });
    let lastKey = null;

    const ensureFresh = () => {
        const forceId = getForceId();
        const prbIds = [...getPrbIds()].sort((a, b) => a - b);
        const key = `${forceId || 0}|${prbIds.join(",")}`;
        if (key === lastKey) {
            return;
        }
        lastKey = key;
        if (!forceId && !prbIds.length) {
            return;
        }
        orm.call("res.person", "get_rack_widget_context", [getPersonId(), forceId, prbIds])
            .then((result) => {
                if (key !== lastKey) {
                    return; // a newer request has since superseded this one - discard
                }
                Object.assign(state, result);
            });
    };

    return { state, ensureFresh };
}

/** Shared fieldDependencies declaration - see ribbon_rack.js / medal_rack.js. */
export const RACK_LEDGER_FIELD_DEPENDENCIES = [
    {
        name: "personal_award_ledger_ids", type: "one2many", relation: "rm.personal.awards",
        fields: [
            { name: "award_id", type: "many2one", relation: "rm.prb" },
            { name: "award_year", type: "integer" },
            { name: "note", type: "char" },
            { name: "attachment_id", type: "many2one", relation: "rm.attachment" },
            { name: "active", type: "boolean" },
            { name: "add_to_big_medal", type: "boolean" },
            { name: "add_to_mini_medal", type: "boolean" },
        ],
    },
    {
        name: "mission_ledger_ids", type: "one2many", relation: "rm.mission.posting",
        fields: [
            { name: "mission_id", type: "many2one", relation: "rm.prb" },
            { name: "award_year", type: "integer" },
            { name: "note", type: "char" },
            { name: "attachment_id", type: "many2one", relation: "rm.attachment" },
            { name: "active", type: "boolean" },
            { name: "add_to_big_medal", type: "boolean" },
            { name: "add_to_mini_medal", type: "boolean" },
        ],
    },
    { name: "force_id", type: "many2one", relation: "rm.forces" },
    { name: "service_confirmation_date", type: "date" },
];

/** Shared field-reading helpers - see ribbon_rack.js / medal_rack.js. */
export function getO2mRows(record, fieldName) {
    const value = record.data[fieldName];
    return ((value && value.records) || []).map((r) => r.data);
}

export function getServiceConfirmationDate(record) {
    const value = record.data.service_confirmation_date;
    // Date fields on record.data are Luxon DateTime objects (or false).
    return value ? value.toFormat("yyyy-MM-dd") : false;
}

export function getReferencedPrbIds(personalRows, missionRows) {
    const ids = new Set();
    for (const row of personalRows) {
        const id = many2oneId(row.award_id);
        if (id) {
            ids.add(id);
        }
    }
    for (const row of missionRows) {
        const id = many2oneId(row.mission_id);
        if (id) {
            ids.add(id);
        }
    }
    return ids;
}
