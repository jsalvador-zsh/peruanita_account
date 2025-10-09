# Módulo Peruanita Account

## Descripción

Este módulo personaliza el comportamiento del campo `name` en las facturas de Odoo para permitir la edición manual del número de factura, manteniendo la funcionalidad de secuencia automática.

## Características Principales

### 1. Edición Manual del Campo Name
- Permite modificar manualmente el campo `name` de las facturas
- Mantiene la funcionalidad de secuencia automática por defecto
- Ideal para registrar facturas antiguas con números específicos

### 2. Control de Secuencia
- Campo `manual_name`: Indica si el nombre fue modificado manualmente
- Campo `original_sequence_name`: Almacena el nombre original de la secuencia
- Botones para alternar entre modo manual y secuencia automática

### 3. Validaciones
- Verificación de unicidad del nombre cuando es manual
- Validación por diario contable
- Prevención de duplicados

## Funcionalidades

### Modo Secuencia Automática (Por Defecto)
- El campo `name` se genera automáticamente usando la secuencia del diario
- Comportamiento estándar de Odoo
- No se puede editar manualmente

### Modo Manual
- Permite editar el campo `name` libremente
- Marca automáticamente como manual cuando se modifica
- Guarda el nombre original de la secuencia
- Valida que el nombre sea único en el diario

### Botones de Acción
- **Usar Secuencia**: Vuelve al modo automático usando el nombre original
- **Nombre Manual**: Marca explícitamente como manual

## Uso

### Para Facturas Nuevas
1. Crear una nueva factura normalmente
2. El sistema asignará automáticamente un número de secuencia
3. Si necesitas un número específico, edita el campo `name` directamente
4. El sistema marcará automáticamente como manual

### Para Facturas Antiguas
1. Crear una nueva factura
2. Editar el campo `name` con el número deseado (ej: "F F001-6231")
3. El sistema detectará la modificación y marcará como manual
4. Guardar la factura

### Cambiar entre Modos
- **A Manual**: Usar el botón "Nombre Manual" o editar el campo directamente
- **A Secuencia**: Usar el botón "Usar Secuencia" para volver al nombre original

## Campos Adicionales

- `manual_name`: Boolean que indica si el nombre es manual
- `original_sequence_name`: Char que almacena el nombre original de la secuencia

## Vistas Personalizadas

- **Formulario**: Incluye botones de acción y campos adicionales
- **Lista**: Muestra columna para identificar nombres manuales
- **Búsqueda**: Filtros para nombres manuales vs secuencia

## Instalación

1. Copiar el módulo a la carpeta de addons personalizados
2. Actualizar la lista de aplicaciones
3. Instalar el módulo "Peruanita Account"

## Dependencias

- `base`
- `account`
- `l10n_pe`

## Autor

Peruanita E.I.R.L.

## Licencia

LGPL-3
