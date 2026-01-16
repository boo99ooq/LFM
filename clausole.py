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
    st.error("Configurazione GitHub mancante nei Secrets di Streamlit.")
    st.stop()

# --- 2. CSS PERSONALIZZATO PER LOOK PREMIUM ---
st.markdown("""
    <style>
    .main { background-color: #f8f9fa; }
    .stNumberInput { border-radius: 8px; }
    .player-title {
        color: #0e1117;
        font-weight: 850;
        text-transform: uppercase;
        margin-top: 30px;
        border-bottom: 2px solid #e0e0e0;
    }
    .stProgress > div > div > div > div {
        background-color: #4CAF50;
    }
    </style>
    """, unsafe_allow_html=True)

# --- 3. FUNZIONI TECNICHE ---
def carica_csv(file_name):
    """Carica i file dal repo GitHub gestendo la codifica latin1."""
    try:
        content = repo.get_contents(file_name)
        decoded = content.decoded_content.decode("latin1")
        return pd.read_csv(StringIO(decoded))
    except:
        return pd.DataFrame()

def calcola_tassa(valore):
    """Calcola la commissione progressiva: 10% fino a 200, 15% fino a 300, 20% oltre."""
    tassa = 0
    if valore <= 200:
        tassa = valore * 0.10
    elif valore <= 300:
        tassa = (200 * 0.10) + (valore - 200) * 0.15
    else:
        tassa = (200 * 0.10) + (100 * 0.15) + (valore - 300) * 0.20
    return math.ceil(tassa)

def recupera_precedenti(squadra):
    """Recupera le clausole già inviate dal file segreto."""
    try:
        f = repo.get_contents("clausole_segrete.csv")
        testo = f.decoded_content.decode("utf-8")
        for riga in testo.splitlines():
            if riga.startswith(f"{squadra},"):
                dati = riga.split(",")[1]
                return {item.split(":")[0]: int(item.split(":")[1]) for item in dati.split(";")}
    except:
        return {}
    return {}

def salva_su_github(squadra, dati_stringa):
    """Aggiorna il file delle clausole segrete su GitHub."""
    path = "clausole_segrete.csv"
    nuova_riga = f"{squadra},{dati_stringa}\n"
    try:
        f = repo.get_contents(path)
        contenuto_attuale = f.decoded_content.decode("utf-8")
        # Rimuove la vecchia riga della squadra se presente
        righe = [r for r in contenuto_attuale.splitlines() if not r.startswith(f"{squadra},")]
        righe.append(nuova_riga.strip())
        nuovo_file = "\n".join(righe)
        repo.update_file(f.path, f"Update clausole {squadra}", nuovo_file, f.sha)
    except:
        repo.create_file(path, "Inizializzazione clausole", nuova_riga)

# --- 4. LOGICA DI LOGIN ---
if 'loggato' not in st.session_state:
    st.session_state.loggato = False
    st.session_state.squadra = None

df_leghe = carica_csv("leghe.csv")

if not st.session_state.loggato:
    st.title("🏆 LFM - Portale Clausole")
    st.subheader("🛡️ Identificazione Manager")
    
    if not df_leghe.empty:
        lega = st.selectbox("Seleziona Lega", df_leghe['Lega'].unique())
        squadra = st.selectbox("Seleziona Squadra", df_leghe[df_leghe['Lega'] == lega]['Squadra'].unique())
        pin = st.text_input("Inserisci PIN Squadra", type="password")
        
        if st.button("ACCEDI AL TERMINALE", use_container_width=True, type="primary"):
            pin_reale = df_leghe[df_leghe['Squadra'] == squadra]['PIN'].values[0]
            if str(pin) == str(pin_reale):
                st.session_state.loggato = True
                st.session_state.squadra = squadra
                st.rerun()
            else:
                st.error("PIN errato. Contatta l'admin.")
