"""
Connection Config Page - Configuración visual de credenciales Salesforce.
"""
import streamlit as st
import json
from pathlib import Path
from config import SF_CREDENTIALS_PATH


def render():
    """Render the connection configuration page."""
    st.markdown('<div class="hero-title" style="font-size:1.6rem;">⚙️ Configuración de Conexiones</div>', unsafe_allow_html=True)
    st.markdown("Gestiona las credenciales de Salesforce para diferentes entornos de forma visual.")
    
    st.divider()
    
    # Load existing credentials
    credentials = {}
    creds_file = Path(SF_CREDENTIALS_PATH)
    
    if creds_file.exists():
        try:
            with open(creds_file, 'r', encoding='utf-8') as f:
                credentials = json.load(f)
        except Exception as e:
            st.error(f"Error leyendo archivo de credenciales: {e}")
            credentials = {}
    else:
        st.warning(f"📁 Archivo de credenciales no encontrado en: `{creds_file}`")
        st.info("Se creará automáticamente al guardar la primera configuración.")
        credentials = {}
    
    # Environment tabs
    tab1, tab2, tab3, tab4 = st.tabs(["🔴 Producción (PRO)", "🟡 Preproducción (PRE)", "🔵 Desarrollo (DEV)", "📋 Vista JSON"])
    
    # Helper function to render environment config
    def render_env_config(env_key: str, env_name: str, description: str):
        """Render configuration form for a specific environment."""
        st.markdown(f"### {env_name}")
        st.markdown(f"<p style='color: var(--text-secondary); font-size: 0.9rem;'>{description}</p>", unsafe_allow_html=True)
        
        env_creds = credentials.get(env_key, {})
        
        col1, col2 = st.columns(2)
        
        with col1:
            username = st.text_input(
                "👤 Usuario",
                value=env_creds.get('USERNAME', ''),
                key=f"{env_key}_username",
                placeholder="usuario@dominio.com"
            )
            
            password = st.text_input(
                "🔒 Contraseña",
                value=env_creds.get('PASSWORD', ''),
                type="password",
                key=f"{env_key}_password",
                placeholder="Tu contraseña"
            )
        
        with col2:
            security_token = st.text_input(
                "🔑 Security Token",
                value=env_creds.get('SECURITY_TOKEN', ''),
                type="password",
                key=f"{env_key}_token",
                placeholder="Token de seguridad (opcional)"
            )
            
            domain = st.selectbox(
                "🌐 Dominio",
                options=["login", "test"],
                index=0 if env_creds.get('DOMAIN') == 'login' else 1,
                key=f"{env_key}_domain",
                help="'login' para producción, 'test' para sandbox"
            )
        
        # Test connection button
        col_test, col_clear = st.columns([2, 1])
        
        with col_test:
            if st.button(f"🔍 Probar Conexión", key=f"{env_key}_test", use_container_width=True):
                if not username or not password:
                    st.error("Usuario y contraseña son obligatorios")
                else:
                    try:
                        from data.salesforce_client import SalesforceClient
                        
                        # Save temporarily to test
                        temp_creds = {
                            env_key: {
                                'USERNAME': username,
                                'PASSWORD': password,
                                'SECURITY_TOKEN': security_token,
                                'DOMAIN': domain
                            }
                        }
                        
                        # Write temp file
                        temp_file = creds_file.parent / '.temp_creds_test.json'
                        with open(temp_file, 'w', encoding='utf-8') as f:
                            json.dump(temp_creds, f, indent=2)
                        
                        # Test connection
                        with st.spinner(f"Conectando a {env_name}..."):
                            client = SalesforceClient(env=env_key)
                            client.authenticate(credentials_path=str(temp_file))
                            st.success(f"✅ Conexión exitosa a {env_name}")
                            st.info(f"Instance: {client.instance_url}")
                            client.disconnect()
                        
                        # Clean up
                        temp_file.unlink()
                        
                    except Exception as e:
                        st.error(f"❌ Error de conexión: {str(e)}")
                        if temp_file.exists():
                            temp_file.unlink()
        
        with col_clear:
            if st.button(f"🗑️ Limpiar", key=f"{env_key}_clear", use_container_width=True):
                st.session_state[f"{env_key}_username"] = ""
                st.session_state[f"{env_key}_password"] = ""
                st.session_state[f"{env_key}_token"] = ""
                st.rerun()
        
        return {
            'USERNAME': username,
            'PASSWORD': password,
            'SECURITY_TOKEN': security_token,
            'DOMAIN': domain
        }
    
    # Production environment
    with tab1:
        pro_creds = render_env_config(
            "pro",
            "Entorno de Producción",
            "Credenciales para el entorno de producción de Salesforce (CUIDADO: datos reales)"
        )
    
    # Preproduction environment
    with tab2:
        pre_creds = render_env_config(
            "pre",
            "Entorno de Preproducción",
            "Credenciales para el entorno de preproducción/staging"
        )
    
    # Development environment
    with tab3:
        dev_creds = render_env_config(
            "dev",
            "Entorno de Desarrollo",
            "Credenciales para el entorno de desarrollo/sandbox"
        )
    
    # JSON view tab
    with tab4:
        st.markdown("### Vista JSON Actual")
        st.markdown("Visualización de todas las credenciales en formato JSON (contraseñas ofuscadas).")
        
        # Ofuscate sensitive data for display
        display_creds = {}
        for env_key, env_data in credentials.items():
            display_creds[env_key] = {
                'USERNAME': env_data.get('USERNAME', ''),
                'PASSWORD': '***' + env_data.get('PASSWORD', '')[-4:] if env_data.get('PASSWORD') else '',
                'SECURITY_TOKEN': '***' + env_data.get('SECURITY_TOKEN', '')[-4:] if env_data.get('SECURITY_TOKEN') else '',
                'DOMAIN': env_data.get('DOMAIN', '')
            }
        
        st.json(display_creds)
        
        st.markdown("**Ruta del archivo:**")
        st.code(str(creds_file), language="text")
    
    # Save button
    st.divider()
    
    col1, col2, col3 = st.columns([1, 1, 1])
    
    with col2:
        if st.button("💾 Guardar Configuración", type="primary", use_container_width=True):
            # Validate at least one environment has credentials
            new_creds = {
                'pro': pro_creds,
                'pre': pre_creds,
                'dev': dev_creds
            }
            
            # Check if at least one environment has username and password
            has_valid_env = any(
                env['USERNAME'] and env['PASSWORD'] 
                for env in new_creds.values()
            )
            
            if not has_valid_env:
                st.error("⚠️ Debes configurar al menos un entorno con usuario y contraseña")
            else:
                try:
                    # Create parent directory if needed
                    creds_file.parent.mkdir(parents=True, exist_ok=True)
                    
                    # Write credentials file
                    with open(creds_file, 'w', encoding='utf-8') as f:
                        json.dump(new_creds, f, indent=2, ensure_ascii=False)
                    
                    st.success(f"✅ Configuración guardada exitosamente en: `{creds_file}`")
                    st.info("Las credenciales estarán disponibles inmediatamente en la página de inicio.")
                    
                    # Reload credentials
                    st.rerun()
                    
                except Exception as e:
                    st.error(f"❌ Error guardando configuración: {e}")
