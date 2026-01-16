import streamlit as st
import pandas as pd
from github import Github
from io import StringIO
import math
from datetime import datetime

# --- 1. CONFIGURAZIONE TEMPORALE E ADMIN ---
# Modifica SCADENZA per i tuoi test (es. 2024 per vedere il mercato aperto)
SCADENZA = datetime(2026, 8, 1) 
OGGI = datetime.now()
PORTALE_APERTO = OGGI >= SCADENZA
# Inserisci i nomi esatti delle squadre che possono approvare gli scippi
ADMIN_SQUADRE = ["Liverpool Football Club", "Villarreal", "Reggina Calcio 1914", "Siviglia"]

try:
    TOKEN = st.secrets["GITHUB_TOKEN"]
    REPO_NAME = st.secrets["REPO_NAME"]
    g = Github(TOKEN)
    repo = g.get_repo(REPO_NAME)
except Exception as e:
    st.error(f"Errore configurazione GitHub Secrets: {e}")
    st.stop()

# --- 2. FUNZIONI DI SUPPORTO GITHUB ---
def carica_csv(file_name):
    try:
        content = repo.get_contents(file_name)
        return pd.read_csv(StringIO(content.decoded_content.decode("latin1")))
    except:
        return pd.DataFrame()

def salva_file_github(path, df, msg):
    csv_buffer = df.to_csv(index=False)
    f = repo.get_contents(path)
    repo.update_file(path, msg, csv_buffer, f.sha)

def salva_clausola_singola(squadra, dati_stringa):
    path = "clausole_segrete.csv"
    nuova_riga = f"{squadra},{dati_stringa}"
    try:
        f = repo.get_contents(path)
        contenuto = f.decoded_content.decode("utf-8")
        # Rimuovo vecchia riga della stessa squadra se presente
        righe = [r for r in contenuto.splitlines() if not r.startswith(f"{squadra},")]
        righe.append(nuova_riga)
        repo.update_file(path, f"Update clausole {squadra}", "\n".join(righe), f.sha)
    except:
        repo.create_file(path, "Inizializzazione clausole", nuova_riga)

def registra_richiesta_scippo(acquirente, proprietario, player_id, nome, costo):
    path = "richieste_scippo.csv"
    nuova_riga = f"{acquirente},{proprietario},{player_id},{nome},{costo},PENDENTE\n"
    try:
        f = repo.get_contents(path)
        contenuto = f.decoded_content.decode("utf-8") + nuova_riga
        repo.update_file(path, f"Nuova richiesta scippo: {nome}", contenuto, f.sha)
    except:
        header = "Acquirente,Proprietario,Id,Nome,Costo,Stato\n"
        repo.create_file(path, "Inizializzazione scippi", header + nuova_riga)

# --- 3. LOGICA CALCOLI ---
def calcola_tassa(valore):
    if valore <= 200: 
        tassa = valore * 0.10
    elif valore <= 300: 
        tassa = 20 + (valore - 200) * 0.15
    else: 
        tassa = 20 + 15 + (valore - 300) * 0.20
    return math.ceil(tassa)

# --- 4. INTERFACCIA E CSS ---
st.set_page_config(page_title="LFM - Portale Clausole", layout="wide")
st.markdown("""<style>
    .player-name { color: #1E3A8A; font-size: 1.8rem !important; font-weight: 900; text-transform: uppercase; margin-top: 10px; }
    .budget-box { background-color: #f8f9fa; padding: 20px; border-radius: 10px; border-left: 6px solid #1E3A8A; margin-bottom: 20px; }
    .stButton>button { width: 100%; border-radius: 5px; }
</style>""", unsafe_allow_html=True)

if 'loggato' not in st.session_state:
    st.session_state.loggato = False
    st.session_state.squadra = None

df_leghe = carica_csv("leghe.csv")

# --- 5. ACCESSO ---
if not st.session_state.loggato:
    st.title("🛡️ LFM - Portale Blindaggio & Mercato")
    if not df_leghe.empty:
        lega = st.selectbox("Seleziona la tua Lega", df_leghe['Lega'].unique())
        squadra = st.selectbox("Seleziona la tua Squadra", df_leghe[df_leghe['Lega'] == lega]['Squadra'].unique())
        pin = st.text_input("Inserisci PIN Segreto", type="password")
        
        if st.button("ACCEDI"):
            pin_r = df_leghe[df_leghe['Squadra'] == squadra]['PIN'].values[0]
            if str(pin) == str(pin_r):
                st.session_state.loggato = True
                st.session_state.squadra = squadra
                st.rerun()
            else: 
                st.error("PIN errato.")
    else:
        st.error("File leghe.csv non trovato o vuoto.")

