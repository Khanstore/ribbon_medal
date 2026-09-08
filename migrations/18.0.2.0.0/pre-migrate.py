# -*- coding: utf-8 -*-
"""Pre-migrate for the res.person -> res.partner merge.

res.person used to be a SEPARATE table (delegation inheritance to
res.partner via partner_id) - every Many2one field that pointed at
'res.person' therefore stored res_person.id values, a different number
from the corresponding res_partner.id.

As of this version, every one of those fields' comodel is now
'res.partner' directly. Odoo's own _auto_init reconciles each field's
underlying foreign-key constraint against its (new) comodel as part of
loading this module's new code - which happens AFTER this script runs,
using whatever values are already in the column at that point. If those
values are still old res_person ids when that reconciliation happens, it
fails (they're not valid res_partner ids). So this MUST run first, on the
OLD schema (while res_person - and its partner_id mapping - still exists),
to fix the values in place before that happens.

This only touches the raw integer values in these columns; it does not
touch res_person's own field data (id_number, rank_id, etc.) or chatter -
see post-migrate.py for those, which need the NEW res.partner columns to
already exist first.
"""

# (table, column) pairs for every field that pointed at res.person before
# this version, across every model in this module.
_FK_COLUMNS = [
    ('sale_order', 'person_id'),
    ('sale_order_line', 'person_id'),
    ('rm_set_order', 'person_id'),
    ('rm_excluded_awards', 'person_id'),
    ('rm_acquisition_custom', 'person_id'),
    ('rm_personal_awards', 'person_id'),
    ('rm_mission_posting', 'person_id'),
    ('rm_rack_unit', 'reserved_person_id'),
    ('rm_rack_unit', 'delivered_to_person_id'),
    ('rm_medal_rack_unit', 'reserved_person_id'),
    ('rm_medal_rack_unit', 'delivered_to_person_id'),
]


def _table_exists(cr, table):
    cr.execute("SELECT 1 FROM information_schema.tables WHERE table_name = %s", (table,))
    return bool(cr.fetchone())


def _column_exists(cr, table, column):
    cr.execute(
        "SELECT 1 FROM information_schema.columns WHERE table_name = %s AND column_name = %s",
        (table, column))
    return bool(cr.fetchone())


def migrate(cr, version):
    if not _table_exists(cr, 'res_person'):
        # Fresh install, or already migrated - nothing to remap.
        return

    for table, column in _FK_COLUMNS:
        if not _table_exists(cr, table) or not _column_exists(cr, table, column):
            continue
        cr.execute(
            f"""
            UPDATE {table} t
            SET {column} = rp.partner_id
            FROM res_person rp
            WHERE t.{column} = rp.id
            """
        )
