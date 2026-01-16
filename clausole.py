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

# --- 2. FUNZIONI DI UTILITÀ ---
def carica_csv(file_name):
    try:
        content = repo.get_contents(file_name)
        decoded = content.decoded_content.decode("latin1")
        return pd.read_csv(StringIO(decoded))
    except Exception as e:
        st.error(f"Errore caricamento {file_name}: {e}")
        return pd.DataFrame()

def calcola_tassa(valore):
    tassa = 0
    if valore <= 200: tassa = valore * 0.10
    elif valore <= 300: tassa = 20 + (valore - 200) * 0.15
    else: tassa = 20 + 15 + (valore - 300) * 0.20
    return math.ceil(tassa)

# --- 3. LOGIN ---
if 'loggato' not in st.session_state:
    st.session_state.loggato = False
    st.session_state.squadra = None

df_leghe = carica_csv("leghe.csv")

if not st.session_state.loggato:
    st.header("🔑 Accesso Blindato")
    if not df_leghe.empty:
        lega = st.selectbox("Lega", df_leghe['Lega'].unique())
        squadra = st.selectbox("Squadra", df_leghe[df_leghe['Lega'] == lega]['Squadra'].unique())
        pin = st.text_input("PIN", type="password")
        if st.button("Accedi"):
            pin_reale = df_leghe[df_leghe['Squadra'] == squadra]['PIN'].values[0]
            if str(pin) == str(pin_reale):
                st.session_state.loggato = True
                st.session_state.squadra = squadra
                st.rerun()
            else: st.error("PIN errato.")

# --- LOGICA DASHBOARD AGGIORNATA CON MESSAGGIO CORRETTO ---
else:
    st.title(f"🛡️ Blindaggio: {st.session_state.squadra}")
    if st.sidebar.button("Logout"):
        st.session_state.loggato = False
        st.rerun()

    df_rosters = carica_csv("fantamanager-2021-rosters.csv")
    df_quot = carica_csv("quot.csv")
    
    # Pulizia ID e Nomi
    df_rosters['Squadra_LFM'] = df_rosters['Squadra_LFM'].astype(str).str.strip()
    df_rosters['Id'] = df_rosters['Id'].astype(str).str.strip()
    df_quot['Id'] = df_quot['Id'].astype(str).str.strip()
    
    ids_miei = df_rosters[df_rosters['Squadra_LFM'] == st.session_state.squadra.strip()]['Id'].tolist()

    if not ids_miei:
        st.warning(f"Nessun giocatore trovato per {st.session_state.squadra}")
    else:
        miei_giocatori = df_quot[df_quot['Id'].isin(ids_miei)].copy()
        miei_giocatori['FVM'] = pd.to_numeric(miei_giocatori['FVM'], errors='coerce').fillna(0)
        top_3 = miei_giocatori.nlargest(3, 'FVM')

        max_crediti_rivali = df_leghe[df_leghe['Squadra'] != st.session_state.squadra]['Crediti'].max()
        
        st.write("---")
        tot_tasse = 0
        dati_invio = []

        # CICLO PER I 3 GIOCATORI
        for i, (_, row) in enumerate(top_3.iterrows()):
            nome, fvm = row['Nome'], int(row['FVM'])
            
            # NOME GIGANTE E VISIBILE
            st.markdown(f"# {nome.upper()}")
            
            col1, col2, col3 = st.columns([2, 1, 1])
            
            with col1:
                clausola = st.number_input(f"Clausola (FVM: {fvm})", 
                                           min_value=fvm, 
                                           value=fvm*2, 
                                           key=f"cl_{nome}")
            with col2:
                tassa = calcola_tassa(clausola)
                tot_tasse += tassa
                st.metric("Tassa", f"{tassa} cr")
            
            with col3:
                if clausola <= max_crediti_rivali:
                    st.error("🟠 VULNERABILE")
                else:
                    st.success("🟢 BLINDATO")
            
            st.write("---")
            dati_invio.append(f"{nome}:{clausola}")

        # --- LOGICA MESSAGGIO BONUS (VERSIONE CORRETTA) ---
        eccedenza = max(0, tot_tasse - 60)
        
        if tot_tasse <= 60:
            st.success(f"✅ Il Bonus Lega copre interamente le tue tasse ({tot_tasse} cr). Spesa netta: 0 cr.")
        else:
            st.warning(f"⚠️ Il Bonus Lega copre le tue tasse fino a 60 cr. Eccedi il bonus di **{eccedenza} crediti**, che verranno scalati dal tuo budget asta.")

        # Riepilogo finale
        c1, c2, c3 = st.columns(3)
        c1.metric("Totale Tasse", f"{tot_tasse} cr")
        c2.metric("Bonus franchigia", "60 cr")
        c3.metric("SPESA REALE", f"{eccedenza} cr", delta=-eccedenza if eccedenza > 0 else 0)

        if st.button("SALVA DEFINITIVAMENTE", type="primary", use_container_width=True):
            salva_blindato(st.session_state.squadra, ";".join(dati_invio))
            st.success("✅ Salvataggio completato!")
            st.balloons()
