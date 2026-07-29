{
    'name': 'Ribbon Medal - Personnel Decorations',
    'version': '18.0.1.0.39',
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
    'depends': ['base', 'mail', 'product'],
    'data': [
        'security/ribbon_medal_security.xml',
        'security/ir.model.access.csv',
        'data/ribbon_medal_data.xml',
        'data/rm_attachment_data.xml',
        'data/product_attribute_data.xml',
        'data/rm.decoration.csv',
        # 'data/rm.ranks.csv',
        'data/ribbon_medal_ranks.xml',
        'data/force_unit_data.xml',

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
        'views/ribbon_medal_menus.xml',
    ],
    'assets': {
        'web.assets_backend': [
            'ribbon_medal/static/src/scss/ribbon_rack.scss',
            'ribbon_medal/static/src/js/ribbon_rack.js',
            'ribbon_medal/static/src/xml/ribbon_rack.xml',
        ],
    },
    'installable': True,
    'application': True,
    'auto_install': False,
}
