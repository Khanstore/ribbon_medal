# -*- coding: utf-8 -*-
"""Post-migrate for the res.person -> res.partner merge.

Runs after this module's new res.partner columns (is_person, id_number,
rank_id, current_workplace, bcs_batch, service_confirmation_date,
force_id, name_eng, name_bng, birth_date, retirement_date) already exist
- see pre-migrate.py in this same folder for why the FK *value*
remapping had to happen earlier, before this point, instead.

This does the rest of the merge:
1. Copies res_person's own field data onto the matching res.partner row
   (via the old partner_id link) and sets is_person=True there.
2. Re-points chatter (mail.message/mail.followers/mail.activity) that
   used to belong to a res.person record onto that same res.partner row.
3. Drops the now fully-migrated, unused res_person table.
"""

# Every column res_person had of its own (i.e. not delegated from
# res.partner) that has a same-named, same-type counterpart on
# res.partner as of this version - a straight column-to-column copy.
_OWN_COLUMNS = [
    'id_number', 'rank_id', 'current_workplace', 'bcs_batch',
    'service_confirmation_date', 'force_id', 'name_eng', 'name_bng',
    'birth_date', 'retirement_date',
]


def _table_exists(cr, table):
    cr.execute("SELECT 1 FROM information_schema.tables WHERE table_name = %s", (table,))
    return bool(cr.fetchone())


def migrate(cr, version):
    if not _table_exists(cr, 'res_person'):
        # Fresh install, or already migrated - nothing to do.
        return

    # 1. Copy res_person's own data onto its partner, and flag it Personnel.
    assignments = ', '.join(f'{col} = rp.{col}' for col in _OWN_COLUMNS)
    cr.execute(f"""
        UPDATE res_partner
        SET is_person = TRUE, {assignments}
        FROM res_person rp
        WHERE res_partner.id = rp.partner_id
    """)

    # 2. Re-point chatter that belonged to a res.person record onto the
    # same underlying res.partner row. res_id here is a plain integer,
    # not a real foreign key, so this is safe regardless of the FK
    # reconciliation timing that pre-migrate.py exists for.
    for table in ('mail_message', 'mail_followers', 'mail_activity'):
        if not _table_exists(cr, table):
            continue
        cr.execute(f"""
            UPDATE {table} t
            SET res_model = 'res.partner', res_id = rp.partner_id
            FROM res_person rp
            WHERE t.res_model = 'res.person' AND t.res_id = rp.id
        """)

    # 3. Every value and chatter record has now been moved off res_person
    # - safe to drop. CASCADE only removes constraints/views that still
    # reference it (there shouldn't be any real ones left at this point,
    # since every FK column was already repointed at res.partner).
    cr.execute("DROP TABLE IF EXISTS res_person CASCADE")
