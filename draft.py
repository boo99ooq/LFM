import streamlit as st
import pandas as pd

st.set_page_config(page_title="LFM Draft - Dashboard Ufficiale", layout="wide")

# --- LISTA ADMIN AUTORIZZATI ---
ADMIN_SQUADRE = ["Liverpool Football Club", "Villarreal", "Reggina Calcio 1914", "Siviglia"]

# --- FUNZIONI DI CARICAMENTO ---
def read_csv_safe(file_name, delimiter=','):
    try:
        return pd.read_csv(file_name, encoding='utf-8', sep=delimiter)
    except:
        return pd.read_csv(file_name, encoding='ISO-8859-1', sep=delimiter)

def load_data():
    try:
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
    except Exception as e:
        st.error(f"Errore caricamento: {e}")
        return None, None, None, None

# --- STATO DELLA SESSIONE ---
if 'draft_log' not in st.session_state:
    st.session_state.draft_log = []
if 'df_rosters' not in st.session_state:
    r, l, q, e = load_data()
    st.session_state.df_rosters = r
    st.session_state.leghe = l
    st.session_state.quot = q
    st.session_state.esclusi = e

# --- SIDEBAR & LOGIN ---
st.sidebar.title("🛡️ Accesso Draft")
campionato = st.sidebar.selectbox("Seleziona Lega", ['Serie A', 'Premier League', 'Liga BBVA', 'Bundesliga'])

st.sidebar.divider()
st.sidebar.subheader("Area Riservata Admin")
admin_selezionato = st.sidebar.selectbox("Seleziona Squadra Admin", ["---"] + ADMIN_SQUADRE)
input_pin = st.sidebar.text_input("Inserisci PIN per sbloccare", type="password")

# Verifica credenziali
is_admin = False
if admin_selezionato != "---":
    # Cerchiamo il PIN nel file leghe.csv
    squadra_info = st.session_state.leghe[st.session_state.leghe['Squadra'] == admin_selezionato]
    if not squadra_info.empty:
        pin_reale = str(squadra_info['PIN'].values[0])
        if input_pin == pin_reale:
            is_admin = True
            st.sidebar.success(f"Autorizzato: {admin_selezionato}")
        elif input_pin != "":
            st.sidebar.error("PIN non valido")

# --- ELABORAZIONE DATI ---
df_full = pd.merge(st.session_state.df_rosters, st.session_state.leghe, left_on='Squadra_LFM', right_on='Squadra')
df_lega = df_full[df_full['Lega'] == campionato]
ids_esclusi = set(st.session_state.esclusi['Id'])
asteriscati_base = df_lega[df_lega['Id'].isin(ids_esclusi)]
asteriscati = pd.merge(asteriscati_base, st.session_state.esclusi[['Id', 'Nome', 'R', 'FVM']], on='Id', how='left')

ids_occupati_lega = set(df_lega['Id'])
# Svincolati REALI (Non in rosa e non esclusi)
svincolati = st.session_state.quot[(~st.session_state.quot['Id'].isin(ids_occupati_lega)) & (~st.session_state.quot['Id'].isin(ids_esclusi))]

# --- DASHBOARD PRINCIPALE ---
st.title(f"🏆 Sessione Draft: {campionato}")

if is_admin:
    st.warning(f"**MODALITÀ SCRITTURA ATTIVA** - Stai operando come admin della lega.")
else:
    st.info("📊 **MODALITÀ CONSULTAZIONE** - Seleziona la tua squadra admin nella sidebar per registrare i cambi.")

ruoli_nomi = {'P': 'Portieri', 'D': 'Difensori', 'C': 'Centrocampisti', 'A': 'Attaccanti'}
tabs = st.tabs([ruoli_nomi[r] for r in ['P', 'D', 'C', 'A']] + ["📜 Registro Movimenti"])

for i, r_code in enumerate(['P', 'D', 'C', 'A']):
    with tabs[i]:
        lista_ruolo = asteriscati[asteriscati['R'] == r_code].sort_values(by='FVM', ascending=False)
        if lista_ruolo.empty:
            st.write(f"Nessuna sostituzione necessaria per i {ruoli_nomi[r_code]}.")
        else:
            for _, row in lista_ruolo.iterrows():
                # Se già processato (acquisto o salto), non mostrarlo
                if any(d['Id_Perso'] == row['Id'] for d in st.session_state.draft_log):
                    continue

                with st.expander(f"📍 Turno: {row['Squadra_LFM']} | Sostituisce {row['Nome']} (FVM {row['FVM']})"):
                    col1, col2 = st.columns([1, 2])
                    
                    options = svincolati[(svincolati['R'] == r_code) & (svincolati['FVM'] <= row['FVM'])]
                    
                    with col1:
                        st.write(f"**Target:** {row['Nome']}")
                        st.write(f"**Max FVM:** {row['FVM']}")
                        if is_admin:
                            if st.button(f"Salta Turno", key=f"skip_{row['Id']}"):
                                st.session_state.draft_log.append({
                                    "Squadra": row['Squadra_LFM'], "Perso": row['Nome'], "Id_Perso": row['Id'],
                                    "Preso": "DRAFT SALTATO", "Tipo": "SKIP"
                                })
                                st.rerun()
                    
                    with col2:
                        if is_admin:
                            scelta_nome = st.selectbox("Scegli il nuovo giocatore:", options['Nome'].tolist(), key=f"sel_{row['Id']}")
                            if st.button("Registra Acquisto", key=f"btn_{row['Id']}"):
                                player_info = options[options['Nome'] == scelta_nome].iloc[0]
                                # Aggiorna la rosa in memoria
                                st.session_state.df_rosters.loc[st.session_state.df_rosters['Id'] == row['Id'], 'Id'] = player_info['Id']
                                # Registra nel log
                                st.session_state.draft_log.append({
                                    "Squadra": row['Squadra_LFM'], "Perso": row['Nome'], "Id_Perso": row['Id'],
                                    "Preso": player_info['Nome'], "Tipo": "ACQUISTO"
                                })
                                st.rerun()
                        else:
                            st.write("**Migliori alternative svincolate:**")
                            st.dataframe(options.sort_values(by='FVM', ascending=False)[['Nome', 'FVM']].head(10), use_container_width=True)

with tabs[4]:
    if st.session_state.draft_log:
        df_log = pd.DataFrame(st.session_state.draft_log)
        st.table(df_log[['Squadra', 'Perso', 'Preso', 'Tipo']])
    else:
        st.write("Ancora nessun movimento registrato.")
