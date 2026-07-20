import streamlit as st
import pandas as pd
from github import Github
from io import StringIO
import math
from datetime import datetime
import time
import re

# --- 1. CONFIGURAZIONE ---
FORZA_MODALITA = False  # False = Terminale Blindaggi | True = Mercato

SCADENZA = datetime(2026, 8, 1) 
OGGI = datetime.now()

if FORZA_MODALITA:
    PORTALE_APERTO = True
else:
    PORTALE_APERTO = OGGI >= SCADENZA

ADMIN_SQUADRE = ["Liverpool Football Club", "Villarreal", "Reggina Calcio 1914", "Siviglia"]

try:
    TOKEN = st.secrets["GITHUB_TOKEN"]
    REPO_NAME = st.secrets["REPO_NAME"]
    g = Github(TOKEN)
    repo = g.get_repo(REPO_NAME)
except:
    st.error("Errore configurazione GitHub nei Secrets.")
    st.stop()

# --- 2. FUNZIONI UTILITY ---
def pulisci_nome(nome):
    """Pulisce il nome rimuovendo TUTTO ciò che non è una lettera all'inizio"""
    if not nome or pd.isna(nome):
        return ""
    
    nome_pulito = str(nome).strip()
    
    # Rimuovi tutto fino al primo carattere alfabetico (A-Z o a-z)
    match = re.search(r'[A-Za-z]', nome_pulito)
    if match:
        nome_pulito = nome_pulito[match.start():]
    
    # Se il nome inizia con una lettera minuscola, rendila maiuscola
    if nome_pulito and nome_pulito[0].islower():
        nome_pulito = nome_pulito[0].upper() + nome_pulito[1:]
    
    # Rimuovi spazi multipli
    nome_pulito = re.sub(r'\s+', ' ', nome_pulito).strip()
    
    # Se il nome è vuoto o troppo corto, restituisci l'originale
    if not nome_pulito or len(nome_pulito) < 2:
        return str(nome).strip()
    
    return nome_pulito

def get_team_display_name(squadra):
    """Restituisce il nome della squadra pulito per la visualizzazione"""
    return pulisci_nome(squadra)

# --- 3. FUNZIONI GITHUB ---
@st.cache_data(ttl=300)
def carica_csv(file_name):
    try:
        content = repo.get_contents(file_name)
        return pd.read_csv(StringIO(content.decoded_content.decode("utf-8")))
    except: 
        return pd.DataFrame()

def salva_file_github(path, df, msg):
    time.sleep(0.5)
    csv_buffer = df.to_csv(index=False)
    try:
        f = repo.get_contents(path)
        repo.update_file(path, msg, csv_buffer, f.sha)
    except Exception as e:
        st.error(f"Errore salvataggio: {e}")
        raise

def salva_clausola_singola(squadra, dati_stringa):
    path = "clausole_segrete.csv"
    nuova_riga = f"{squadra},{dati_stringa}"
    try:
        f = repo.get_contents(path)
        contenuto = f.decoded_content.decode("utf-8")
        righe = [r for r in contenuto.splitlines() if not r.startswith(f"{squadra},")]
        righe.append(nuova_riga)
        repo.update_file(path, f"Update {squadra}", "\n".join(righe), f.sha)
    except:
        repo.create_file(path, "Inizializzazione", nuova_riga)

def carica_clausole_salvate():
    """Legge clausole_segrete.csv e restituisce {squadra: 'id:nome:valore;id:nome:valore'}"""
    salvati = {}
    try:
        f = repo.get_contents("clausole_segrete.csv")
        for riga in f.decoded_content.decode("utf-8").splitlines():
            if riga.strip() and "," in riga:
                s, d = riga.split(",", 1)
                salvati[s] = d
    except:
        pass
    return salvati

def registra_richiesta_clausola(acquirente, proprietario, player_id, nome, costo):
    time.sleep(0.5)
    path = "richieste_scippo.csv"
    orario = datetime.now().strftime("%H:%M:%S")
    nuova_riga = f"{acquirente},{proprietario},{player_id},{nome},{costo},PENDENTE,{orario}\n"
    try:
        f = repo.get_contents(path)
        contenuto = f.decoded_content.decode("utf-8") + nuova_riga
        repo.update_file(path, f"Clausola Rescissoria: {nome} alle {orario}", contenuto, f.sha)
    except:
        header = "Acquirente,Proprietario,Id,Nome,Costo,Stato,Orario\n"
        repo.create_file(path, "Init Richieste", header + nuova_riga)

