import streamlit as st
import pandas as pd

st.set_page_config(page_title="LFM Admin Draft Panel", layout="wide")

# --- FUNZIONI DI CARICAMENTO ---
def read_csv_safe(file_name, delimiter=','):
    try:
        return pd.read_csv(file_name, encoding='utf-8', sep=delimiter)
    except:
        return pd.read_csv(file_name, encoding='ISO-8859-1', sep=delimiter)

# --- INIZIALIZZAZIONE SESSIONE (DATABASE TEMPORANEO) ---
if 'draft_log' not in st.session_state:
    st.session_state.draft_log = []
if 'updated_rosters' not in st.session_state:
    st.session_state.updated_rosters = None

def load_initial_data():
    rosters = read_csv_safe('fantamanager-2021-rosters.csv')
    leghe = read_csv_safe('leghe.csv')
    quot = read_csv_safe('quot.csv')
    esclusi = read_csv_safe('esclusi.csv', delimiter='\t')
    
    if len(esclusi.columns) >= 5:
        esclusi.columns = ['Id', 'R', 'Nome', 'Qt.I', 'FVM']
    
    for df in [rosters, quot, esclusi]:
        df['Id'] = pd.to_numeric(df['Id'], errors='coerce')
        if 'FVM' in df.columns:
            df['FVM'] = pd.to_numeric(df['FVM'], errors='coerce').fillna(0)
        df.dropna(subset=['Id'], inplace=True)
        df['Id'] = df['Id'].astype(int)
    
    return rosters, leghe, quot, esclusi

# Carichiamo i dati solo all'inizio
if st.session_state.updated_rosters is None:
    r, l, q, e = load_initial_data()
    st.session_state.updated_rosters = r
    st.session_state.leghe = l
    st.session_state.quot = q
    st.session_state.esclusi = e

# Alias per comodità
df_rosters = st.session_state.updated_rosters
df_quot = st.session_state.quot
df_esclusi = st.session_state.esclusi

# --- INTERFACCIA ---
st.title("⚙️ Pannello Admin Draft")

campionato = st.sidebar.selectbox("Campionato Attivo", ['Serie A', 'Premier League', 'Liga BBVA', 'Bundesliga'])

# Logica di calcolo Asteriscati e Svincolati
df_full = pd.merge(df_rosters, st.session_state.leghe, left_on='Squadra_LFM', right_on='Squadra')
df_lega = df_full[df_full['Lega'] == campionato]
ids_esclusi = set(df_esclusi['Id'])
asteriscati_base = df_lega[df_lega['Id'].isin(ids_esclusi)]
asteriscati = pd.merge(asteriscati_base, df_esclusi[['Id', 'Nome', 'R', 'FVM']], on='Id', how='left')

# Escludiamo chi è già stato draftato in questa sessione o è in altre rose
ids_occupati_lega = set(df_lega['Id'])
svincolati = df_quot[(~df_quot['Id'].isin(ids_occupati_lega)) & (~df_quot['Id'].isin(ids_esclusi))]

# --- SESSIONE DRAFT PER RUOLO ---
ordine_ruoli = ['P', 'D', 'C', 'A']
tabs = st.tabs(["Portieri", "Difensori", "Centrocampisti", "Attaccanti", "📜 REGISTRO DRAFT"])

for i, r_code in enumerate(ordine_ruoli):
    with tabs[i]:
        lista_ruolo = asteriscati[asteriscati['R'] == r_code].sort_values(by='FVM', ascending=False)
        
        if lista_ruolo.empty:
            st.info("Nessuna pendenza per questo ruolo.")
        else:
            for _, row in lista_ruolo.iterrows():
                # Verifichiamo se il manager ha già saltato o scelto per questo giocatore specifico
                if any(d['Id_Perso'] == row['Id'] for d in st.session_state.draft_log):
                    continue

                with st.expander(f"📢 Turno di: {row['Squadra_LFM']} (Sostituisce {row['Nome']})"):
                    col1, col2 = st.columns([1, 2])
                    
                    with col1:
                        st.write(f"**Perso:** {row['Nome']} (FVM: {row['FVM']})")
                        if st.button(f"Passa / Salta Turno", key=f"skip_{row['Id']}"):
                            st.session_state.draft_log.append({
                                "Squadra": row['Squadra_LFM'], "Perso": row['Nome'], "Id_Perso": row['Id'],
                                "Preso": "SALTATO", "FVM": 0, "Tipo": "SKIP"
                            })
                            st.rerun()

                    with col2:
                        # Filtro svincolati
                        options = svincolati[(svincolati['R'] == r_code) & (svincolati['FVM'] <= row['FVM'])]
                        scelta = st.selectbox(f"Scegli sostituto per {row['Squadra_LFM']}:", 
                                            options['Nome'].tolist(), key=f"sel_{row['Id']}")
                        
                        if st.button(f"Conferma Acquisto", key=f"btn_{row['Id']}"):
                            player_data = options[options['Nome'] == scelta].iloc[0]
                            # AGGIORNAMENTO ROSA: sostituiamo l'ID nel dataframe principale
                            st.session_state.updated_rosters.loc[st.session_state.updated_rosters['Id'] == row['Id'], 'Id'] = player_data['Id']
                            
                            st.session_state.draft_log.append({
                                "Squadra": row['Squadra_LFM'], "Perso": row['Nome'], "Id_Perso": row['Id'],
                                "Preso": player_data['Nome'], "FVM": player_data['FVM'], "Tipo": "ACQUISTO"
                            })
                            st.success(f"Registrato: {player_data['Nome']} al {row['Squadra_LFM']}")
                            st.rerun()

# --- TAB REGISTRO ---
with tabs[4]:
    st.subheader("Storico Movimenti Draft")
    if st.session_state.draft_log:
        df_log = pd.DataFrame(st.session_state.draft_log)
        st.table(df_log)
        
        # Bottone per esportare in Excel (opzionale)
        csv = df_log.to_csv(index=False).encode('utf-8')
        st.download_button("Scarica Registro CSV", csv, "registro_draft.csv", "text/csv")
    else:
        st.write("Nessun movimento registrato.")
