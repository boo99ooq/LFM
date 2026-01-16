import streamlit as st
import pandas as pd
from github import Github
from io import StringIO
import math
from datetime import datetime

# --- 1. CONFIGURAZIONE TEMPORALE ---
SCADENZA = datetime(2026, 8, 1)
OGGI = datetime.now()
PORTALE_APERTO = OGGI >= SCADENZA

try:
    TOKEN = st.secrets["GITHUB_TOKEN"]
    REPO_NAME = st.secrets["REPO_NAME"]
    g = Github(TOKEN)
    repo = g.get_repo(REPO_NAME)
except:
    st.error("Errore configurazione GitHub.")
    st.stop()

# --- 2. FUNZIONI TECNICHE ---
def carica_csv(file_name):
    try:
        content = repo.get_contents(file_name)
        decoded = content.decoded_content.decode("latin1")
        return pd.read_csv(StringIO(decoded))
    except: return pd.DataFrame()

def calcola_tassa(valore):
    if valore <= 200: tassa = valore * 0.10
    elif valore <= 300: tassa = 20 + (valore - 200) * 0.15
    else: tassa = 20 + 15 + (valore - 300) * 0.20
    return math.ceil(tassa)

def salva_su_github(squadra, dati_stringa):
    path = "clausole_segrete.csv"
    nuova_riga = f"{squadra},{dati_stringa}\n"
    try:
        f = repo.get_contents(path)
        contenuto = f.decoded_content.decode("utf-8")
        righe = [r for r in contenuto.splitlines() if not r.startswith(f"{squadra},")]
        righe.append(nuova_riga.strip())
        repo.update_file(f.path, f"Update {squadra}", "\n".join(righe), f.sha)
    except:
        repo.create_file(path, "Inizializzazione", nuova_riga)

def recupera_precedenti(squadra):
    try:
        f = repo.get_contents("clausole_segrete.csv")
        testo = f.decoded_content.decode("utf-8")
        for riga in testo.splitlines():
            if riga.startswith(f"{squadra},"):
                dati = riga.split(",")[1]
                return {item.split(":")[0]: int(item.split(":")[1]) for item in dati.split(";")}
    except: return {}
    return {}

# --- 3. UI E CSS ---
st.set_page_config(page_title="LFM - Blindaggio", layout="wide")
st.markdown("""<style>
    .player-title { color: #0e1117; font-weight: 850; text-transform: uppercase; margin-top: 25px; border-bottom: 2px solid #e0e0e0; }
    .budget-box { background-color: #ffffff; padding: 15px; border-radius: 10px; border-left: 5px solid #1E3A8A; box-shadow: 2px 2px 5px rgba(0,0,0,0.05); }
</style>""", unsafe_allow_html=True)

if PORTALE_APERTO:
    # --- MODALITÀ TABELLONE PUBBLICO ---
    st.title("🔓 LFM - Tabellone Pubblico")
    # (Logica tabellone già vista...)
