# -*- coding: utf-8 -*-
{
    'name': 'Peruanita Account',
    'version': '1.0.0',
    'category': 'Accounting',
    'summary': 'Personalización del módulo de contabilidad para Peruanita',
    'description': """
        Módulo de personalización para contabilidad de Peruanita:
        - Permite modificar manualmente el campo name de las facturas
        - Mantiene la funcionalidad de secuencia pero con posibilidad de edición
        - Facilita el registro de facturas antiguas
    """,
    'author': 'Juan Salvador',
    'website': 'https://jsalvador.dev',
    'depends': [
        'base',
        'account',
        'l10n_pe',
    ],
    'data': [
        'security/ir.model.access.csv',
        'views/account_move_views.xml',
    ],
    'installable': True,
    'auto_install': False,
    'application': False,
    'license': 'LGPL-3',
}
