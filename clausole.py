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
        # Usiamo latin1 per evitare errori con nomi tipo Montipò
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

# --- 4. DASHBOARD ---
else:
    st.title(f"🛡️ Blindaggio: {st.session_state.squadra}")
    if st.sidebar.button("Logout"):
        st.session_state.loggato = False
        st.rerun()

    df_rosters = carica_csv("fantamanager-2021-rosters.csv")
    df_quot = carica_csv("quot.csv")
    
    # --- LOGICA DI FILTRAGGIO ROBUSTA ---
    # Cerchiamo gli ID associati alla squadra nel roster
    # Usiamo str().strip() per evitare errori dovuti a spazi vuoti invisibili
    ids_miei = df_rosters[df_rosters['Squadra_LFM'].astype(str).str.strip() == st.session_state.squadra.strip()]['Id'].tolist()

    if not ids_miei:
        st.warning(f"Attenzione: Non ho trovato giocatori per '{st.session_state.squadra}' nel file roster.")
        # Debug per l'admin: mostra i nomi delle squadre presenti nel roster
        if st.checkbox("Mostra nomi squadre nel roster (Debug)"):
            st.write(df_rosters['Squadra_LFM'].unique())
    else:
        # Recupero dati reali da quot.csv
        miei_giocatori = df_quot[df_quot['Id'].isin(ids_miei)].nlargest(3, 'FVM')
        
        max_crediti_rivali = df_leghe[df_leghe['Squadra'] != st.session_state.squadra]['Crediti'].max()
        st.info(f"Ricchezza massima avversaria: **{max_crediti_rivali} cr**")

        tot_tasse = 0
        dati_invio = []

        for _, row in miei_giocatori.iterrows():
            nome, fvm = row['Nome'], int(row['FVM'])
            with st.expander(f"💎 {nome} (FVM: {fvm})", expanded=True):
                c1, c2, c3 = st.columns([2, 1, 1])
                with c1:
                    clausola = st.number_input(f"Clausola", min_value=fvm, value=fvm*2, key=f"cl_{nome}")
                with c2:
                    tassa = calcola_tassa(clausola)
                    tot_tasse += tassa
                    st.metric("Tassa", f"{tassa} cr")
                with c3:
                    if clausola <= max_crediti_rivali: st.error("🟠 Vulnerabile")
                    else: st.success("🟢 Blindato")
                dati_invio.append(f"{nome}:{clausola}")

        spesa_netta = max(0, tot_tasse - 60)
        st.divider()
        col_a, col_b, col_c = st.columns(3)
        col_a.metric("Totale Tasse", f"{tot_tasse} cr")
        col_b.metric("Bonus", "-60 cr")
        col_c.metric("Costo Finale", f"{spesa_netta} cr")

        if st.button("CONFERMA E SALVA", type="primary", use_container_width=True):
            salva_blindato(st.session_state.squadra, ";".join(dati_invio))
            st.success("✅ Salvataggio completato!")
            st.balloons()
