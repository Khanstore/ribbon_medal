# -*- coding: utf-8 -*-
"""
The 18.0.1.0.12 migration tried to adopt a pre-existing 'Police' rm.forces
record under the 'ribbon_medal.force_police' external id, on the theory
that data/ribbon_medal_data.xml was failing to create it due to a
unique(name) collision. That migration ran but the problem persisted,
which means data/ribbon_medal_data.xml is failing (or being skipped) for
some other, not-fully-diagnosable-remotely reason.

Rather than depend on that XML file's behaviour at all, this migration
guarantees the 'ribbon_medal.force_police' external id resolves to a real
rm_forces row by the time data/rm.ranks.csv loads, using raw SQL only:

  * If the external id already exists - nothing to do.
  * Else if an rm_forces row named 'Police' already exists (trimmed,
    case-insensitive) - adopt it (register the external id against it).
  * Else - create the row directly and register the external id.

When data/ribbon_medal_data.xml runs afterwards, it will see the external
id already exists and (being noupdate=1) leave that record's fields
alone, so this doesn't fight with or duplicate anything.
"""


def migrate(cr, version):
    cr.execute("""
        SELECT 1 FROM ir_model_data
        WHERE module = 'ribbon_medal' AND name = 'force_police'
    """)
    if cr.fetchone():
        return

    cr.execute("""
        SELECT id FROM rm_forces
        WHERE trim(lower(name)) = 'police'
        ORDER BY id
        LIMIT 1
    """)
    row = cr.fetchone()
    if row:
        force_id = row[0]
    else:
        cr.execute("""
            INSERT INTO rm_forces (name, description, active, create_date, write_date, create_uid, write_uid)
            VALUES ('Police', 'Bangladesh Police', TRUE, NOW(), NOW(), 1, 1)
            RETURNING id
        """)
        force_id = cr.fetchone()[0]

    cr.execute("""
        INSERT INTO ir_model_data
            (name, module, model, res_id, noupdate, create_date, write_date, create_uid, write_uid)
        VALUES
            ('force_police', 'ribbon_medal', 'rm.forces', %s, TRUE, NOW(), NOW(), 1, 1)
    """, (force_id,))