def calcola_tassa(valore):
    if valore <= 200: 
        tassa = valore * 0.10
    elif valore <= 300: 
        tassa = 20 + (valore - 200) * 0.15
    else: 
        tassa = 20 + 15 + (valore - 300) * 0.20
    return math.ceil(tassa)

# --- 4. UI E CSS ---
st.set_page_config(
    page_title="LFM - Portale Clausole", 
    page_icon="🛡️", 
    layout="wide",
    initial_sidebar_state="expanded"
)

st.markdown("""
<style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800;900&display=swap');
    
    html, body, [class*="css"], p, span, div, label, h1, h2, h3, h4, h5, h6,
    button, input, textarea, select, .stMarkdown, .stButton, .stMetric,
    div[data-testid="stExpander"] summary {
        font-family: 'Inter', sans-serif;
    }

    /* Le icone di sistema Streamlit (menu in alto a destra, frecce expander, */
    /* pulsante hamburger) usano un font a legature: qui va ripristinato */
    /* ESPLICITAMENTE, "unset" non basta perché eredita Inter dal genitore. */
    [data-testid="stIconMaterial"],
    [data-testid="stExpanderToggleIcon"],
    [data-testid="baseButton-header"],
    [data-testid="stHeaderActionElements"],
    [data-testid="stHeaderActionElements"] *,
    [data-testid="stToolbarActions"],
    [data-testid="stToolbarActions"] *,
    [data-testid="stMainMenu"],
    [data-testid="stMainMenu"] *,
    [data-testid="stSidebarCollapseButton"],
    [data-testid="stSidebarCollapseButton"] *,
    span[class*="material-symbols"],
    span[class*="material-icons"],
    i[class*="material-symbols"],
    i[class*="material-icons"] {
        font-family: 'Material Symbols Rounded', 'Material Symbols Outlined', 'Material Icons', sans-serif !important;
    }

    .stApp {
        background: linear-gradient(135deg, #0a0e1a 0%, #141b2d 50%, #1a2338 100%);
    }
    
    .player-card {
        background: linear-gradient(145deg, #1a2338, #0f1628);
        border-radius: 20px;
        padding: 24px;
        margin-bottom: 20px;
        border: 1px solid rgba(255, 215, 0, 0.15);
        box-shadow: 0 8px 32px rgba(0,0,0,0.4);
        transition: all 0.3s ease;
    }
    
    .player-card:hover {
        border-color: rgba(255, 215, 0, 0.3);
        transform: translateY(-2px);
        box-shadow: 0 12px 40px rgba(0,0,0,0.5);
    }
    
    .player-name {
        background: linear-gradient(135deg, #FFD700, #FFA500, #FFD700);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
        background-clip: text;
        font-size: 2.4rem !important;
        font-weight: 900 !important;
        text-transform: uppercase;
        letter-spacing: 1px;
        margin-bottom: 4px;
        text-align: center;
    }
    
    .fvm-sub {
        color: #94a3b8 !important;
        font-size: 1rem !important;
        margin-bottom: 20px;
        padding-bottom: 16px;
        border-bottom: 1px solid rgba(255,215,0,0.1);
        text-align: center;
    }
    
    div[data-baseweb="input"] {
        background: #0f1628 !important;
        border: 2px solid rgba(255, 215, 0, 0.3) !important;
        border-radius: 14px !important;
        transition: all 0.3s ease;
    }
    
    div[data-baseweb="input"]:focus-within {
        border-color: #FFD700 !important;
        box-shadow: 0 0 20px rgba(255, 215, 0, 0.1);
    }
    
    input[type="number"] {
        font-size: 2.8rem !important;
        font-weight: 900 !important;
        color: #FFD700 !important;
        text-align: center !important;
        background: transparent !important;
    }
    
    .stProgress > div > div {
        background: linear-gradient(90deg, #FFD700, #FF6B00) !important;
        border-radius: 10px !important;
        height: 8px !important;
    }
    
    .badge-safe {
        background: rgba(34, 197, 94, 0.15);
        border: 1px solid rgba(34, 197, 94, 0.3);
        border-radius: 12px;
        padding: 12px 16px;
        text-align: center;
        color: #4ade80;
        font-weight: 700;
    }
    
    .badge-danger {
        background: rgba(239, 68, 68, 0.15);
        border: 1px solid rgba(239, 68, 68, 0.3);
        border-radius: 12px;
        padding: 12px 16px;
        text-align: center;
        color: #f87171;
        font-weight: 700;
    }
    
    .budget-box {
        background: linear-gradient(145deg, #1a2338, #0f1628);
        border-radius: 16px;
        padding: 20px 24px;
        border: 1px solid rgba(255, 215, 0, 0.2);
        margin-bottom: 24px;
        box-shadow: 0 4px 20px rgba(0,0,0,0.3);
    }
    
    div[data-testid="stMetric"] {
        background: linear-gradient(145deg, #1a2338, #0f1628);
        border-radius: 14px;
        padding: 16px 20px;
        border: 1px solid rgba(255, 215, 0, 0.1);
    }
    
    div[data-testid="stMetricLabel"] {
        color: #94a3b8 !important;
        font-weight: 600 !important;
    }
    
    div[data-testid="stMetricValue"] {
        color: #FFD700 !important;
        font-weight: 800 !important;
    }
    
    div[data-testid="stExpander"] {
        background: linear-gradient(145deg, #1a2338, #0f1628) !important;
        border: 1px solid rgba(255, 215, 0, 0.12) !important;
        border-radius: 16px !important;
        margin-bottom: 12px !important;
        box-shadow: 0 4px 16px rgba(0,0,0,0.3) !important;
    }
    
    div[data-testid="stExpander"] summary {
        font-weight: 700 !important;
        color: #FFD700 !important;
        padding: 12px 4px !important;
        font-size: 1.4rem !important;
        text-align: center !important;
        text-shadow: 0 0 30px rgba(255,215,0,0.15) !important;
        letter-spacing: 0.5px !important;
    }
    
    div[data-testid="stExpander"] summary:hover {
        color: #FFE44D !important;
        text-shadow: 0 0 50px rgba(255,215,0,0.3) !important;
    }
    
    .stButton > button {
        background: linear-gradient(135deg, #FFD700, #F59E0B) !important;
        color: #0f1628 !important;
        font-weight: 700 !important;
        border: none !important;
        border-radius: 12px !important;
        padding: 0.6rem 1.5rem !important;
        transition: all 0.3s ease !important;
        box-shadow: 0 4px 16px rgba(255, 215, 0, 0.2) !important;
    }
    
    .stButton > button:hover {
        transform: translateY(-2px) !important;
        box-shadow: 0 8px 24px rgba(255, 215, 0, 0.3) !important;
    }
    
    section[data-testid="stSidebar"] {
        background: linear-gradient(180deg, #0f1628, #0a0e1a) !important;
        border-right: 1px solid rgba(255, 215, 0, 0.1) !important;
    }
    
    section[data-testid="stSidebar"] * {
        color: #e2e8f0 !important;
    }
    
    h1, h2, h3 {
        color: #e2e8f0 !important;
        font-weight: 800 !important;
        text-align: center !important;
    }
    
    hr {
        border-color: rgba(255, 215, 0, 0.15) !important;
        margin: 24px 0 !important;
    }
    
    p, span, label, .stMarkdown {
        color: #94a3b8 !important;
    }
    
    .stAlert {
        border-radius: 12px !important;
        border: none !important;
    }
    
    .stAlert > div {
        background: rgba(255, 215, 0, 0.05) !important;
    }
    
    .player-row {
        display: flex;
        align-items: center;
        justify-content: space-between;
        padding: 8px 0;
        border-bottom: 1px solid rgba(255,215,0,0.06);
    }
    
    .player-row:last-child {
        border-bottom: none;
    }
    
    .player-row .p-name {
        color: #e2e8f0 !important;
        font-weight: 600 !important;
    }
    
    .player-row .p-value {
        background: rgba(255, 215, 0, 0.12);
        color: #FFD700;
        font-weight: 700;
        padding: 4px 14px;
        border-radius: 20px;
        font-size: 0.9rem;
    }
    
    .header-bar {
        display: flex;
        align-items: center;
        gap: 16px;
        margin-bottom: 24px;
        padding: 16px 24px;
        background: linear-gradient(145deg, #1a2338, #0f1628);
        border-radius: 16px;
        border: 1px solid rgba(255,215,0,0.15);
    }
    
    .status-badge {
        display: inline-block;
        padding: 4px 16px;
        border-radius: 20px;
        font-size: 0.85rem;
        font-weight: 700;
    }
    
    .status-open {
        background: rgba(34, 197, 94, 0.2);
        color: #4ade80;
        border: 1px solid rgba(34, 197, 94, 0.3);
    }
    
    .status-closed {
        background: rgba(239, 68, 68, 0.2);
        color: #f87171;
        border: 1px solid rgba(239, 68, 68, 0.3);
    }
    
    button[data-testid="baseButton-header"] {
        font-size: 0 !important;
    }
    button[data-testid="baseButton-header"]::before {
        content: "☰" !important;
        font-size: 1.5rem !important;
    }
    
    .login-container {
        background: #1a2338;
        padding: 30px;
        border-radius: 20px;
        border: 1px solid rgba(255,215,0,0.1);
    }
    
    .login-title {
        text-align: center;
        padding: 30px 0 20px 0;
    }
    .login-title .icon {
        font-size: 4rem;
    }
    .login-title h1 {
        font-size: 2.8rem;
        margin: 0;
        background: linear-gradient(135deg, #FFD700, #FFA500);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
    }
    .login-title p {
        color: #94a3b8;
        font-size: 1.1rem;
        margin-top: 8px;
    }
    
    .terminal-header {
        text-align: center;
        padding: 16px 0;
        margin-bottom: 24px;
    }
    .terminal-header .title {
        font-size: 2.2rem;
        font-weight: 900;
        color: #FFD700;
    }
    .terminal-header .subtitle {
        color: #94a3b8;
        font-size: 1rem;
        margin-top: 4px;
    }
</style>
""", unsafe_allow_html=True)

