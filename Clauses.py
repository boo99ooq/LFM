import streamlit as st
import pandas as pd
from github import Github
from io import StringIO
import math
import base64
from datetime import datetime

# --- 1. CONFIGURAZIONE ---
SCADENZA = datetime(2026, 8, 1)
OGGI = datetime.now()
PORTALE_APERTO = OGGI >= SCADENZA
ADMIN_SQUADRE = ["Liverpool Football Club", "Villarreal", "Reggina Calcio 1914", "Siviglia"]

# =========================================================================
# 🎨 APPLICAZIONE DELLO STILE CSS (Grafica Scura e Dorata)
# =========================================================================
stile_css = """
<style>
html, body, [class*="css"] { font-family: 'Poppins', sans-serif !important; }
.stApp {
background: radial-gradient(circle at 50% -10%, #12203d 0%, var(--navy-dark) 55%) fixed;
}
/* SIDEBAR */
section[data-testid="stSidebar"] {
background: linear-gradient(180deg, var(--navy) 0%, var(--navy-dark) 100%);
border-right: 1px solid rgba(212,175,55,0.18);
}
section[data-testid="stSidebar"] * { color: #E8ECF4 !important; }
/* TEXT */
h1, h2, h3 { color: #F2F4F8 !important; font-weight: 800 !important; }
p, span, label, .stMarkdown, .stCaption { color: var(--text-soft); }
/* TITLE BAR */
.lfm-header {
background: linear-gradient(120deg, #0d1526 0%, #1b2846 55%, #0d1526 100%);
border: 1px solid rgba(212,175,55,0.35);
border-radius: 18px;
padding: 18px 26px;
margin-bottom: 22px;
display: flex;
align-items: center;
gap: 18px;
box-shadow: 0 8px 24px rgba(0,0,0,0.45);
}
.lfm-header img { width: 64px; }
.lfm-header .title {
background: linear-gradient(90deg, var(--gold-light), var(--gold), var(--gold-light));
-webkit-background-clip: text; -webkit-text-fill-color: transparent;
background-clip: text;
font-size: 1.9rem; font-weight: 900; text-transform: uppercase; letter-spacing: 1px;
}
.lfm-header .subtitle { color: var(--text-soft); font-size: 0.95rem; margin-top: -4px;}
/* BUTTONS */
.stButton>button {
background: linear-gradient(135deg, var(--gold-light) 0%, var(--gold) 60%, #a9791e 100%);
color: #131a2b !important;
font-weight: 700 !important;
border: none !important;
border-radius: 10px !important;
padding: 0.55rem 1.3rem !important;
transition: all 0.18s ease;
box-shadow: 0 4px 10px rgba(0,0,0,0.35);
}
.stButton>button:hover { transform: translateY(-2px); box-shadow: 0 8px 18px rgba(212,175,55,0.35); }
.stButton>button p { color: #131a2b !important; font-weight: 700 !important; }
/* INPUTS */
div[data-baseweb="input"], div[data-baseweb="select"] > div {
background-color: var(--navy-card) !important;
border: 2px solid var(--gold) !important;
border-radius: 14px !important;
}
input, textarea, div[data-baseweb="select"] span { color: #FFFFFF !important; }
input[type="number"] { font-size: 2.6rem !important; font-weight: 900 !important; color: var(--gold-light) !important; text-align: center !important; }
input[type="password"] { font-size: 1.2rem !important; color: #fff !important; text-align: left !important; }
/* EXPANDERS → TEAM CARDS */
div[data-testid="stExpander"] {
background: linear-gradient(150deg, var(--navy-card), var(--navy-card-2));
border: 1px solid rgba(212,175,55,0.28) !important;
border-radius: 16px !important;
margin-bottom: 16px;
box-shadow: 0 6px 16px rgba(0,0,0,0.4);
overflow: hidden;
}
div[data-testid="stExpander"] summary {
font-weight: 700 !important;
color: #F2F4F8 !important;
padding: 6px 4px;
}
div[data-testid="stExpander"] summary:hover { color: var(--gold-light) !important; }
/* METRIC CARDS */
div[data-testid="stMetric"] {
background: linear-gradient(150deg, var(--navy-card), var(--navy-card-2));
border: 1px solid rgba(212,175,55,0.25);
border-radius: 14px;
padding: 14px 18px 10px 18px;
box-shadow: 0 6px 14px rgba(0,0,0,0.35);
}
div[data-testid="stMetricLabel"] { color: #9aa4b8 !important; font-weight: 600 !important; }
div[data-testid="stMetricValue"] { color: var(--gold-light) !important; font-weight: 800 !important; }
/* GENERIC CARD */
.lfm-card {
background: linear-gradient(150deg, var(--navy-card), var(--navy-card-2));
border: 1px solid rgba(212,175,55,0.25);
border-radius: 16px;
padding: 18px 22px;
margin-bottom: 16px;
box-shadow: 0 6px 16px rgba(0,0,0,0.4);
}
/* PLAYER NAME (terminale blindaggio) */
.player-name {
background: linear-gradient(90deg, var(--gold-light), var(--gold));
-webkit-background-clip: text; -webkit-text-fill-color: transparent; background-clip: text;
font-size: 2.6rem !important; font-weight: 900 !important; text-transform: uppercase;
margin-bottom: -6px;
}
.fvm-sub { color: var(--text-soft); font-size: 1.05rem; margin-bottom: 18px; }
/* PLAYER ROW (mercato) */
.player-row {
display: flex; align-items: center; justify-content: space-between;
background: rgba(255,255,255,0.03);
border: 1px solid rgba(212,175,55,0.12);
border-radius: 12px;
padding: 10px 14px;
margin-bottom: 8px;
}
.player-row .p-name { font-weight: 700; color: #F2F4F8; }
.player-row .p-value {
background: rgba(212,175,55,0.14);
color: var(--gold-light);
font-weight: 700;
border-radius: 20px;
padding: 4px 14px;
font-size: 0.9rem;
}
/* BADGES BLINDATO / VULNERABILE */
.badge-ok {
background: rgba(46, 204, 113, 0.15); color: #4ade80; border: 1px solid rgba(74,222,128,0.4);
border-radius: 10px; padding: 8px 10px; font-weight: 700; text-align: center;
}
.badge-ko {
background: rgba(239, 68, 68, 0.15); color: #f87171; border: 1px solid rgba(248,113,113,0.4);
border-radius: 10px; padding: 8px 10px; font-weight: 700; text-align: center;
}
/* BUDGET BOX */
.budget-box {
background: linear-gradient(150deg, var(--navy-card), var(--navy-card-2));
padding: 18px 22px; border-radius: 16px;
border: 1px solid rgba(212,175,55,0.3);
box-shadow: 0 6px 16px rgba(0,0,0,0.4);
margin-bottom: 8px;
}
hr { border-color: rgba(212,175,55,0.2) !important; }
</style>
"""

