import streamlit as st
import pandas as pd
from github import Github
import math

# --- FUNZIONI TECNICHE ---
def calcola_commissione(valore):
    """Calcola la tassa a scaglioni: 10% fino a 200, 15% fino a 300, 20% oltre."""
    tassa = 0
    if valore <= 200:
        tassa = valore * 0.10
    elif valore <= 300:
        tassa = (200 * 0.10) + (valore - 200) * 0.15
    else:
        tassa = (200 * 0.10) + (100 * 0.15) + (valore - 300) * 0.20
    return math.ceil(tassa)

# --- CARICAMENTO DATI (Simulato dai tuoi CSV) ---
# In produzione useremo la funzione carica_csv_da_github() definita prima
# Prova prima con latin1, che risolve il 90% dei casi con nomi accentati
df_quot = pd.read_csv("quot.csv", encoding='latin1')

# Se hai lo stesso errore anche sugli altri file, aggiungilo anche lì:
df_leghe = pd.read_csv("leghe.csv", encoding='latin1')
df_rosters = pd.read_csv("fantamanager-2021-rosters.csv", encoding='latin1')

st.title("🛡️ LFM - Gestione Blindaggio Top Player")

# --- LOGIN STEP 1: SCELTA LEGA E SQUADRA ---
col1, col2 = st.columns(2)
with col1:
    lega_scelta = st.selectbox("Seleziona la tua Lega", df_leghe['Lega'].unique())
with col2:
    squadre_filtrate = df_leghe[df_leghe['Lega'] == lega_scelta]['Squadra'].unique()
    squadra_scelta = st.selectbox("Seleziona la tua Squadra", squadre_filtrate)

pin = st.text_input("Inserisci PIN Squadra", type="password")

if pin == "1234": # Esempio di PIN
    st.success(f"Accesso autorizzato: {squadra_scelta}")
    
    # --- LOGICA INCROCIO FILE ---
    # 1. Trovo gli ID dei giocatori della squadra dal roster
    ids_squadra = df_rosters[df_rosters['Squadra_LFM'] == squadra_scelta]['Id'].tolist()
    
    # 2. Prendo i dettagli di questi giocatori da quot.csv
    giocatori_squadra = df_quot[df_quot['Id'].isin(ids_squadra)].copy()
    
    # 3. Identifico i 3 Top Player per FVM (come da regolamento)
    top_3_default = giocatori_squadra.nlargest(3, 'FVM')
    
    st.subheader("I tuoi 3 Top Player (per FVM)")
    st.write("Puoi confermare questi o sceglierne altri tra i tuoi migliori 10.")

    scelti = st.multiselect("Seleziona i 3 da blindare:", 
                            giocatori_squadra.nlargest(10, 'FVM')['Nome'].tolist(), 
                            default=top_3_default['Nome'].tolist(),
                            max_selections=3)

    if len(scelti) == 3:
        totale_commissioni = 0
        clausole_finali = {}

        for nome in scelti:
            fvm_player = giocatori_squadra[giocatori_squadra['Nome'] == nome]['FVM'].values[0]
            clausola = st.number_input(f"Clausola per {nome} (FVM: {fvm_player})", 
                                       min_value=int(fvm_player), 
                                       value=int(fvm_player * 2))
            
            tassa = calcola_commissione(clausola)
            totale_commissioni += tassa
            clausole_finali[nome] = clausola
            st.caption(f"Costo blindaggio per {nome}: {tassa} cr")

        # --- CALCOLO BONUS 60 ---
        spesa_reale = max(0, totale_commissioni - 60)
        
        st.divider()
        st.metric("Totale Tasse Blindaggio", f"{totale_commissioni} cr")
        st.metric("Costo netto su Budget Asta (Bonus 60cr applicato)", f"{spesa_reale} cr")

        if st.button("Consegna e Cripta su GitHub"):
            # Qui inseriremo la funzione save_to_github() con il tuo TOKEN
            st.warning("Salvataggio in corso nel database segreto...")
            # save_to_github(...)
            st.balloons()
