{
    'name': 'Ribbon Medal - Personnel Decorations',
<<<<<<< Updated upstream
    'version': '18.0.1.0.65',
=======
<<<<<<< HEAD
    'version': '18.0.1.0.87',
=======
    'version': '18.0.1.0.79',
>>>>>>> bb3a35d8c0f0303a5d80a0b497603fa7185d7356
>>>>>>> Stashed changes
    'category': 'Human Resources',
    'summary': 'Manage personnel records and their decorations (ribbons/medals) for military/police organizations',
    'description': """
Ribbon Medal
============
Manage personnel (res.person, extending res.partner), organizational forces,
ranks, decoration acquisition rules, and decorations (ribbons/medals).

Features
--------
* Personnel records independent of the hr module.
* Forces / branches of service and rank hierarchy.
* Decoration (Ribbon/Medal) catalogue with seniority-based precedence.
* Automatic seniority-based sorting of obtained awards.
* Interactive "Ribbon Rack" OWL widget: displays obtained decorations in a
  4-column grid, filled starting bottom-right toward top-left in order of
  seniority precedence.
""",
    'author': 'Khan Store',
    'license': 'LGPL-3',
    'depends': ['base', 'sale', 'stock', 'mail','website_sale','purchase' ,'product', 'mrp'],
    'data': [
        'security/ribbon_medal_security.xml',
        'security/ir.model.access.csv',
        'data/ribbon_medal_data.xml',
        'data/product_attribute_data.xml',
        'data/rm_attachment_data.xml',
        'data/rm.decoration.csv',
        'data/rm.rules.category.csv',
        'data/rm.forces.csv',
        'data/rm.prb.csv',
        # 'data/rm.ranks.csv',
        'data/ribbon_medal_ranks.xml',
        'data/force_unit_data.xml',
        'data/rm_manufacturing_data.xml',
        'data/rm_set_template_data.xml',
        'data/rm_medal_set_data.xml',

        'views/res_person_views.xml',
        'views/rm_ranks_views.xml',
        'views/rm_bcs_batch.xml',
        'views/rm_attachment_views.xml',
        'views/rm_decoration_views.xml',
        'views/personal_award.xml',
        'views/mission_posting.xml',
        'views/excluded_award.xml',
        'views/prb.xml',
        'views/rm_rules_category_views.xml',
        'views/rm_acquisition_views.xml',
        'views/rm_acquisition_custom_views.xml',
        'views/rm_unit_views.xml',
        'views/rm_unit_category_views.xml',
        'views/rm_forces_views.xml',
        'views/rm_set_template_views.xml',
        'views/rm_person_search_wizard_views.xml',
<<<<<<< Updated upstream
=======
        'views/rm_sale_line_person_wizard_views.xml',
        'views/rm_partner_to_person_wizard_views.xml',
>>>>>>> Stashed changes
        'views/rm_set_order_views.xml',
        'views/rm_rack_line_views.xml',
        'views/rm_rack_product_views.xml',
        'views/rm_medal_part_views.xml',
        'views/rm_medal_rack_views.xml',
        'views/sale_order_views.xml',
        'views/ribbon_medal_menus.xml',
    ],
    'assets': {
        'web.assets_backend': [
            'ribbon_medal/static/src/js/rack_ledger.js',
            'ribbon_medal/static/src/scss/ribbon_rack.scss',
            'ribbon_medal/static/src/js/ribbon_rack.js',
            'ribbon_medal/static/src/xml/ribbon_rack.xml',
            'ribbon_medal/static/src/scss/medal_rack.scss',
            'ribbon_medal/static/src/js/medal_rack.js',
            'ribbon_medal/static/src/xml/medal_rack.xml',
        ],
    },
    'installable': True,
    'application': True,
    'auto_install': False,
}