else:
    # --- LOGICA ADMIN (Visibile solo alle squadre autorizzate) ---
    if st.session_state.squadra in ADMIN_SQUADRE:
        with st.sidebar:
            st.subheader("🕵️ Pannello Amministratore")
            if st.checkbox("Mostra Scippi da Approvare"):
                df_scippi = carica_csv("richieste_scippo.csv")
                if not df_scippi.empty:
                    pendenti = df_scippi[df_scippi['Stato'] == 'PENDENTE']
                    if pendenti.empty:
                        st.write("Nessuna richiesta pendente.")
                    else:
                        for idx, row in pendenti.iterrows():
                            st.warning(f"{row['Acquirente']} vuole {row['Nome']} da {row['Proprietario']}")
                            if st.button(f"APPROVA SCIPPO #{idx}"):
                                # 1. Aggiorna Crediti (Leghe)
                                df_l = carica_csv("leghe.csv")
                                df_l.loc[df_l['Squadra'] == row['Acquirente'], 'Crediti'] -= row['Costo']
                                df_l.loc[df_l['Squadra'] == row['Proprietario'], 'Crediti'] += row['Costo']
                                salva_file_github("leghe.csv", df_l, "Update Crediti post-scippo")
                                
                                # 2. Sposta Giocatore (Rosters)
                                df_r = carica_csv("fantamanager-2021-rosters.csv")
                                df_r.loc[df_r['Id'].astype(str) == str(row['Id']), 'Squadra_LFM'] = row['Acquirente']
                                salva_file_github("fantamanager-2021-rosters.csv", df_r, "Update Roster post-scippo")
                                
                                # 3. Chiudi richiesta
                                df_scippi.at[idx, 'Stato'] = 'APPROVATO'
                                salva_file_github("richieste_scippo.csv", df_scippi, "Richiesta approvata")
                                st.rerun()
                else:
                    st.write("File richieste_scippo.csv non esistente.")

    # --- LOGICA POST-SCADENZA: TABELLONE PUBBLICO ---
    if PORTALE_APERTO:
        st.title("🔓 LFM - Mercato Clausole Aperto")
        lega_view = st.selectbox("Visualizza Lega", df_leghe['Lega'].unique())
        my_credits = df_leghe[df_leghe['Squadra'] == st.session_state.squadra]['Crediti'].values[0]
        st.sidebar.metric("Il tuo Budget", f"{my_credits} cr")

        # Recupero salvataggi esistenti
        salvati = {}
        try:
            f = repo.get_contents("clausole_segrete.csv")
            testo = f.decoded_content.decode("utf-8")
            for riga in testo.splitlines():
                if riga.strip():
                    parti = riga.split(",")
                    if len(parti) == 2:
                        salvati[parti[0]] = parti[1]
        except: pass

        # Dati per generazione automatica d'ufficio
        df_rosters = carica_csv("fantamanager-2021-rosters.csv")
        df_quot = carica_csv("quot.csv")
        df_rosters['Squadra_LFM'] = df_rosters['Squadra_LFM'].astype(str).str.strip()
        df_quot['Id'] = df_quot['Id'].astype(str)

        squadre_lega = df_leghe[df_leghe['Lega'] == lega_view]['Squadra'].unique()
        
        for sq in squadre_lega:
            with st.expander(f"🏟️ SQUADRA: {sq.upper()}"):
                # CASO A: Squadra ha depositato le clausole
                if sq in salvati:
                    for p in salvati[sq].split(";"):
                        p_id, p_nome, p_val = p.split(":")
                        c1, c2, c3 = st.columns([3,1,2])
                        c1.write(f"**{p_nome}**")
                        c2.write(f"{p_val} cr")
                        if sq != st.session_state.squadra:
                            if c3.button(f"SCIPPA {p_nome}", key=f"pay_{p_id}_{sq}"):
                                if my_credits >= int(p_val):
                                    registra_richiesta_scippo(st.session_state.squadra, sq, p_id, p_nome, p_val)
                                    st.success("Richiesta inviata all'admin!")
                                else:
                                    st.error("Crediti insufficienti.")
                
                # CASO B: Generazione automatica (FVM x 2)
                else:
                    st.caption("⚠️ Clausole d'ufficio (FVM x 2)")
                    ids_sq = df_rosters[df_rosters['Squadra_LFM'] == sq]['Id'].astype(str).tolist()
                    giocatori_sq = df_quot[df_quot['Id'].isin(ids_sq)].copy()
                    giocatori_sq['FVM'] = pd.to_numeric(giocatori_sq['FVM'], errors='coerce').fillna(0)
                    top_3_auto = giocatori_sq.nlargest(3, 'FVM')
                    
                    for _, row in top_3_auto.iterrows():
                        p_id, p_nome, p_fvm = row['Id'], row['Nome'], int(row['FVM'])
                        p_val_auto = p_fvm * 2
                        c1, c2, c3 = st.columns([3,1,2])
                        c1.write(f"**{p_nome}**")
                        c2.write(f"{p_val_auto} cr")
                        if sq != st.session_state.squadra:
                            if c3.button(f"SCIPPA {p_nome}", key=f"auto_{p_id}_{sq}"):
                                if my_credits >= p_val_auto:
                                    registra_richiesta_scippo(st.session_state.squadra, sq, p_id, p_nome, p_val_auto)
                                    st.success("Richiesta d'ufficio inviata!")
                                else:
                                    st.error("Crediti insufficienti.")

    # --- LOGICA PRE-SCADENZA: BLINDAGGIO MANUALE ---
    else:
        st.title(f"🛡️ Blindaggio: {st.session_state.squadra}")
        df_rosters = carica_csv("fantamanager-2021-rosters.csv")
        df_quot = carica_csv("quot.csv")
        
        crediti_totali = df_leghe[df_leghe['Squadra'] == st.session_state.squadra]['Crediti'].values[0]
        max_rivale = df_leghe[df_leghe['Squadra'] != st.session_state.squadra]['Crediti'].max()
        
        st.markdown(f"""<div class='budget-box'>
            <div style='display:flex; justify-content:space-around;'>
                <div><b>Tuo Budget:</b> {crediti_totali} cr</div>
                <div><b>Max Rivali:</b> {max_rivale} cr</div>
            </div>
        </div>""", unsafe_allow_html=True)

        df_rosters['Squadra_LFM'] = df_rosters['Squadra_LFM'].astype(str).str.strip()
        ids_miei = df_rosters[df_rosters['Squadra_LFM'] == st.session_state.squadra]['Id'].astype(str).tolist()
        df_quot['Id'] = df_quot['Id'].astype(str)
        miei_giocatori = df_quot[df_quot['Id'].isin(ids_miei)].copy()
        miei_giocatori['FVM'] = pd.to_numeric(miei_giocatori['FVM'], errors='coerce').fillna(0)
        
        # Prendo i 3 giocatori con FVM più alto
        top_3 = miei_giocatori.nlargest(3, 'FVM')
        
        tot_tasse = 0
        dati_per_github = []
        
        for i, (_, row) in enumerate(top_3.iterrows()):
            nome, fvm, p_id = row['Nome'], int(row['FVM']), row['Id']
            st.markdown(f"<div class='player-name'>{nome}</div>", unsafe_allow_html=True)
            st.caption(f"Valore di mercato (FVM): {fvm} cr")
            
            # Input clausola
            val_clausola = st.number_input(f"Imposta Clausola per {nome}", min_value=fvm, value=fvm*2, key=f"inp_{p_id}")
            tassa = calcola_tassa(val_clausola)
            tot_tasse += tassa
            
            dati_per_github.append(f"{p_id}:{nome}:{val_clausola}")
            st.write(f"📈 Tassa blindaggio: **{tassa} cr**")
            st.divider()

        # Calcolo eccedenza budget per le tasse
        budget_tasse_fisso = 60
        costo_extra = max(0, tot_tasse - budget_tasse_fisso)
        
        st.subheader(f"Riepilogo Costi")
        st.write(f"Tasse Totali: {tot_tasse} cr")
        if costo_extra > 0:
            st.error(f"⚠️ Pagherai {costo_extra} cr dal tuo budget crediti (superati i 60 cr bonus)")
        else:
            st.success(f"✅ Costo tasse coperto interamente dal bonus di 60 cr.")

        if st.button("SALVA E CONFERMA CLAUSOLE", type="primary"):
            if crediti_totali >= costo_extra:
                salva_clausola_singola(st.session_state.squadra, ";".join(dati_per_github))
                st.success("Configurazione salvata con successo su GitHub!")
            else:
                st.error("Non hai abbastanza crediti per coprire le tasse!")
