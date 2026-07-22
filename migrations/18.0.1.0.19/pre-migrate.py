# -*- coding: utf-8 -*-
"""
Two things changed together this round, and they interact:

1. rm.decorator was renamed to rm.decoration, and trimmed down to a pure
   catalog entry (award_name -> decoration_name; starting_date, force_id,
   rule_id, seniority_sequence, person_ids/person_count all REMOVED).

2. A brand new, separate model rm.prb was introduced (models/prb.py) -
   the per-force acquisition variant of a decoration. It reuses the table
   name `rm_prb` and the relation table name `rm_prb_res_person_rel`,
   which is safe now, since the *original* rm.prb (the one this module
   started with) was already renamed away to `rm_decorator` by the
   18.0.1.0.18 migration, freeing that name up.

   res.person.obtained_awards_ids now points at rm.prb (the force-specific
   variant), not rm.decoration directly - i.e. the relationship itself
   changed shape, not just its name. Any existing person<->decoration
   links can't be automatically re-pointed at a specific rm.prb variant
   (there could be zero or several PRB variants of a given decoration for
   a given force, and picking one would be guessing at business data), so
   this migration does NOT try to invent that mapping. It preserves the
   old link table under an "_archived" name instead of dropping it, in
   case you want to manually recover/re-apply any assignments, but the
   new obtained_awards_ids will start empty.

This migration is defensive about which of `rm_decorator` / `rm_prb`
(original) is actually present, since it depends on whether
18.0.1.0.18 previously completed successfully on this database.
"""


def _table_exists(cr, table_name):
    cr.execute("""
        SELECT 1 FROM information_schema.tables WHERE table_name = %s
    """, (table_name,))
    return bool(cr.fetchone())


def migrate(cr, version):
    # --- Catalog table: rename whichever of rm_decorator / rm_prb (the
    # ORIGINAL, pre-18.0.1.0.18 one) is present to rm_decoration. ---
    source_table = None
    if _table_exists(cr, 'rm_decorator'):
        source_table = 'rm_decorator'
    elif _table_exists(cr, 'rm_prb') and not _table_exists(cr, 'rm_decorator'):
        # 18.0.1.0.18 never ran on this database - the table is still
        # under its very first name.
        source_table = 'rm_prb'

    if source_table and not _table_exists(cr, 'rm_decoration'):
        cr.execute('ALTER TABLE %s RENAME TO rm_decoration' % source_table)

    # Columns that no longer exist on rm.decoration are simply left as
    # harmless orphaned columns (starting_date, force_id, rule_id,
    # seniority_sequence, person_count) - Odoo's normal schema sync only
    # adds/renames what the model declares, it never drops columns, so
    # nothing to do here explicitly; the ORM will just ignore them.

    # --- Old person<->decoration relation link: archive it rather than
    # reuse or drop it, since the relationship shape genuinely changed. ---
    for old_rel in ('rm_decorator_res_person_rel', 'rm_prb_res_person_rel'):
        if _table_exists(cr, old_rel) and not _table_exists(cr, old_rel + '_archived'):
            # Only archive rm_prb_res_person_rel if it's still in its
            # ORIGINAL shape (person_id/prb_id pointing at the catalog
            # table we just renamed above) - i.e. only when source_table
            # was 'rm_prb' (18.0.1.0.18 never ran, so this table has
            # never been touched and is still the old relation).
            if old_rel == 'rm_prb_res_person_rel' and source_table != 'rm_prb':
                continue
            cr.execute('ALTER TABLE %s RENAME TO %s_archived' % (old_rel, old_rel))

    # --- ir.model bookkeeping: reuse the existing row instead of leaving
    # it orphaned while Odoo creates a brand new one for 'rm.decoration'. ---
    cr.execute("""
        UPDATE ir_model SET model = 'rm.decoration'
        WHERE model IN ('rm.decorator', 'rm.prb')
          AND NOT EXISTS (SELECT 1 FROM ir_model WHERE model = 'rm.decoration')
    """)

    # Same idea for rm.acquisition.rules -> rm.rules.category.
    cr.execute("""
        UPDATE ir_model SET model = 'rm.rules.category'
        WHERE model = 'rm.acquisition.rules'
          AND NOT EXISTS (SELECT 1 FROM ir_model WHERE model = 'rm.rules.category')
    """)
    if _table_exists(cr, 'rm_acquisition_rules') and not _table_exists(cr, 'rm_rules_category'):
        cr.execute('ALTER TABLE rm_acquisition_rules RENAME TO rm_rules_category')
