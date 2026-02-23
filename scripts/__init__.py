"""
Scripts module - Adaptadores de scripts existentes.

Para añadir un nuevo script:
1. Crear un archivo .py en esta carpeta
2. Heredar de BaseScript
3. Usar el decorador @register_script
4. Implementar get_queries() y process()

Los scripts se registran automáticamente al importar este módulo.
"""

# Import all script modules to register them
# Original scripts
from . import contratos_activos_cortados
from . import contratos_inactivos_status
from . import contracts_without_asset

# Asset scripts
from . import assets_sin_contrato
from . import assets_hijos_sin_padre
from . import assets_desajuste_provisioning
from . import assets_fecha_incorrecta
from . import assets_without_directriz
from . import assets_presion_vacia
from . import assets_provisioning_status_mal
from . import asset_fixes_hijos_sin_parent_item

# Contract scripts
from . import contracts_multiple_asset_active
from . import contracts_asset_active_pending
from . import contracts_asset_active_general_en_curso
from . import contracts_asset_active_modificacion
from . import contracts_multiple_asset_baja
from . import contratos_sin_billing_account
from . import contratos_fechas_inconsistentes
from . import contratos_integracion_sap
from . import contratos_baja_assets_status_invalido
from . import contratos_ultimo_asset_modificado
from . import contrato_reenganche

# Account and billing scripts
from . import billing_accounts_without_payment
from . import billing_accounts_without_payment_completo
from . import service_account_multiples_contratos

# Data quality scripts
from . import desajuste_tarifa_service_point
from . import premises_multiple_sp_same_energy
from . import tarifa_incorrecta_contrato
from . import contact_mobile_number_bad
from . import usuarios_sin_licencia_vlocity

# Maintenance scripts
from . import error_log_checkout_renovacion
from . import fixes_generales

# Enhanced/Complete versions
from . import contratos_integracion_sap_completo
from . import contrato_reenganche_v3_completo

__all__ = [
    # Original
    'contratos_activos_cortados',
    'contratos_inactivos_status',
    'contracts_without_asset',
    # Assets
    'assets_sin_contrato',
    'assets_hijos_sin_padre',
    'assets_desajuste_provisioning',
    'assets_fecha_incorrecta',
    'assets_without_directriz',
    'assets_presion_vacia',
    'assets_provisioning_status_mal',
    'asset_fixes_hijos_sin_parent_item',
    # Contracts
    'contracts_multiple_asset_active',
    'contracts_asset_active_pending',
    'contracts_asset_active_general_en_curso',
    'contracts_asset_active_modificacion',
    'contracts_multiple_asset_baja',
    'contratos_sin_billing_account',
    'contratos_fechas_inconsistentes',
    'contratos_integracion_sap',
    'contratos_baja_assets_status_invalido',
    'contratos_ultimo_asset_modificado',
    'contrato_reenganche',
    # Account/Billing
    'billing_accounts_without_payment',
    'billing_accounts_without_payment_completo',
    'service_account_multiples_contratos',
    # Data Quality
    'desajuste_tarifa_service_point',
    'premises_multiple_sp_same_energy',
    'tarifa_incorrecta_contrato',
    'contact_mobile_number_bad',
    'usuarios_sin_licencia_vlocity',
    # Maintenance
    'error_log_checkout_renovacion',
    'fixes_generales',
    # Enhanced/Complete versions
    'contratos_integracion_sap_completo',
    'contrato_reenganche_v3_completo',
]