# --- 5. STATO SESSIONE ---
if 'loggato' not in st.session_state:
    st.session_state.loggato = False
    st.session_state.squadra = None
    
if 'portale_aperto' not in st.session_state:
    st.session_state.portale_aperto = PORTALE_APERTO

# --- 6. CARICAMENTO DATI ---
df_leghe = carica_csv("leghe.csv")

# Pulisci i nomi delle squadre nel DataFrame
if not df_leghe.empty:
    df_leghe['Squadra_Pulita'] = df_leghe['Squadra'].apply(pulisci_nome)

# --- 7. FUNZIONE PER OTTENERE SQUADRE PULITE ---
def get_clean_teams(lega=None):
    """Restituisce un dizionario {nome_pulito: nome_originale} per le squadre"""
    if lega:
        df_filtered = df_leghe[df_leghe['Lega'] == lega]
    else:
        df_filtered = df_leghe
    
    teams = {}
    for _, row in df_filtered.iterrows():
        original = row['Squadra']
        clean = row.get('Squadra_Pulita', pulisci_nome(original))
        if not clean:
            clean = original
        teams[clean] = original
    return teams

# --- 8. LOGIN ---
if not st.session_state.loggato:
    st.markdown("""
    <div class="login-title">
        <div class="icon">🛡️</div>
        <h1>LFM - Accesso Portale</h1>
        <p>Inserisci le tue credenziali per accedere</p>
    </div>
    """, unsafe_allow_html=True)
    
    if not df_leghe.empty:
        col1, col2, col3 = st.columns([1, 1.5, 1])
        with col2:
            with st.container():
                st.markdown('<div class="login-container">', unsafe_allow_html=True)
                
                lega = st.selectbox("📋 Lega", df_leghe['Lega'].unique())
                teams_dict = get_clean_teams(lega)
                clean_team_names = list(teams_dict.keys())
                selected_clean = st.selectbox("🏟️ Squadra", clean_team_names)
                squadra = teams_dict[selected_clean]
                pin = st.text_input("🔑 PIN Segreto", type="password")
                
                if st.button("🚀 ACCEDI", use_container_width=True):
                    try:
                        pin_r = df_leghe[df_leghe['Squadra'] == squadra]['PIN'].values[0]
                        if str(pin) == str(pin_r):
                            st.session_state.loggato = True
                            st.session_state.squadra = squadra
                            st.rerun()
                        else:
                            st.error("❌ PIN errato. Riprova.")
                    except:
                        st.error("❌ Squadra non trovata. Contatta l'amministratore.")
                
                st.markdown('</div>', unsafe_allow_html=True)

