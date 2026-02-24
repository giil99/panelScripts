"""
Home Page - Dashboard principal con resumen y conexión.
"""
import streamlit as st
from datetime import datetime
from data.salesforce_client import SalesforceClient
from core.script_registry import get_registry
from core.history_manager import get_history_manager
from config import SF_CREDENTIALS_PATH


def render():
    """Render the home page."""

    # ── Hero Section ────────────────────────────────────────────────────
    st.markdown("""
    <div class="hero-title">Dashboard de Scripts de Datos</div>
    <div class="hero-subtitle">
        Ejecuta, visualiza y analiza scripts de procesamiento de datos Salesforce
    </div>
    """, unsafe_allow_html=True)

    # ── Connection Section ──────────────────────────────────────────────
    st.markdown('<div class="section-header">🔐 Conexión a Salesforce</div>', unsafe_allow_html=True)

    col1, col2 = st.columns([1, 2])

    with col1:
        st.markdown("**Selecciona Entorno:**")
        
        # Visual environment selector using columns for buttons
        env_col1, env_col2, env_col3 = st.columns(3)
        
        # Initialize selected environment
        if 'selected_env' not in st.session_state:
            st.session_state.selected_env = 'pre'
        
        with env_col1:
            if st.button("🟡 PRE", use_container_width=True, 
                        type="primary" if st.session_state.selected_env == 'pre' else "secondary"):
                st.session_state.selected_env = 'pre'
                st.rerun()
        
        with env_col2:
            if st.button("🔴 PRO", use_container_width=True,
                        type="primary" if st.session_state.selected_env == 'pro' else "secondary"):
                st.session_state.selected_env = 'pro'
                st.rerun()
        
        with env_col3:
            if st.button("🔵 DEV", use_container_width=True,
                        type="primary" if st.session_state.selected_env == 'dev' else "secondary"):
                st.session_state.selected_env = 'dev'
                st.rerun()
        
        env = st.session_state.selected_env
        
        # Connection buttons
        st.markdown("")
        col_connect, col_config = st.columns([2, 1])
        
        with col_connect:
            if st.button("🔗 Conectar", type="primary", use_container_width=True):
                try:
                    with st.spinner(f"Conectando a {env.upper()}..."):
                        client = SalesforceClient(env=env)
                        # Use credentials from app root automatically
                        client.authenticate(credentials_path=str(SF_CREDENTIALS_PATH))
                        st.session_state.sf_client = client
                        st.success(f"✅ Conectado a {env.upper()}")
                        st.rerun()
                except FileNotFoundError as e:
                    st.error(f"📁 Archivo de credenciales no encontrado.")
                    st.info("💡 Ve a **⚙️ Configuración de Conexiones** para crear las credenciales.")
                except ConnectionError as e:
                    st.error(f"❌ Error de conexión: {e}")
                except Exception as e:
                    st.error(f"⚠️ Error: {e}")
        
        with col_config:
            if st.button("⚙️", use_container_width=True, help="Configurar credenciales"):
                st.session_state.current_page = 'connection_config'
                st.rerun()

    with col2:
        if st.session_state.sf_client and st.session_state.sf_client.is_authenticated:
            st.markdown(f"""
            <div class="info-card">
                <div class="status-badge status-connected" style="margin-bottom: 0.8rem;">🟢 Conectado</div>
                <p style="margin: 0.3rem 0; color: var(--text-secondary); font-size: 0.85rem;">
                    <strong>Entorno:</strong> {st.session_state.sf_client.env.upper()}
                </p>
                <p style="margin: 0.3rem 0; color: var(--text-secondary); font-size: 0.85rem;">
                    <strong>Instance:</strong> {st.session_state.sf_client.instance_url}
                </p>
            </div>
            """, unsafe_allow_html=True)
        else:
            st.markdown("""
            <div class="info-card">
                <div class="status-badge status-disconnected" style="margin-bottom: 0.8rem;">DESCONECTADO</div>
                <p style="margin: 0.3rem 0; color: var(--text-muted); font-size: 0.85rem;">
                    Conecta a Salesforce para ejecutar scripts.
                </p>
            </div>
            """, unsafe_allow_html=True)

    st.divider()

    # ── Quick Stats ─────────────────────────────────────────────────────
    registry = get_registry()
    scripts = registry.list_scripts()
    
    st.markdown('<div class="section-header">Estadísticas</div>', unsafe_allow_html=True)

    col1, col2, col3 = st.columns(3)

    with col1:
        st.metric(label="Scripts Disponibles", value=len(scripts))

    with col2:
        st.metric(
            label="Categorías",
            value=len(set(s['category'] for s in scripts)) if scripts else 0
        )

    with col3:
        status = "Conectado" if (st.session_state.sf_client and st.session_state.sf_client.is_authenticated) else "Desconectado"
        st.metric(label="Estado Conexión", value=status)

    st.divider()

    # ── Available Scripts ───────────────────────────────────────────────
    st.markdown('<div class="section-header">Scripts Disponibles</div>', unsafe_allow_html=True)

    # Check if a script is currently executing
    script_executing = st.session_state.get('script_executing', False)
    if script_executing:
        executing_script_name = st.session_state.get('executing_script_name', 'Desconocido')
        st.warning(f"**Script en ejecución:** {executing_script_name}. No se pueden ejecutar otros scripts hasta que finalice.")

    if not scripts:
        st.info("No hay scripts registrados. Añade scripts en la carpeta `scripts/`.")
        with st.expander("Cómo añadir scripts"):
            st.code("""
from core.base_script import BaseScript, ScriptResult
from core.script_registry import register_script

@register_script
class MiScript(BaseScript):
    name = "Mi Script"
    description = "Descripción del script"
    category = "Regularización"

    def get_queries(self, preview=False):
        return ["SELECT Id FROM Account LIMIT 10"]

    def process(self, query_results):
        df = query_results['query_0']
        return ScriptResult(data=df)
            """, language="python")
    else:
        # Get execution history for last execution times
        history_manager = get_history_manager()
        all_history = history_manager.get_all()
        
        # Create mapping of script name -> last execution time
        last_execution = {}
        for record in all_history:
            script_name = record['script_name']
            executed_at = record['executed_at']
            if script_name not in last_execution:
                last_execution[script_name] = executed_at
        
        # Group by category
        categories = {}
        for script in scripts:
            cat = script['category']
            categories.setdefault(cat, []).append(script)

        for category, cat_scripts in sorted(categories.items()):
            # Sort scripts by name within each category
            cat_scripts_sorted = sorted(cat_scripts, key=lambda x: x['name'])

            # Use expander for each category (collapsible)
            with st.expander(
                f"**{category}** · {len(cat_scripts_sorted)} script{'s' if len(cat_scripts_sorted) > 1 else ''}",
                expanded=True
            ):
                for script in cat_scripts_sorted:
                    # Get last execution time
                    last_exec_str = ""
                    if script['name'] in last_execution:
                        try:
                            last_exec_dt = datetime.fromisoformat(last_execution[script['name']])
                            last_exec_str = f"<div style='color: #999; font-size: 0.8rem; margin-top: 0.3rem;'>🕓Última ejecución: {last_exec_dt.strftime('%d/%m/%Y %H:%M')}</div>"
                        except:
                            pass
                    
                    col1, col2 = st.columns([5, 1])
                    with col1:
                        st.markdown(f"""
                        <div style="border: 1px solid #e0e0e0; border-radius: 0.5rem; padding: 0.7rem 1rem; margin-bottom: 0.7rem; background: #fafbfc;">
                            <div style="font-weight: 600; font-size: 1.05rem; margin-bottom: 0.3rem; color: #1f1f1f;">{script['name']}</div>
                            <div style="color: #666; font-size: 0.93rem;">{script['description']}</div>
                            {last_exec_str}
                        </div>
                        """, unsafe_allow_html=True)
                    with col2:
                        # Add vertical centering
                        st.markdown('<div style="padding-top: 0.5rem;"></div>', unsafe_allow_html=True)
                        
                        # Custom styled button without emoji
                        button_label = "Ejecutar script" if not script_executing else "En ejecución..."
                        if st.button(
                            button_label,
                            key=f"run_{script['name']}",
                            help=f"Ejecutar: {script['description']}",
                            use_container_width=True,
                            type="primary",
                            disabled=script_executing
                        ):
                            st.session_state.selected_script = script['name']
                            st.session_state.current_page = 'script_execution'
                            st.rerun()

                st.markdown("<div style='margin-bottom: 0.3rem;'></div>", unsafe_allow_html=True)
