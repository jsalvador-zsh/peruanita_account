# -*- coding: utf-8 -*-

from odoo import models, fields, api, _
from odoo.exceptions import ValidationError


class AccountMove(models.Model):
    _inherit = 'account.move'

    # Campo para controlar si el nombre fue modificado manualmente
    manual_name = fields.Boolean(
        string='Nombre Manual',
        default=False,
        help='Indica si el nombre de la factura fue modificado manualmente'
    )
    month_out = fields.Char(string='Mes de entrega', tracking=True, help='Mes de entrega del pedido')
    
    # Campo para almacenar el nombre original de la secuencia
    original_sequence_name = fields.Char(
        string='Nombre Original de Secuencia',
        help='Almacena el nombre generado por la secuencia antes de la modificación manual'
    )
    
    # Nuevos campos para retención
    has_retention = fields.Boolean(
        string='Tiene Retención',
        default=False,
        tracking=True,
        help='Marcar si esta factura tiene retención'
    )
    
    retention_amount = fields.Monetary(
        string='Monto de Retención',
        currency_field='currency_id',
        default=0.0,
        tracking=True,
        help='Monto que será retenido y no se cobrará directamente'
    )
    
    amount_after_retention = fields.Monetary(
        string='Monto a Cobrar',
        currency_field='currency_id',
        compute='_compute_amount_after_retention',
        store=True,
        help='Monto total menos la retención'
    )

    @api.depends('amount_total', 'retention_amount', 'has_retention')
    def _compute_amount_after_retention(self):
        """Calcular el monto a cobrar después de la retención"""
        for record in self:
            if record.has_retention:
                record.amount_after_retention = record.amount_total - record.retention_amount
            else:
                record.amount_after_retention = record.amount_total

    @api.onchange('has_retention')
    def _onchange_has_retention(self):
        """Limpiar retención si se desmarca el checkbox"""
        if not self.has_retention:
            self.retention_amount = 0.0

    @api.constrains('retention_amount', 'amount_total', 'has_retention')
    def _check_retention_amount(self):
        """Validar que la retención no sea mayor al total"""
        for record in self:
            if record.has_retention:
                if record.retention_amount < 0:
                    raise ValidationError(_('El monto de retención no puede ser negativo.'))
                if record.retention_amount > record.amount_total:
                    raise ValidationError(
                        _('El monto de retención (%.2f) no puede ser mayor al monto total (%.2f).') % 
                        (record.retention_amount, record.amount_total)
                    )

    @api.model
    def create(self, vals):
        """Override create para manejar la secuencia y el nombre manual"""
        # Si no se especifica manual_name, usar secuencia normal
        if 'manual_name' not in vals or not vals.get('manual_name'):
            # Generar nombre usando secuencia normal
            if not vals.get('name') or vals['name'] == '/':
                vals['name'] = self._get_next_sequence_number()
                vals['original_sequence_name'] = vals['name']
        else:
            # Si es manual, guardar el nombre original si existe
            if vals.get('name') and vals['name'] != '/':
                vals['original_sequence_name'] = vals['name']
        
        return super(AccountMove, self).create(vals)

    def write(self, vals):
        """Override write para manejar cambios en el nombre"""
        for record in self:
            # Si se está modificando el nombre y no es manual, marcarlo como manual
            if 'name' in vals and not record.manual_name:
                if vals['name'] != record.name and vals['name'] != '/':
                    vals['manual_name'] = True
                    # Guardar el nombre original si no existe
                    if not record.original_sequence_name:
                        vals['original_sequence_name'] = record.name
            
            # Si se está desmarcando manual_name, restaurar secuencia
            if 'manual_name' in vals and not vals['manual_name'] and record.original_sequence_name:
                vals['name'] = record.original_sequence_name
        
        return super(AccountMove, self).write(vals)

    def _get_next_sequence_number(self):
        """Obtener el siguiente número de secuencia"""
        if self.journal_id and self.journal_id.sequence_id:
            return self.journal_id.sequence_id.next_by_id()
        return '/'

    def action_use_sequence(self):
        """Acción para volver a usar la secuencia automática"""
        for record in self:
            if record.manual_name and record.original_sequence_name:
                record.write({
                    'name': record.original_sequence_name,
                    'manual_name': False
                })
            elif record.manual_name and not record.original_sequence_name:
                # Si no hay nombre original, generar uno nuevo
                new_name = record._get_next_sequence_number()
                record.write({
                    'name': new_name,
                    'original_sequence_name': new_name,
                    'manual_name': False
                })

    def action_use_manual_name(self):
        """Acción para marcar como nombre manual"""
        for record in self:
            if not record.manual_name:
                record.write({
                    'manual_name': True,
                    'original_sequence_name': record.name
                })

    @api.constrains('name', 'manual_name')
    def _check_name_uniqueness(self):
        """Verificar que el nombre sea único cuando es manual"""
        for record in self:
            if record.manual_name and record.name and record.name != '/':
                # Buscar otros registros con el mismo nombre en el mismo diario
                domain = [
                    ('id', '!=', record.id),
                    ('name', '=', record.name),
                    ('journal_id', '=', record.journal_id.id),
                    ('state', '!=', 'cancel')
                ]
                if self.search(domain):
                    raise ValidationError(
                        _('El nombre "%s" ya existe en el diario "%s". '
                          'Por favor, use un nombre único.') % 
                        (record.name, record.journal_id.name)
                    )

    def _get_sequence_prefix(self):
        """Obtener el prefijo de la secuencia para mostrar en la interfaz"""
        if self.journal_id and self.journal_id.sequence_id:
            return self.journal_id.sequence_id.prefix or ''
        return ''

    def _get_sequence_suffix(self):
        """Obtener el sufijo de la secuencia para mostrar en la interfaz"""
        if self.journal_id and self.journal_id.sequence_id:
            return self.journal_id.sequence_id.suffix or ''
        return ''