# --- 9. AREA LOGGATO ---
else:
    # Header
    status_text = "🔓 MERCATO APERTO" if st.session_state.portale_aperto else "🛡️ TERMINALE BLINDAGGI"
    status_class = "status-open" if st.session_state.portale_aperto else "status-closed"
    squadra_display = get_team_display_name(st.session_state.squadra)
    
    st.markdown(f"""
    <div class="header-bar">
        <div style="font-size: 2.8rem;">🛡️</div>
        <div style="flex: 1;">
            <div style="color: #94a3b8; font-size: 0.9rem;">LFM · Portale Clausole</div>
            <div style="font-size: 1.4rem; font-weight: 800; color: #FFD700;">{squadra_display}</div>
        </div>
        <div>
            <span class="status-badge {status_class}">{status_text}</span>
        </div>
    </div>
    """, unsafe_allow_html=True)

    # --- 10. SIDEBAR ADMIN ---
    if st.session_state.squadra in ADMIN_SQUADRE:
        with st.sidebar:
            st.markdown("### 🕵️ PANNELLO ADMIN")
            st.markdown("---")
            
            nuova_modalita = st.toggle(
                "🔓 Modalità Mercato", 
                value=st.session_state.portale_aperto,
                help="Attiva per vedere il mercato, disattiva per il terminale blindaggi"
            )
            if nuova_modalita != st.session_state.portale_aperto:
                st.session_state.portale_aperto = nuova_modalita
                st.rerun()
            
            st.markdown("---")
            
            st.markdown("#### 📝 Stato Blindaggi")
            salvati_admin = carica_clausole_salvate()
            consegnate = list(salvati_admin.keys())
            mancanti = [s for s in df_leghe['Squadra'].unique() if s not in consegnate]

            col1, col2 = st.columns(2)
            col1.metric("Consegnate", f"{len(consegnate)}")
            col2.metric("Mancanti", f"{len(mancanti)}")
            if st.checkbox("👀 Vedi chi manca"):
                for m in mancanti:
                    st.text(f"❌ {get_team_display_name(m)}")
            
            st.markdown("---")
            
            st.markdown("#### 💸 Clausole Rescissorie")
            if st.checkbox("📥 GESTISCI RICHIESTE"):
                df_sc = carica_csv("richieste_scippo.csv")
                if not df_sc.empty:
                    pendenti = df_sc[df_sc['Stato'].astype(str).str.contains('PENDENTE', na=False)]
                    if pendenti.empty:
                        st.info("✅ Nessuna richiesta pendente")
                    else:
                        st.warning(f"📬 {len(pendenti)} richieste in attesa")
                        for i, r in pendenti.iterrows():
                            acquirente_clean = get_team_display_name(r['Acquirente'])
                            proprietario_clean = get_team_display_name(r['Proprietario'])
                            with st.expander(f"🕒 {r['Orario']} - {r['Nome']}"):
                                st.write(f"**Acquirente:** {acquirente_clean}")
                                st.write(f"**Proprietario:** {proprietario_clean}")
                                st.write(f"**Costo:** {r['Costo']} cr")
                                c_adm1, c_adm2 = st.columns(2)
                                if c_adm1.button("✅ APPROVA", key=f"ok_{i}", use_container_width=True):
                                    df_l = carica_csv("leghe.csv")
                                    df_l.loc[df_l['Squadra'] == r['Acquirente'], 'Crediti'] -= int(r['Costo'])
                                    df_l.loc[df_l['Squadra'] == r['Proprietario'], 'Crediti'] += int(r['Costo'])
                                    salva_file_github("leghe.csv", df_l, f"Pagata clausola rescissoria {r['Nome']}")
                                    df_ros = carica_csv("fantamanager-2021-rosters.csv")
                                    df_ros.loc[df_ros['Id'].astype(str) == str(r['Id']), 'Squadra_LFM'] = r['Acquirente']
                                    salva_file_github("fantamanager-2021-rosters.csv", df_ros, f"Trasferimento {r['Nome']}")
                                    df_sc.at[i, 'Stato'] = 'APPROVATO'
                                    salva_file_github("richieste_scippo.csv", df_sc, "Richiesta approvata")
                                    st.rerun()
                                if c_adm2.button("❌ RIFIUTA", key=f"no_{i}", use_container_width=True):
                                    df_sc.at[i, 'Stato'] = 'RIFIUTATO'
                                    salva_file_github("richieste_scippo.csv", df_sc, "Richiesta rifiutata")
                                    st.rerun()
                else:
                    st.info("📭 Nessuna richiesta presente")

    # --- 11. LOGICA PRINCIPALE ---
    
    # SEZIONE MERCATO (PORTALE APERTO)
    if st.session_state.portale_aperto:
        st.markdown("""
        <div style="text-align: center; padding: 10px 0 20px 0;">
            <h2 style="font-size: 2.5rem; color: #FFD700; text-shadow: 0 0 40px rgba(255,215,0,0.3);">🔓 Mercato Clausole Rescissorie</h2>
            <p style="color: #94a3b8; font-size: 1.1rem;">Acquista i giocatori pagando la loro clausola rescissoria</p>
        </div>
        """, unsafe_allow_html=True)
        
        lega_view = st.selectbox("📋 Filtra Lega", df_leghe['Lega'].unique())
        my_cred = df_leghe[df_leghe['Squadra'] == st.session_state.squadra]['Crediti'].values[0]
        
        st.sidebar.markdown(f"""
        <div style="background: linear-gradient(145deg, #1a2338, #0f1628); padding: 20px; border-radius: 16px; border: 1px solid rgba(255,215,0,0.2); text-align: center; margin-bottom: 20px;">
            <div style="color: #94a3b8; font-weight: 600; font-size: 0.9rem;">💰 IL TUO BUDGET</div>
            <div style="color: #FFD700; font-weight: 900; font-size: 2.4rem;">{my_cred} cr</div>
        </div>
        """, unsafe_allow_html=True)

        df_r = carica_csv("fantamanager-2021-rosters.csv")
        df_q = carica_csv("quot.csv")
        
        # PULIZIA NOMI
        if not df_r.empty and 'Squadra_LFM' in df_r.columns:
            df_r['Squadra_LFM'] = df_r['Squadra_LFM'].astype(str).str.strip()
            df_r['Squadra_LFM'] = df_r['Squadra_LFM'].apply(pulisci_nome)
        
        if not df_q.empty and 'Nome' in df_q.columns:
            df_q['Nome'] = df_q['Nome'].apply(pulisci_nome)
        
        df_q['Id'] = df_q['Id'].astype(str)
        salvati = carica_clausole_salvate()

        # Mostra squadre
        for sq in df_leghe[df_leghe['Lega'] == lega_view]['Squadra']:
            sq_clean = get_team_display_name(sq)
            sq_c = df_leghe[df_leghe['Squadra'] == sq]['Crediti'].values[0]
            
            team_title = f"🏟️  {sq_clean.upper()}  ·  💰 {sq_c} cr"
            
            with st.expander(team_title):
                if sq in salvati:
                    giocatori = []
                    for p in salvati[sq].split(";"):
                        if not p.strip():
                            continue
                        pid, pnm, pvl = p.split(":")
                        giocatori.append((pid, pnm, int(pvl)))
                else:
                    st.caption("⚠️ Clausole d'ufficio applicate (Valore FVM)")
                    ids = df_r[df_r['Squadra_LFM'] == sq]['Id'].astype(str).tolist()
                    top_giocatori = df_q[df_q['Id'].isin(ids)].nlargest(3, 'FVM')
                    giocatori = [(row['Id'], row['Nome'], int(row['FVM'])) for _, row in top_giocatori.iterrows()]

                for pid, pnm, pvl in giocatori:
                    pnm_clean = get_team_display_name(pnm)
                    
                    col1, col2, col3 = st.columns([3, 1, 1.5])
                    with col1:
                        st.markdown(f"<div class='player-row' style='margin-bottom:0; border:none; padding:6px 0;'><span class='p-name'>⚽ {pnm_clean}</span></div>", unsafe_allow_html=True)
                    with col2:
                        st.markdown(f"<span class='p-value'>💰 {pvl} cr</span>", unsafe_allow_html=True)
                    if sq != st.session_state.squadra:
                        with col3:
                            if st.button("💸 PAGA", key=f"a_{pid}", use_container_width=True):
                                if my_cred >= pvl:
                                    registra_richiesta_clausola(st.session_state.squadra, sq, pid, pnm, pvl)
                                    st.success("✅ Richiesta inviata!")
                                    st.rerun()
                                else:
                                    st.error("❌ Budget insufficiente!")

    # SEZIONE TERMINALE BLINDAGGI (PORTALE CHIUSO)
    else:
        squadra_display = get_team_display_name(st.session_state.squadra)
        
        st.markdown(f"""
        <div class="terminal-header">
            <div class="title">🛡️ {squadra_display.upper()}</div>
            <div class="subtitle">Imposta le clausole per blindare i tuoi giocatori</div>
        </div>
        """, unsafe_allow_html=True)
        
        # VERIFICA CHE LA SQUADRA ESISTA
        squadra_found = False
        if not df_leghe.empty:
            squadra_match = df_leghe[df_leghe['Squadra'] == st.session_state.squadra]
            if not squadra_match.empty:
                squadra_found = True
                crediti_totali = squadra_match['Crediti'].values[0]
                mia_lega = squadra_match['Lega'].values[0]
                max_rivale = df_leghe[
                    (df_leghe['Squadra'] != st.session_state.squadra) &
                    (df_leghe['Lega'] == mia_lega)
                ]['Crediti'].max()
            else:
                st.error(f"⚠️ Squadra '{st.session_state.squadra}' non trovata nel database.")
                if st.button("🔄 TORNA AL LOGIN"):
                    st.session_state.loggato = False
                    st.session_state.squadra = None
                    st.rerun()
                st.stop()
        
        if squadra_found:
            st.markdown("<div class='budget-box'>", unsafe_allow_html=True)
            c1, c2, c3 = st.columns(3)
            c1.metric("💰 Budget Attuale", f"{crediti_totali} cr")
            c2.metric("🔝 Massimo Rivali", f"{max_rivale} cr")
            c3.info(f"Soglia Blindaggio: > {max_rivale} cr")
            st.markdown("</div>", unsafe_allow_html=True)

            df_r = carica_csv("fantamanager-2021-rosters.csv")
            df_q = carica_csv("quot.csv")
            
            if df_r.empty or df_q.empty:
                st.error("⚠️ Dati dei giocatori non disponibili.")
                st.stop()
            
            # PULIZIA NOMI
            if 'Squadra_LFM' not in df_r.columns:
                st.error(
                    f"⚠️ Il file 'fantamanager-2021-rosters.csv' non contiene la colonna "
                    f"'Squadra_LFM'. Colonne trovate: {df_r.columns.tolist()}. "
                    f"Controlla l'intestazione del file su GitHub (spazi, maiuscole, delimitatore)."
                )
                st.stop()
            df_r['Squadra_LFM'] = df_r['Squadra_LFM'].astype(str).str.strip()
            df_r['Squadra_LFM'] = df_r['Squadra_LFM'].apply(pulisci_nome)

            if 'Nome' in df_q.columns:
                df_q['Nome'] = df_q['Nome'].apply(pulisci_nome)

            df_q['Id'] = df_q['Id'].astype(str)
            ids_miei = df_r[df_r['Squadra_LFM'] == st.session_state.squadra]['Id'].astype(str).tolist()
            
            if not ids_miei:
                st.warning("⚠️ Nessun giocatore trovato per la tua squadra.")
                st.stop()

            # --- BUDGET NETTO: crediti - ingaggi rosa (Qt.I) - manutenzione stadio ---
            df_q['Qt.I'] = pd.to_numeric(df_q['Qt.I'], errors='coerce').fillna(0)
            costo_ingaggi = df_q[df_q['Id'].isin(ids_miei)]['Qt.I'].sum()

            LIVELLI_STADIO = [10, 20, 30, 40, 50, 60, 70, 80, 90, 100]
            MANUTENZIONE_STADIO = {10: 45, 20: 25, 30: 35, 40: 50, 50: 70,
                                    60: 90, 70: 120, 80: 150, 90: 185, 100: 215}

            df_stadi = carica_csv("stadi.csv")
            costo_stadio = 0
            capacita_stadio = None
            if not df_stadi.empty and 'Squadra' in df_stadi.columns and 'Stadio' in df_stadi.columns:
                stadio_match = df_stadi[df_stadi['Squadra'] == st.session_state.squadra]
                if not stadio_match.empty:
                    capacita_stadio = pd.to_numeric(stadio_match['Stadio'].values[0], errors='coerce')
                    if pd.notna(capacita_stadio):
                        livello_vicino = min(LIVELLI_STADIO, key=lambda x: abs(x - capacita_stadio))
                        costo_stadio = MANUTENZIONE_STADIO[livello_vicino]

            budget_netto = crediti_totali - costo_ingaggi - costo_stadio

            st.markdown("<div class='budget-box'>", unsafe_allow_html=True)
            n1, n2, n3, n4 = st.columns(4)
            n1.metric("💼 Ingaggi Rosa", f"-{int(costo_ingaggi)} cr", help="Somma di Qt.I (quot.csv) di tutti i giocatori in rosa")
            if capacita_stadio is not None and pd.notna(capacita_stadio):
                n2.metric("🏟️ Manutenzione Stadio", f"-{costo_stadio} cr", help=f"Capacità: {int(capacita_stadio)}.000 posti (stadi.csv)")
            else:
                n2.metric("🏟️ Manutenzione Stadio", "N/D", help="Squadra non trovata in stadi.csv")
            n3.metric("💰 Budget Netto Proiettato", f"{int(budget_netto)} cr")
            if budget_netto < 0:
                n4.error("⚠️ Negativo")
            else:
                n4.success("✅ In equilibrio")
            st.markdown("</div>", unsafe_allow_html=True)

            top_3 = df_q[df_q['Id'].isin(ids_miei)].copy()
            top_3['FVM'] = pd.to_numeric(top_3['FVM'], errors='coerce').fillna(0)
            top_3 = top_3.nlargest(3, 'FVM')

            # Carica l'eventuale bozza già salvata da questa squadra, per pre-riempire i campi
            bozza_salvata = carica_clausole_salvate().get(st.session_state.squadra, "")
            bozza_dict = {}
            if bozza_salvata:
                for p in bozza_salvata.split(";"):
                    if p.strip():
                        b_pid, b_nome, b_val = p.split(":")
                        bozza_dict[b_pid] = int(b_val)

            if bozza_dict:
                st.info("💾 Hai già una bozza salvata: i valori qui sotto sono quelli dell'ultimo salvataggio. Puoi modificarli liberamente fino alla scadenza.")
            else:
                st.caption("ℹ️ Nessuna bozza salvata finora: i campi partono dal valore FVM di default.")

            tot_tasse = 0
            dati_invio = []

            for i, (_, row) in enumerate(top_3.iterrows()):
                nome, fvm, p_id = row['Nome'], int(row['FVM']), row['Id']
                nome_clean = get_team_display_name(nome)
                valore_default = bozza_dict.get(str(p_id), fvm)
                
                st.markdown("<div class='player-card'>", unsafe_allow_html=True)
                st.markdown(f"<div class='player-name'>{nome_clean}</div>", unsafe_allow_html=True)
                st.markdown(f"<div class='fvm-sub'><span style='color:#94a3b8;'>Valore di Mercato (FVM):</span> <span style='color:#FFD700; font-weight:700;'>{fvm} cr</span></div>", unsafe_allow_html=True)
                
                col1, col2 = st.columns([1.8, 1.5])
                with col1:
                    val = st.number_input(
                        "💎 CLAUSOLA", 
                        min_value=1, 
                        value=valore_default, 
                        key=f"c_{p_id}",
                        help="Inserisci l'importo della clausola rescissoria"
                    )
                    progress = min(1.0, val / max_rivale) if max_rivale > 0 else 0
                    st.progress(progress)
                    if val > max_rivale:
                        st.caption(f"✅ Superata la soglia di {max_rivale} cr")
                    
                with col2:
                    st.write("")
                    t = calcola_tassa(val)
                    tot_tasse += t
                    c_t, c_s = st.columns(2)
                    with c_t:
                        st.metric("📊 Tassa", f"{t} cr")
                    with c_s:
                        if val <= max_rivale:
                            st.markdown("<div class='badge-danger'>🔓 VULNERABILE</div>", unsafe_allow_html=True)
                        else:
                            st.markdown("<div class='badge-safe'>🛡️ BLINDATO</div>", unsafe_allow_html=True)
                
                st.markdown("</div>", unsafe_allow_html=True)
                dati_invio.append(f"{p_id}:{nome}:{val}")

            st.markdown("---")
            st.markdown("### 📊 Riepilogo Clausole")
            
            extra = max(0, tot_tasse - 60)
            budget_residuo = crediti_totali - extra

            if tot_tasse <= 60:
                st.success(f"✅ Il Bonus Lega di 60cr copre interamente le tue tasse ({tot_tasse} cr). Il tuo budget resta intatto.")
            else:
                st.warning(f"⚠️ Il Bonus Lega copre le tue tasse fino a 60cr. Eccedi il bonus di **{extra} crediti** (Tasse totali: {tot_tasse} cr), che verranno scalati dal tuo budget.")

            c_fin1, c_fin2, c_fin3 = st.columns(3)
            c_fin1.metric("💰 Totale Tasse", f"{tot_tasse} cr")
            c_fin2.metric("🎁 Franchigia Bonus", "- 60 cr")
            c_fin3.metric("💳 Budget Rimanente", f"{budget_residuo} cr", delta=-extra if extra > 0 else 0)

            st.caption(f"🗓️ Potrai modificare questa bozza quante volte vuoi fino al {SCADENZA.strftime('%d/%m/%Y')}. Dopo quella data il Terminale si chiude e l'ultima bozza salvata diventa la clausola definitiva.")

            if st.button("📥 REGISTRA CLAUSOLE TEMPORANEAMENTE (PUOI MODIFICARLE FINO ALLA DEADLINE)", type="primary", use_container_width=True):
                with st.spinner("⏳ Salvataggio in corso..."):
                    try:
                        salva_clausola_singola(st.session_state.squadra, ";".join(dati_invio))
                        st.success(f"✅ Bozza salvata! Puoi tornare a modificarla in qualsiasi momento prima del {SCADENZA.strftime('%d/%m/%Y')}.")
                        st.balloons()
                    except Exception as e:
                        st.error(f"❌ Errore durante il salvataggio: {e}")