st.markdown(stile_css, unsafe_allow_html=True)
# =========================================================================

try:
    TOKEN = st.secrets["GITHUB_TOKEN"]
    REPO_NAME = st.secrets["REPO_NAME"]
    g = Github(TOKEN)
    repo = g.get_repo(REPO_NAME)
except:
    st.error("Errore configurazione GitHub nei Secrets.")
    st.stop()

# --- 2. FUNZIONI TECNICHE (INVARIATE) ---
def carica_csv(file_name):
    try:
        content = repo.get_contents(file_name)
        return pd.read_csv(StringIO(content.decoded_content.decode("latin1")))
    except: return pd.DataFrame()

def salva_file_github(path, df, msg):
    csv_buffer = df.to_csv(index=False)
    f = repo.get_contents(path)
    repo.update_file(path, msg, csv_buffer, f.sha)

def salva_clausola_singola(squadra, dati_stringa):
    path = "clausole_segrete.csv"
    nuova_riga = f"{squadra},{dati_stringa}"
    try:
        f = repo.get_contents(path)
        content_vecchio = f.decoded_content.decode("utf-8")
        nuovo_contenuto = content_vecchio + "\n" + nuova_riga
        repo.update_file(path, "Nuovo blindaggio segreto", nuovo_contenuto, f.sha)
    except:
        repo.create_file(path, "Inizializzazione clausole", nuova_riga)

