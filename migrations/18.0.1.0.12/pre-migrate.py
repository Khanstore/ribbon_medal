# -*- coding: utf-8 -*-
"""
Fixes an upgrade failure caused by a 'Police' rm.forces record that was
created manually via the UI before data/ribbon_medal_data.xml existed.

data/ribbon_medal_data.xml tries to create its own rm.forces record named
'Police' tagged with the external id 'ribbon_medal.force_police'. Since
rm.forces.name has a unique() constraint, that insert silently collides
with the pre-existing manually-created record, so the external id never
gets registered - which then makes data/rm.ranks.csv fail too, since every
row references 'ribbon_medal.force_police' for its Force.

This script runs BEFORE any data file loads for this version. It looks
for an existing rm.forces row named 'Police' that isn't already tied to
an external id, and "adopts" it by registering the external id against
it directly in ir_model_data. When data/ribbon_medal_data.xml then runs,
it will see the external id already exists (noupdate=1 on that record
means its fields are left alone) instead of trying - and failing - to
insert a duplicate. No existing data (ranks, personnel, units already
linked to that Police force) is touched or lost.

If the external id already exists, or there's no pre-existing 'Police'
force at all (clean install), this is a no-op.
"""


def migrate(cr, version):
    cr.execute("""
        SELECT 1 FROM ir_model_data
        WHERE module = 'ribbon_medal' AND name = 'force_police'
    """)
    if cr.fetchone():
        # Already registered - nothing to do.
        return

    cr.execute("""
        SELECT id FROM rm_forces
        WHERE lower(name) = 'police'
        ORDER BY id
        LIMIT 1
    """)
    row = cr.fetchone()
    if not row:
        # No pre-existing 'Police' force - clean install, let the normal
        # seed data create it.
        return

    force_id = row[0]
    cr.execute("""
        INSERT INTO ir_model_data
            (name, module, model, res_id, noupdate, create_date, write_date, create_uid, write_uid)
        VALUES
            ('force_police', 'ribbon_medal', 'rm.forces', %s, TRUE, NOW(), NOW(), 1, 1)
    """, (force_id,))