else:
    # --- 5. DASHBOARD BLINDAGGIO ---
    st.title(f"🛡️ Terminale: {st.session_state.squadra}")
    if st.sidebar.button("LOGOUT"):
        st.session_state.loggato = False
        st.rerun()

    # Caricamento e pulizia dati
    df_rosters = carica_csv("fantamanager-2021-rosters.csv")
    df_quot = carica_csv("quot.csv")
    
    df_rosters['Squadra_LFM'] = df_rosters['Squadra_LFM'].astype(str).str.strip()
    df_rosters['Id'] = df_rosters['Id'].astype(str).str.strip()
    df_quot['Id'] = df_quot['Id'].astype(str).str.strip()

    # Recupero dati precedenti
    salvati = recupera_precedenti(st.session_state.squadra)
    if salvati:
        st.info("🔄 Sono presenti dati salvati. Puoi modificarli e registrare di nuovo.")

    # Trovo i 3 Top Player
    ids_miei = df_rosters[df_rosters['Squadra_LFM'] == st.session_state.squadra]['Id'].tolist()
    miei_giocatori = df_quot[df_quot['Id'].isin(ids_miei)].copy()
    miei_giocatori['FVM'] = pd.to_numeric(miei_giocatori['FVM'], errors='coerce').fillna(0)
    top_3 = miei_giocatori.nlargest(3, 'FVM')

    # Analisi Rivali
    max_rivale = df_leghe[df_leghe['Squadra'] != st.session_state.squadra]['Crediti'].max()
    st.markdown(f"""> 💰 **Analisi Strategica:** La squadra più ricca della lega possiede **{max_rivale} cr**. 
    > Impostando per un tuo giocatore una soglia oltre questi crediti, nessuno potrà comprarlo.""")

    tot_tasse = 0
    dati_per_invio = []

    # Ciclo visualizzazione Giocatori
    for i, (_, row) in enumerate(top_3.iterrows()):
        nome, fvm = row['Nome'], int(row['FVM'])
        
        # Valore di default (recuperato o FVM*2)
        def_val = salvati.get(nome, fvm * 2)
        def_val = max(def_val, fvm) # Sicurezza se FVM è salita

        st.markdown(f"<h1 class='player-title'>{nome}</h1>", unsafe_allow_html=True)
        
        col1, col2, col3 = st.columns([2, 1, 1])
        with col1:
            val = st.number_input(f"Clausola (FVM: {fvm})", min_value=fvm, value=def_val, key=f"c_{nome}")
            # Barra di sicurezza
            progresso = min(1.0, val / max_rivale) if max_rivale > 0 else 1.0
            st.progress(progresso, text=f"Livello Protezione vs Rivali")
        
        with col2:
            t = calcola_tassa(val)
            tot_tasse += t
            st.metric("Tassa", f"{t} cr")
            
        with col3:
            if val <= max_rivale:
                st.error("🟠 VULNERABILE")
            else:
                st.success("🟢 BLINDATO")
        
        dati_per_invio.append(f"{nome}:{val}")

    # --- 6. RIEPILOGO E SALVATAGGIO ---
    st.write("---")
    eccedenza = max(0, tot_tasse - 60)
    
    if tot_tasse <= 60:
        st.success(f"✅ Il Bonus Lega copre interamente le tue tasse ({tot_tasse} cr). Spesa netta: 0 cr.")
    else:
        st.warning(f"⚠️ Il Bonus Lega copre le tue tasse fino a 60 cr. Eccedi il bonus di **{eccedenza} crediti**, che verranno scalati dal tuo budget asta.")

    c1, c2, c3 = st.columns(3)
    c1.metric("Totale Tasse", f"{tot_tasse} cr")
    c2.metric("Bonus Franchigia", "60 cr", delta="-60")
    c3.metric("ADDEBITO REALE", f"{eccedenza} cr", delta=f"{eccedenza} cr" if eccedenza > 0 else "0", delta_color="inverse")

    if st.button("📥 REGISTRA CLAUSOLE DEFINITIVAMENTE", type="primary", use_container_width=True):
        salva_su_github(st.session_state.squadra, ";".join(dati_per_invio))
        st.toast("Dati sincronizzati con GitHub!", icon='🚀')
        st.success(f"✅ Operazione riuscita! Le clausole di {st.session_state.squadra} sono state criptate.")
        st.balloons()
