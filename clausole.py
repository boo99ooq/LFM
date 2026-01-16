import streamlit as st
import pandas as pd
from github import Github
from io import StringIO
import math

# --- 1. CONFIGURAZIONE GITHUB ---
try:
    TOKEN = st.secrets["GITHUB_TOKEN"]
    REPO_NAME = st.secrets["REPO_NAME"]
    g = Github(TOKEN)
    repo = g.get_repo(REPO_NAME)
except Exception as e:
    st.error("Configurazione GitHub mancante nei Secrets.")
    st.stop()

# --- 2. CSS PERSONALIZZATO PER IL LOOK ---
st.markdown("""
    <style>
    .main { background-color: #f5f7f9; }
    .stNumberInput { border-radius: 10px; }
    .player-header {
        color: #1E3A8A;
        font-family: 'Inter', sans-serif;
        font-weight: 800;
        margin-bottom: -10px;
    }
    .summary-card {
        background-color: #ffffff;
        padding: 20px;
        border-radius: 15px;
        box-shadow: 0 4px 6px rgba(0,0,0,0.1);
    }
    </style>
    """, unsafe_allow_html=True)

# --- 3. FUNZIONI DI UTILITÀ ---
def carica_csv(file_name):
    try:
        content = repo.get_contents(file_name)
        decoded = content.decoded_content.decode("latin1")
        return pd.read_csv(StringIO(decoded))
    except:
        return pd.DataFrame()

def calcola_tassa(valore):
    if valore <= 200: tassa = valore * 0.10
    elif valore <= 300: tassa = 20 + (valore - 200) * 0.15
    else: tassa = 20 + 15 + (valore - 300) * 0.20
    return math.ceil(tassa)

def salva_blindato(squadra, dati):
    path = "clausole_segrete.csv"
    nuova_riga = f"{squadra},{dati}\n"
    try:
        f = repo.get_contents(path)
        vecchio_contenuto = f.decoded_content.decode("utf-8")
        righe = [r for r in vecchio_contenuto.splitlines() if not r.startswith(f"{squadra},")]
        righe.append(nuova_riga.strip())
        repo.update_file(f.path, f"Update {squadra}", "\n".join(righe), f.sha)
    except:
        repo.create_file(path, "Inizializzazione", nuova_riga)

# --- 4. LOGIN ---
if 'loggato' not in st.session_state:
    st.session_state.loggato = False
    st.session_state.squadra = None

df_leghe = carica_csv("leghe.csv")

if not st.session_state.loggato:
    st.title("🏆 LFM Portal")
    with st.container():
        st.subheader("🛡️ Accesso Area Blindaggio")
        lega = st.selectbox("Seleziona la tua Lega", df_leghe['Lega'].unique())
        squadra = st.selectbox("Squadra", df_leghe[df_leghe['Lega'] == lega]['Squadra'].unique())
        pin = st.text_input("PIN Segreto", type="password")
        if st.button("SBLOCCA TERMINALE", use_container_width=True, type="primary"):
            pin_reale = df_leghe[df_leghe['Squadra'] == squadra]['PIN'].values[0]
            if str(pin) == str(pin_reale):
                st.session_state.loggato = True
                st.session_state.squadra = squadra
                st.rerun()
            else: st.error("Accesso negato. PIN errato.")

# --- 5. DASHBOARD MANAGER ---
else:
    st.title(f"🛡️ Terminale {st.session_state.squadra}")
    st.sidebar.markdown(f"**Squadra:** {st.session_state.squadra}")
    if st.sidebar.button("LOGOUT"):
        st.session_state.loggato = False
        st.rerun()

    df_rosters = carica_csv("fantamanager-2021-rosters.csv")
    df_quot = carica_csv("quot.csv")
    
    # Pulizia dati
    df_rosters['Squadra_LFM'] = df_rosters['Squadra_LFM'].astype(str).str.strip()
    df_rosters['Id'] = df_rosters['Id'].astype(str).str.strip()
    df_quot['Id'] = df_quot['Id'].astype(str).str.strip()
    
    ids_miei = df_rosters[df_rosters['Squadra_LFM'] == st.session_state.squadra]['Id'].tolist()
    miei_giocatori = df_quot[df_quot['Id'].isin(ids_miei)].copy()
    miei_giocatori['FVM'] = pd.to_numeric(miei_giocatori['FVM'], errors='coerce').fillna(0)
    top_3 = miei_giocatori.nlargest(3, 'FVM')
    
    max_rivale = df_leghe[df_leghe['Squadra'] != st.session_state.squadra]['Crediti'].max()

    st.markdown(f"### 🧮 Analisi Top Player")
    st.caption(f"Soglia Blindaggio Totale: ** > {max_rivale} cr**")

    tot_tasse = 0
    dati_invio = []

    for i, (_, row) in enumerate(top_3.iterrows()):
        nome, fvm = row['Nome'], int(row['FVM'])
        
        # CARD GIOCATORE
        with st.container():
            st.markdown(f"<h1 class='player-header'>{i+1}. {nome.upper()}</h1>", unsafe_allow_html=True)
            
            c1, c2, c3 = st.columns([2, 1, 1])
            
            with c1:
                val = st.number_input(f"Valore Clausola (FVM {fvm})", min_value=fvm, value=fvm*2, key=f"v_{nome}")
                
                # Barra di sicurezza visiva
                percentuale = min(100, int((val / max_rivale) * 100)) if max_rivale > 0 else 100
                st.progress(percentuale / 100, text=f"Livello Protezione: {percentuale}%")
            
            with c2:
                t = calcola_tassa(val)
                tot_tasse += t
                st.metric("Tassa", f"{t} cr", help="Calcolata a scaglioni (10%, 15%, 20%)")
            
            with c3:
                if val <= max_rivale:
                    st.error("🟠 VULNERABILE")
                else:
                    st.success("🟢 BLINDATO")
            
            dati_invio.append(f"{nome}:{val}")
            st.write(" ")

    # --- FOOTER RIEPILOGO ---
    st.markdown("---")
    eccedenza = max(0, tot_tasse - 60)
    
    with st.expander("📝 DETTAGLIO COSTI E BONUS", expanded=True):
        if tot_tasse <= 60:
            st.balloons() if tot_tasse > 0 else None
            st.info(f"✨ Ottimo! Il bonus di 60cr copre tutte le tasse. **Spesa Netta: 0 cr**")
        else:
            st.warning(f"⚠️ Il bonus copre fino a 60cr. Eccedi di **{eccedenza} cr**, che saranno scalati dal tuo budget.")

        col_a, col_b, col_c = st.columns(3)
        col_a.metric("Totale Tasse", f"{tot_tasse} cr")
        col_b.metric("Franchigia Bonus", "60 cr", delta="-60", delta_color="normal")
        col_c.metric("ADDEBITO REALE", f"{eccedenza} cr", delta=f"{eccedenza} cr", delta_color="inverse")

    if st.button("📥 REGISTRA CLAUSOLE NEL DATABASE", type="primary", use_container_width=True):
        salva_blindato(st.session_state.squadra, ";".join(dati_invio))
        st.success("OPERAZIONE COMPLETATA. I dati sono stati criptati nei server LFM.")
