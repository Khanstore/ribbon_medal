# -*- coding: utf-8 -*-
"""rm_is_finished_rack (product.template) is new as of this version and
is only ever set going forward, at the moment rm.rack.product /
rm.medal.rack first create their product (see _ensure_product on each).
Existing installs already have Rack/Medal Rack products created by
earlier versions that predate the flag, so those must be backfilled
here for the new "Racks Only" Manufacturing Orders filter to include
them.

Only product_template rows already linked from rm_rack_product or
rm_medal_rack are touched; nothing else in the database is affected.
Safe to run on any upgrade path, including one that jumps across
several versions at once.
"""


def migrate(cr, version):
    cr.execute("""
        UPDATE product_template pt
        SET rm_is_finished_rack = TRUE
        WHERE pt.rm_is_finished_rack IS NOT TRUE
          AND pt.id IN (
              SELECT product_tmpl_id FROM rm_rack_product WHERE product_tmpl_id IS NOT NULL
              UNION
              SELECT product_tmpl_id FROM rm_medal_rack WHERE product_tmpl_id IS NOT NULL
          )
    """)
