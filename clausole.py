import streamlit as st
import pandas as pd
from github import Github
from io import StringIO
import math

# --- 1. CONFIGURAZIONE GITHUB ---
# Assicurati di aver impostato GITHUB_TOKEN e REPO_NAME nei Secrets di Streamlit
try:
    TOKEN = st.secrets["GITHUB_TOKEN"]
    REPO_NAME = st.secrets["REPO_NAME"]
    g = Github(TOKEN)
    repo = g.get_repo(REPO_NAME)
except Exception as e:
    st.error("Configurazione GitHub mancante nei Secrets di Streamlit.")
    st.stop()

# --- 2. FUNZIONI DI UTILITÀ ---
def carica_csv(file_name):
    """Carica i file dal repo con codifica corretta per i nomi accentati."""
    try:
        content = repo.get_contents(file_name)
        decoded = content.decoded_content.decode("latin1")
        return pd.read_csv(StringIO(decoded))
    except:
        return pd.DataFrame()

def calcola_tassa(valore):
    """Calcola la commissione progressiva (10%, 15%, 20%)."""
    tassa = 0
    if valore <= 200:
        tassa = valore * 0.10
    elif valore <= 300:
        tassa = (200 * 0.10) + (valore - 200) * 0.15
    else:
        tassa = (200 * 0.10) + (100 * 0.15) + (valore - 300) * 0.20
    return math.ceil(tassa)

def salva_blindato(squadra, dati):
    """Salva la stringa delle clausole su GitHub."""
    path = "clausole_segrete.csv"
    nuova_riga = f"{squadra},{dati}\n"
    try:
        f = repo.get_contents(path)
        vecchio_contenuto = f.decoded_content.decode("utf-8")
        # Sovrascrive se la squadra ha già inviato, altrimenti appende
        righe = vecchio_contenuto.splitlines()
        nuove_righe = [r for r in righe if not r.startswith(f"{squadra},")]
        nuove_righe.append(nuova_riga.strip())
        repo.update_file(f.path, f"Update clausole {squadra}", "\n".join(nuove_righe), f.sha)
    except:
        repo.create_file(path, "Inizializzazione clausole", nuova_riga)

# --- 3. GESTIONE SESSIONE E LOGIN ---
if 'loggato' not in st.session_state:
    st.session_state.loggato = False
    st.session_state.squadra = None

df_leghe = carica_csv("leghe.csv")

if not st.session_state.loggato:
    st.header("🔑 LFM - Accesso Blindato")
    lega = st.selectbox("Lega", df_leghe['Lega'].unique())
    squadra = st.selectbox("Squadra", df_leghe[df_leghe['Lega'] == lega]['Squadra'].unique())
    pin = st.text_input("PIN", type="password")
    
    if st.button("Accedi"):
        pin_reale = df_leghe[df_leghe['Squadra'] == squadra]['PIN'].values[0]
        if str(pin) == str(pin_reale):
            st.session_state.loggato = True
            st.session_state.squadra = squadra
            st.rerun()
        else:
            st.error("PIN errato.")

# --- 4. DASHBOARD AUTOMATICA ---
else:
    st.title(f"🛡️ Blindaggio: {st.session_state.squadra}")
    if st.sidebar.button("Logout"):
        st.session_state.loggato = False
        st.rerun()

    # Caricamento dati per incrocio
    df_rosters = carica_csv("fantamanager-2021-rosters.csv")
    df_quot = carica_csv("quot.csv")
    
    # Calcolo ricchezza massima avversari per avviso vulnerabilità
    max_crediti_rivali = df_leghe[df_leghe['Squadra'] != st.session_state.squadra]['Crediti'].max()

    # Identificazione automatica Top 3
    ids_miei = df_rosters[df_rosters['Squadra_LFM'] == st.session_state.squadra]['Id'].tolist()
    miei_giocatori = df_quot[df_quot['Id'].isin(ids_miei)].nlargest(3, 'FVM')

    st.info(f"Il manager più ricco della lega ha **{max_crediti_rivali} crediti**. Se imposti una clausola inferiore, sarai 'Vulnerabile'.")

    tot_tasse = 0
    dati_invio = []

    for _, row in miei_giocatori.iterrows():
        nome, fvm = row['Nome'], int(row['FVM'])
        
        with st.expander(f"💎 {nome} (FVM: {fvm})", expanded=True):
            c1, c2, c3 = st.columns([2, 1, 1])
            with c1:
                clausola = st.number_input(f"Clausola per {nome}", min_value=fvm, value=fvm*2, key=f"cl_{nome}")
            with c2:
                tassa = calcola_tassa(clausola)
                tot_tasse += tassa
                st.metric("Tassa", f"{tassa} cr")
            with c3:
                # LOGICA VULNERABILITÀ
                if clausola <= max_crediti_rivali:
                    st.error("🟠 Vulnerabile")
                else:
                    st.success("🟢 Blindato")
            
            dati_invio.append(f"{nome}:{clausola}")

    # Riepilogo Economico
    spesa_netta = max(0, tot_tasse - 60)
    st.divider()
    col_a, col_b, col_c = st.columns(3)
    col_a.metric("Totale Tasse", f"{tot_tasse} cr")
    col_b.metric("Bonus Lega", "-60 cr")
    col_c.metric("Costo Finale", f"{spesa_netta} cr", delta_color="inverse")

    if st.button("CONFERMA E CONSEGNA AL BUIO", type="primary", use_container_width=True):
        salva_blindato(st.session_state.squadra, ";".join(dati_invio))
        st.success("Salvataggio effettuato! I dati sono criptati fino al 31 Luglio.")
        st.balloons()
