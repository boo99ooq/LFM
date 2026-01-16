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

# --- 2. CSS PERSONALIZZATO LOOK PREMIUM ---
st.markdown("""
    <style>
    .main { background-color: #f8f9fa; }
    .player-title {
        color: #0e1117;
        font-weight: 850;
        text-transform: uppercase;
        margin-top: 30px;
        border-bottom: 2px solid #e0e0e0;
    }
    .stProgress > div > div > div > div { background-color: #4CAF50; }
    </style>
    """, unsafe_allow_html=True)

# --- 3. FUNZIONI TECNICHE ---
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

# --- 4. AREA ADMIN (VISIBILE SOLO A TE) ---
def mostra_monitoraggio_admin(df_leghe):
    st.sidebar.markdown("---")
    st.sidebar.subheader("🕵️ Area Admin LFM")
    if st.sidebar.checkbox("Stato Consegne"):
        try:
            f = repo.get_contents("clausole_segrete.csv")
            testo = f.decoded_content.decode("utf-8")
            consegnate = [r.split(",")[0] for r in testo.splitlines() if r.strip()]
        except: consegnate = []

        tutte = df_leghe['Squadra'].unique()
        mancanti = [s for s in tutte if s not in consegnate]
        
        st.write("### 📊 Monitoraggio")
        c1, c2 = st.columns(2)
        c1.metric("OK", len(consegnate))
        c2.metric("Mancano", len(mancanti), delta=-len(mancanti), delta_color="inverse")

        if mancanti:
            st.error("Squadre da sollecitare:")
            lista_txt = "\n".join([f"- {s}" for s in mancanti])
            st.code(lista_txt, language="text")
            st.caption("Copia la lista qui sopra per WhatsApp")

# --- 5. LOGIN ---
if 'loggato' not in st.session_state:
    st.session_state.loggato = False
    st.session_state.squadra = None

df_leghe = carica_csv("leghe.csv")

if not st.session_state.loggato:
    st.title("🛡️ LFM - Blindaggio")
    if not df_leghe.empty:
        lega = st.selectbox("Lega", df_leghe['Lega'].unique())
        squadra = st.selectbox("Squadra", df_leghe[df_leghe['Lega'] == lega]['Squadra'].unique())
        pin = st.text_input("PIN", type="password")
        if st.button("ACCEDI", use_container_width=True, type="primary"):
            pin_reale = df_leghe[df_leghe['Squadra'] == squadra]['PIN'].values[0]
            if str(pin) == str(pin_reale):
                st.session_state.loggato = True
                st.session_state.squadra = squadra
                st.rerun()
            else: st.error("PIN errato.")
else:
    # Mostra admin se l'utente sei TU
    if st.session_state.squadra == "Liverpool Football Club": # <--- CAMBIA QUESTO
        mostra_monitoraggio_admin(df_leghe)

    st.title(f"🛡️ Terminale: {st.session_state.squadra}")
    if st.sidebar.button("LOGOUT"):
        st.session_state.loggato = False
        st.rerun()

    # Caricamento dati
    df_rosters = carica_csv("fantamanager-2021-rosters.csv")
    df_quot = carica_csv("quot.csv")
    
    # Pulizia
    df_rosters['Squadra_LFM'] = df_rosters['Squadra_LFM'].astype(str).str.strip()
    df_rosters['Id'] = df_rosters['Id'].astype(str).str.strip()
    df_quot['Id'] = df_quot['Id'].astype(str).str.strip()

    salvati = recupera_precedenti(st.session_state.squadra)
    ids_miei = df_rosters[df_rosters['Squadra_LFM'] == st.session_state.squadra]['Id'].tolist()
    miei_giocatori = df_quot[df_quot['Id'].isin(ids_miei)].copy()
    miei_giocatori['FVM'] = pd.to_numeric(miei_giocatori['FVM'], errors='coerce').fillna(0)
    top_3 = miei_giocatori.nlargest(3, 'FVM')

    max_rivale = df_leghe[df_leghe['Squadra'] != st.session_state.squadra]['Crediti'].max()
    st.markdown(f"""> 💰 **Analisi Strategica:** La squadra più ricca della lega possiede **{max_rivale} cr**. 
    > Impostando per un tuo giocatore una soglia oltre questi crediti, nessuno potrà comprarlo.""")

    tot_tasse = 0
    dati_invio = []

    for i, (_, row) in enumerate(top_3.iterrows()):
        nome, fvm = row['Nome'], int(row['FVM'])
        def_val = max(salvati.get(nome, fvm * 2), fvm)

        st.markdown(f"<h1 class='player-title'>{nome}</h1>", unsafe_allow_html=True)
        c1, c2, c3 = st.columns([2, 1, 1])
        with c1:
            val = st.number_input(f"Clausola (FVM: {fvm})", min_value=fvm, value=def_val, key=f"c_{nome}")
            st.progress(min(1.0, val / max_rivale) if max_rivale > 0 else 1.0, text="Protezione vs Rivali")
        with c2:
            t = calcola_tassa(val)
            tot_tasse += t
            st.metric("Tassa", f"{t} cr")
        with c3:
            if val <= max_rivale: st.error("🟠 VULNERABILE")
            else: st.success("🟢 BLINDATO")
        dati_invio.append(f"{nome}:{val}")

    st.write("---")
    eccedenza = max(0, tot_tasse - 60)
    if tot_tasse <= 60:
        st.success(f"✅ Il Bonus Lega copre interamente le tue tasse. Spesa netta: 0 cr.")
    else:
        st.warning(f"⚠️ Il Bonus Lega copre fino a 60 cr. Eccedi il bonus di **{eccedenza} crediti**, che verranno scalati dal tuo budget.")

    c1, c2, c3 = st.columns(3)
    c1.metric("Totale Tasse", f"{tot_tasse} cr")
    c2.metric("Bonus", "60 cr", delta="-60")
    c3.metric("ADDEBITO ASTA", f"{eccedenza} cr", delta=f"{eccedenza}" if eccedenza > 0 else "0", delta_color="inverse")

    if st.button("📥 REGISTRA CLAUSOLE", type="primary", use_container_width=True):
        salva_su_github(st.session_state.squadra, ";".join(dati_invio))
        st.success("✅ Salvataggio completato!")
        st.balloons()
