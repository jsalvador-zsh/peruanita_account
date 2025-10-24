# -*- coding: utf-8 -*-

from odoo import models, fields, api, _
from odoo.exceptions import UserError


class AccountPaymentRegister(models.TransientModel):
    _inherit = 'account.payment.register'

    def _get_line_batch_key(self, line):
        """Override para agrupar líneas considerando retenciones"""
        res = super()._get_line_batch_key(line)
        
        # Verificar si res es un diccionario (algunas versiones de Odoo lo retornan así)
        if isinstance(res, dict):
            # Agregar has_retention al diccionario
            res['has_retention'] = line.move_id.has_retention
            return res
        else:
            # Si es tupla, agregar has_retention a la tupla
            return res + (line.move_id.has_retention,)

    def _create_payment_vals_from_wizard(self, batch_result):
        """Override para ajustar el monto del pago considerando retenciones"""
        payment_vals = super()._create_payment_vals_from_wizard(batch_result)
        
        # Obtener las facturas del batch
        lines = batch_result['lines']
        invoices = lines.mapped('move_id')
        
        # Verificar si alguna factura tiene retención
        invoices_with_retention = invoices.filtered('has_retention')
        
        if invoices_with_retention:
            # Calcular el monto total después de retenciones
            total_after_retention = sum(invoices.mapped('amount_after_retention'))
            
            # Ajustar el monto del pago
            if total_after_retention > 0:
                payment_vals['amount'] = total_after_retention
        
        return payment_vals

    def _create_payment_vals_from_batch(self, batch_result):
        """Override alternativo para versiones diferentes de Odoo"""
        payment_vals = super()._create_payment_vals_from_batch(batch_result)
        
        # Obtener las facturas del batch
        lines = batch_result['lines']
        invoices = lines.mapped('move_id')
        
        # Verificar si alguna factura tiene retención
        invoices_with_retention = invoices.filtered('has_retention')
        
        if invoices_with_retention:
            # Calcular el monto total después de retenciones
            total_after_retention = sum(invoices.mapped('amount_after_retention'))
            
            # Ajustar el monto del pago
            if total_after_retention > 0:
                payment_vals['amount'] = total_after_retention
        
        return payment_vals

    def action_create_payments(self):
        """Override para procesar retenciones después de crear pagos"""
        # Guardar las facturas con retención ANTES de crear los pagos
        invoices_with_retention = []
        if self.line_ids:
            invoices = self.line_ids.mapped('move_id')
            invoices_with_retention = invoices.filtered('has_retention')
        
        # Llamar al método original para crear los pagos
        result = super().action_create_payments()
        
        # Si hay facturas con retención, crear los asientos de retención
        if invoices_with_retention:
            for invoice in invoices_with_retention:
                self._create_retention_move_and_reconcile(invoice)
        
        return result

    def _create_retention_move_and_reconcile(self, invoice):
        """
        Crear asiento contable para registrar la retención y reconciliar la factura completamente.
        
        Lógica:
        - La factura tiene un total de 1000
        - Se paga 900 (ya reconciliado por el pago normal)
        - Quedan 100 pendientes
        - Creamos un asiento que:
          * DEBITA 100 en "Retenciones por Cobrar" (activo)
          * ACREDITA 100 en "Cuentas por Cobrar" (cancela el saldo pendiente)
        - Reconciliamos este asiento con la factura
        - La factura queda en estado "Pagado"
        """
        if not invoice.has_retention or invoice.retention_amount <= 0:
            return
        
        # Obtener la cuenta por cobrar de la factura
        receivable_lines = invoice.line_ids.filtered(
            lambda l: l.account_id.account_type == 'asset_receivable'
        )
        
        if not receivable_lines:
            return
        
        receivable_account = receivable_lines[0].account_id
        
        # Obtener o crear cuenta de retenciones
        retention_account = self._get_or_create_retention_account()
        
        if not retention_account:
            import logging
            _logger = logging.getLogger(__name__)
            _logger.error('No se pudo obtener cuenta de retenciones para factura %s', invoice.name)
            return
        
        # Obtener el journal (diario general o de banco)
        journal = self.env['account.journal'].search([
            ('type', '=', 'general')
        ], limit=1)
        
        if not journal:
            journal = self.env['account.journal'].search([
                ('type', 'in', ['bank', 'cash'])
            ], limit=1)
        
        if not journal:
            import logging
            _logger = logging.getLogger(__name__)
            _logger.error('No se encontró journal para crear asiento de retención')
            return
        
        # Crear el asiento de retención
        retention_move_vals = {
            'move_type': 'entry',
            'date': fields.Date.context_today(self),
            'journal_id': journal.id,
            'ref': _('Retención - %s') % invoice.name,
            'line_ids': [
                # DÉBITO: Aumenta el activo "Retenciones por Cobrar"
                (0, 0, {
                    'account_id': retention_account.id,
                    'partner_id': invoice.partner_id.id,
                    'debit': invoice.retention_amount,
                    'credit': 0.0,
                    'name': _('Retención aplicada - %s') % invoice.name,
                }),
                # CRÉDITO: Disminuye "Cuentas por Cobrar" (cancela el saldo pendiente)
                (0, 0, {
                    'account_id': receivable_account.id,
                    'partner_id': invoice.partner_id.id,
                    'debit': 0.0,
                    'credit': invoice.retention_amount,
                    'name': _('Aplicación de retención - %s') % invoice.name,
                }),
            ],
        }
        
        try:
            # Crear y publicar el asiento
            retention_move = self.env['account.move'].sudo().create(retention_move_vals)
            retention_move.action_post()
            
            # Reconciliar: Unir la línea de crédito del asiento de retención 
            # con la línea de débito pendiente de la factura
            self._reconcile_retention_with_invoice(invoice, retention_move)
            
            import logging
            _logger = logging.getLogger(__name__)
            _logger.info('Asiento de retención creado exitosamente para %s por %s', 
                        invoice.name, invoice.retention_amount)
            
        except Exception as e:
            import logging
            _logger = logging.getLogger(__name__)
            _logger.error('Error al crear asiento de retención para %s: %s', invoice.name, str(e))

    def _get_or_create_retention_account(self):
        """Obtener o crear cuenta para retenciones - sin filtro de company_id"""
        
        # 1. Buscar cuenta con código específico RETENTION
        retention_account = self.env['account.account'].search([
            ('code', '=', 'RETENTION')
        ], limit=1)
        
        if retention_account:
            return retention_account
        
        # 2. Buscar cuenta con código 1231 (código común para retenciones)
        retention_account = self.env['account.account'].search([
            ('code', '=', '1231')
        ], limit=1)
        
        if retention_account:
            return retention_account
        
        # 3. Buscar cuenta que contenga "retenc" en código o nombre
        retention_account = self.env['account.account'].search([
            ('account_type', '=', 'asset_current'),
            '|',
            ('code', 'ilike', 'retenc'),
            ('name', 'ilike', 'retenc')
        ], limit=1)
        
        if retention_account:
            return retention_account
        
        # 4. Intentar crear una cuenta específica para retenciones
        try:
            # Verificar si ya existe
            existing = self.env['account.account'].search([
                ('code', '=', '1231')
            ])
            
            if not existing:
                retention_account = self.env['account.account'].sudo().create({
                    'code': '1231',
                    'name': 'Retenciones por Cobrar',
                    'account_type': 'asset_current',
                    'reconcile': True,  # Permitir reconciliación
                })
                
                import logging
                _logger = logging.getLogger(__name__)
                _logger.info('Cuenta de retenciones creada: 1231 - Retenciones por Cobrar')
                
                return retention_account
            
        except Exception as e:
            import logging
            _logger = logging.getLogger(__name__)
            _logger.warning('No se pudo crear cuenta de retenciones: %s', str(e))
        
        # 5. Como último recurso, buscar cualquier cuenta de activo corriente reconciliable
        retention_account = self.env['account.account'].search([
            ('account_type', '=', 'asset_current'),
            ('reconcile', '=', True),
        ], limit=1)
        
        if retention_account:
            return retention_account
        
        # 6. Si todo falla, usar cuenta de activo corriente sin reconcile
        return self.env['account.account'].search([
            ('account_type', '=', 'asset_current'),
        ], limit=1)

    def _reconcile_retention_with_invoice(self, invoice, retention_move):
        """
        Reconciliar el asiento de retención con la factura para marcarla como pagada.
        
        Reconciliamos:
        - La línea de DÉBITO pendiente de la factura (Cuentas por Cobrar)
        - La línea de CRÉDITO del asiento de retención (Cuentas por Cobrar)
        """
        # Obtener líneas por cobrar de la factura que NO estén reconciliadas
        invoice_receivable_lines = invoice.line_ids.filtered(
            lambda l: l.account_id.account_type == 'asset_receivable' and not l.reconciled
        )
        
        # Obtener líneas de CRÉDITO del asiento de retención (Cuentas por Cobrar)
        retention_credit_lines = retention_move.line_ids.filtered(
            lambda l: l.account_id.account_type == 'asset_receivable' and l.credit > 0
        )
        
        if invoice_receivable_lines and retention_credit_lines:
            lines_to_reconcile = invoice_receivable_lines + retention_credit_lines
            
            try:
                # Intentar reconciliación completa
                lines_to_reconcile.reconcile()
                
                import logging
                _logger = logging.getLogger(__name__)
                _logger.info('Retención reconciliada exitosamente para factura %s', invoice.name)
                
            except Exception as e:
                import logging
                _logger = logging.getLogger(__name__)
                _logger.warning('No se pudo reconciliar retención para %s: %s', invoice.name, str(e))