else:
    # --- MODALITÀ INSERIMENTO ---
    if 'loggato' not in st.session_state:
        st.session_state.loggato = False
        st.session_state.squadra = None

    df_leghe = carica_csv("leghe.csv")

    if not st.session_state.loggato:
        st.title("🛡️ LFM - Portale Blindaggio")
        lega = st.selectbox("Lega", df_leghe['Lega'].unique())
        squadra = st.selectbox("Squadra", df_leghe[df_leghe['Lega'] == lega]['Squadra'].unique())
        pin = st.text_input("PIN", type="password")
        if st.button("ACCEDI"):
            pin_reale = df_leghe[df_leghe['Squadra'] == squadra]['PIN'].values[0]
            if str(pin) == str(pin_reale):
                st.session_state.loggato = True
                st.session_state.squadra = squadra
                st.rerun()
            else: st.error("PIN errato.")
    else:
        # AREA ADMIN
        ADMIN_SQUADRE = ["Liverpool Football Club", "Villarreal", "Reggina Calcio 1914", "Siviglia"]
        if st.session_state.squadra in ADMIN_SQUADRE:
            # (Codice admin qui...)
            pass

        # RECUPERO DATI BUDGET UTENTE
        crediti_totali = df_leghe[df_leghe['Squadra'] == st.session_state.squadra]['Crediti'].values[0]
        max_rivale = df_leghe[df_leghe['Squadra'] != st.session_state.squadra]['Crediti'].max()

        st.title(f"🛡️ Terminale: {st.session_state.squadra}")
        
        # --- CRUSCOTTO FINANZIARIO ---
        with st.container():
            st.markdown("<div class='budget-box'>", unsafe_allow_html=True)
            c1, c2, c3 = st.columns(3)
            c1.metric("💰 Il tuo Budget", f"{crediti_totali} cr")
            c2.metric("🔝 Rivale più ricco", f"{max_rivale} cr")
            c3.info(f"Devi superare i **{max_rivale} cr** per rendere un giocatore inattaccabile.")
            st.markdown("</div>", unsafe_allow_html=True)

        # Logica Giocatori
        df_rosters = carica_csv("fantamanager-2021-rosters.csv")
        df_quot = carica_csv("quot.csv")
        df_rosters['Squadra_LFM'] = df_rosters['Squadra_LFM'].astype(str).str.strip()
        df_rosters['Id'] = df_rosters['Id'].astype(str).str.strip()
        df_quot['Id'] = df_quot['Id'].astype(str).str.strip()

        salvati = recupera_precedenti(st.session_state.squadra)
        ids_miei = df_rosters[df_rosters['Squadra_LFM'] == st.session_state.squadra]['Id'].tolist()
        miei_giocatori = df_quot[df_quot['Id'].isin(ids_miei)].copy()
        miei_giocatori['FVM'] = pd.to_numeric(miei_giocatori['FVM'], errors='coerce').fillna(0)
        top_3 = miei_giocatori.nlargest(3, 'FVM')

        tot_tasse = 0
        dati_invio = []

        for i, (_, row) in enumerate(top_3.iterrows()):
            nome, fvm = row['Nome'], int(row['FVM'])
            def_val = max(salvati.get(nome, fvm * 2), fvm)
            
            st.markdown(f"<h1 class='player-title'>{nome}</h1>", unsafe_allow_html=True)
            col1, col2, col3 = st.columns([2, 1, 1])
            with col1:
                val = st.number_input(f"Clausola", min_value=fvm, value=def_val, key=f"c_{nome}")
                st.progress(min(1.0, val / max_rivale) if max_rivale > 0 else 1.0)
            with col2:
                t = calcola_tassa(val)
                tot_tasse += t
                st.metric("Tassa", f"{t} cr")
            with col3:
                if val <= max_rivale: st.error("🟠 VULNERABILE")
                else: st.success("🟢 BLINDATO")
            dati_invio.append(f"{nome}:{val}")

        # --- CALCOLO FINALE E BUDGET RESIDUO ---
        st.write("---")
        eccedenza = max(0, tot_tasse - 60)
        budget_residuo = crediti_totali - eccedenza

        col_fin1, col_fin2 = st.columns([2, 1])
        with col_fin1:
            if tot_tasse <= 60:
                st.success("✅ Spesa coperta dal Bonus. Il tuo budget resta intatto.")
            else:
                st.warning(f"⚠️ Eccedi il bonus di {eccedenza} cr. Questa somma verrà scalata dal tuo budget.")
        
        with col_fin2:
            st.metric("Budget Rimanente", f"{budget_residuo} cr", delta=-eccedenza if eccedenza > 0 else 0)

        if st.button("📥 REGISTRA CLAUSOLE", type="primary", use_container_width=True):
            salva_su_github(st.session_state.squadra, ";".join(dati_invio))
            st.success("Salvataggio completato!")
            st.balloons()
