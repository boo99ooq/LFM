import streamlit as st
import pandas as pd
from github import Github
from io import StringIO
import math
from datetime import datetime

# --- 1. CONFIGURAZIONE TEMPORALE ---
SCADENZA = datetime(2024, 8, 1)
OGGI = datetime.now()
PORTALE_APERTO = OGGI >= SCADENZA

try:
    TOKEN = st.secrets["GITHUB_TOKEN"]
    REPO_NAME = st.secrets["REPO_NAME"]
    g = Github(TOKEN)
    repo = g.get_repo(REPO_NAME)
except:
    st.error("Errore configurazione GitHub nei Secrets.")
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

# --- 3. UI E CSS PERSONALIZZATO (FOCUS SULLA CLAUSOLA) ---
st.set_page_config(page_title="LFM - Blindaggio", layout="wide")
st.markdown("""
    <style>
    .player-row {
        background-color: #ffffff;
        padding: 20px;
        border-radius: 15px;
        border: 1px solid #e0e0e0;
        margin-bottom: 25px;
    }
    .player-name {
        color: #1E3A8A;
        font-size: 2.5rem !important;
        font-weight: 900 !important;
        margin-bottom: 0px;
        text-transform: uppercase;
    }
    .fvm-text {
        color: #6B7280;
        font-size: 1.1rem;
        margin-bottom: 20px;
    }
    /* Rende l'input del numero enorme */
    .stNumberInput input {
        font-size: 2.2rem !important;
        font-weight: bold !important;
        color: #1E3A8A !important;
        height: 70px !important;
    }
    .stNumberInput label {
        font-size: 1.2rem !important;
        color: #1E3A8A !important;
        font-weight: bold !important;
    }
    </style>
    """, unsafe_allow_html=True)

# --- 4. LOGICA VISUALIZZAZIONE ---
if PORTALE_APERTO:
    st.title("🔓 LFM - Tabellone Pubblico")
    # (Logica tabellone...)
else:
    if 'loggato' not in st.session_state:
        st.session_state.loggato = False
        st.session_state.squadra = None

    df_leghe = carica_csv("leghe.csv")

    if not st.session_state.loggato:
        st.title("🛡️ LFM - Portale Blindaggio")
        if not df_leghe.empty:
            lega = st.selectbox("Seleziona Lega", df_leghe['Lega'].unique())
            squadra = st.selectbox("Squadra", df_leghe[df_leghe['Lega'] == lega]['Squadra'].unique())
            pin = st.text_input("PIN Segreto", type="password")
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
            # (Funzione monitoraggio admin...)
            pass

        crediti_totali = df_leghe[df_leghe['Squadra'] == st.session_state.squadra]['Crediti'].values[0]
        max_rivale = df_leghe[df_leghe['Squadra'] != st.session_state.squadra]['Crediti'].max()

        st.title(f"🛡️ Terminale: {st.session_state.squadra}")
        
        # Dashboard Crediti
        c1, c2, c3 = st.columns(3)
        c1.metric("💰 Budget", f"{crediti_totali} cr")
        c2.metric("🔝 Max Rivali", f"{max_rivale} cr")
        c3.info(f"Soglia Blindaggio: > {max_rivale}")

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

        st.write("---")

        for i, (_, row) in enumerate(top_3.iterrows()):
            nome, fvm = row['Nome'], int(row['FVM'])
            def_val = max(salvati.get(nome, fvm * 2), fvm)
            
            # BLOCCO GIOCATORE
            st.markdown(f"<div class='player-name'>{nome}</div>", unsafe_allow_html=True)
            st.markdown(f"<div class='fvm-text'>Valore di Mercato (FVM): {fvm} cr</div>", unsafe_allow_html=True)
            
            col_main, col_stats = st.columns([2, 1.5])
            
            with col_main:
                # INPUT GIGANTE
                val = st.number_input(f"IMPOSTA VALORE CLAUSOLA", min_value=fvm, value=def_val, key=f"c_{nome}")
                st.progress(min(1.0, val / max_rivale) if max_rivale > 0 else 1.0)
            
            with col_stats:
                st.write("") # Spazio per allineare
                st.write("")
                t = calcola_tassa(val)
                tot_tasse += t
                
                c_t, c_s = st.columns(2)
                c_t.metric("Tassa", f"{t} cr")
                if val <= max_rivale: c_s.error("VULNERABILE")
                else: c_s.success("BLINDATO")
            
            st.markdown("<br>", unsafe_allow_html=True)
            dati_invio.append(f"{nome}:{val}")

        # --- RIEPILOGO ---
        st.write("---")
        eccedenza = max(0, tot_tasse - 60)
        budget_residuo = crediti_totali - eccedenza

        if tot_tasse <= 60:
            st.success(f"✅ Il Bonus Lega di 60cr copre interamente le tue tasse ({tot_tasse} cr). Il tuo budget resta intatto.")
        else:
            st.warning(f"⚠️ Il Bonus Lega copre le tue tasse fino a 60cr. Eccedi il bonus di **{eccedenza} crediti** (Tasse totali: {tot_tasse} cr), che verranno scalati dal tuo budget.")

        c_fin1, c_fin2, c_fin3 = st.columns(3)
        c_fin1.metric("Totale Tasse", f"{tot_tasse} cr")
        c_fin2.metric("Franchigia", "- 60 cr")
        c_fin3.metric("Budget Rimanente", f"{budget_residuo} cr", delta=-eccedenza if eccedenza > 0 else 0)

        if st.button("📥 REGISTRA CLAUSOLE DEFINITIVAMENTE", type="primary", use_container_width=True):
            salva_su_github(st.session_state.squadra, ";".join(dati_invio))
            st.success("✅ Salvataggio completato!")
            st.balloons()