# --- 3. LOGICA DI CALCOLO TASSE ---
def calcola_tassa_giocatore(ruolo, qt_iniziale, fvm):
    moltiplicatore = 1.5 if ruolo in ['A', 'C'] else 1.2
    base = fvm * moltiplicatore
    if base <= 15:
        return 2
    elif base <= 35:
        return 5
    elif base <= 65:
        return 10
    else:
        eccedenza = base - 65
        tassa = 10 + math.floor(eccedenza / 10) * 3
        return tassa

# --- 4. INTERFACCIA PRINCIPALE ---
st.markdown('''
<div class="lfm-header">
    <div class="title">Accesso Portale</div>
</div>
''', unsafe_allow_html=True)

squadra_selezionata = st.sidebar.selectbox("Squadra", ADMIN_SQUADRE)
pin_inserito = st.sidebar.text_input("PIN Segreto", type="password")

if pin_inserito:
    df_rose = carica_csv("rose.csv")
    df_quot = carica_csv("quot.csv")
    
    if df_rose.empty or df_quot.empty:
        st.error("Impossibile caricare i file dei dati da GitHub.")
        st.stop()
        
    giocatori_squadra = df_rose[df_rose['Squadra'] == squadra_selezionata]
    
    if giocatori_squadra.empty:
        st.warning(f"Nessun giocatore trovato per la squadra {squadra_selezionata}")
    else:
        st.write(f"### Gestione Blindaggi - {squadra_selezionata}")
        
        tot_tasse = 0
        crediti_totali = 500  # Esempio budget iniziale fisso
        dati_invio = []
        
        for idx, row in giocatori_squadra.iterrows():
            p_id = row['Id']
            info_giocatore = df_quot[df_quot['Id'] == p_id]
            
            if not info_giocatore.empty:
                nome = info_giocatore.iloc[0]['Nome']
                ruolo = info_giocatore.iloc[0]['R']
                qt = info_giocatore.iloc[0]['Qt.I']
                fvm = info_giocatore.iloc[0]['FVM']
                
                tassa_base = calcola_tassa_giocatore(ruolo, qt, fvm)
                tot_tasse += tassa_base
                
                st.markdown(f'''
                <div class="lfm-card">
                    <div class="player-name">{nome}</div>
                    <div class="fvm-sub">{ruolo} | Quotazione Iniziale: {qt} | FVM: {fvm}</div>
                ''', unsafe_allow_html=True)
                
                val = st.number_input(f"Valore Blindaggio per {nome}", min_value=0, value=int(fvm), key=f"val_{p_id}")
                
                # Controllo rivali (Simulato nel frammento)
                max_rivale = 0 
                if val <= max_rivale:
                    st.markdown("<div class='badge-ko'>🔓 VULNERABILE</div>", unsafe_allow_html=True)
                else:
                    st.markdown("<div class='badge-ok'>🛡️ BLINDATO</div>", unsafe_allow_html=True)
                st.markdown("</div>", unsafe_allow_html=True)
                dati_invio.append(f"{p_id}:{nome}:{val}")

        st.write("---\")")
        eccedenza = max(0, tot_tasse - 60)
        budget_residuo = crediti_totali - eccedenza

        if tot_tasse <= 60:
            st.success(f"✅ Il Bonus Lega di 60cr copre interamente le tue tasse ({tot_tasse} cr). Il tuo budget resta intatto.")
        else:
            st.warning(f"⚠️ Il Bonus Lega copre le tue tasse fino a 60cr. Eccedi il bonus di **{eccedenza} crediti** (Tasse totali: {tot_tasse} cr), che verranno scalati dal tuo budget.")

        c_fin1, c_fin2, c_fin3 = st.columns(3)
        c_fin1.metric("Totale Tasse", f"{tot_tasse} cr")
        c_fin2.metric("Franchigia Bonus", "- 60 cr")
        c_fin3.metric("Budget Residuo", f"{budget_residuo} cr")
        
        if st.button("Invia Scelte Segrete"):
            stringa_finale = "|".join(dati_invio)
            salva_clausola_singola(squadra_selezionata, stringa_finale)
            st.success("🔒 Scelte salvate con successo su GitHub!")
