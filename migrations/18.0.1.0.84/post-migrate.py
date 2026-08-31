# -*- coding: utf-8 -*-
"""purchase_ok now defaults to True for every product this app
auto-manages (previously False). The three generic rack products and
the mixin's own default are declared with purchase_ok=True as of this
version, but their XML data records use noupdate="1", so an upgrade
alone won't retroactively flip already-existing rows - fix those here.

Only product.template rows currently purchase_ok=False AND actually
linked from one of this app's own tables are touched; nothing else in
the database is affected. Safe to run on any upgrade path, including
one that jumps across several versions at once, since by the post-migrate
stage the ORM has already synced this version's tables (including the
newer rm_medal_part/rm_medal_rack ones, even for installs that never
had them before)."""


def migrate(cr, version):
    cr.execute("""
        UPDATE product_template pt
        SET purchase_ok = TRUE
        WHERE pt.purchase_ok = FALSE
          AND pt.id IN (
              SELECT imd.res_id FROM ir_model_data imd
              WHERE imd.model = 'product.template'
                AND imd.module = 'ribbon_medal'
                AND imd.name IN (
                    'product_ribbon_rack',
                    'product_tunic_medal_rack',
                    'product_meskit_medal_rack'
                )
              UNION
              SELECT product_tmpl_id FROM rm_rack_line WHERE product_tmpl_id IS NOT NULL
              UNION
              SELECT product_tmpl_id FROM rm_rack_product WHERE product_tmpl_id IS NOT NULL
              UNION
              SELECT product_tmpl_id FROM rm_medal_part WHERE product_tmpl_id IS NOT NULL
              UNION
              SELECT product_tmpl_id FROM rm_medal_rack WHERE product_tmpl_id IS NOT NULL
              UNION
              SELECT ribbon_product_tmpl_id FROM rm_decoration WHERE ribbon_product_tmpl_id IS NOT NULL
              UNION
              SELECT medal_product_tmpl_id FROM rm_decoration WHERE medal_product_tmpl_id IS NOT NULL
              UNION
              SELECT device_product_tmpl_id FROM rm_attachment WHERE device_product_tmpl_id IS NOT NULL
          )
    """)
