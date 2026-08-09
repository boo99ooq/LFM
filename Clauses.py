import streamlit as st
import pandas as pd
from github import Github
from io import StringIO
import math
from datetime import datetime, timedelta
import time
import re

# --- 1. CONFIGURAZIONE ---
FORZA_MODALITA = False  # False = Terminale Blindaggi | True = Mercato

SCADENZA = datetime(2026, 8, 10)          # 00:00 del 10/08 — le clausole diventano visibili (fine Terminale)
APERTURA_MERCATO = datetime(2026, 8, 10, 22, 0)  # 22:00 del 10/08 — da qui si può iniziare a pagarle
FINESTRA_CONTRORISCATTO_INIZIO = datetime(2026, 8, 30, 0, 0, 0)   # ultime 48 ore di agosto
FINESTRA_CONTRORISCATTO_FINE = datetime(2026, 8, 31, 23, 59, 59)
OGGI = datetime.now()

if FORZA_MODALITA:
    PORTALE_APERTO = True
else:
    PORTALE_APERTO = OGGI >= SCADENZA

MERCATO_PAGABILE = FORZA_MODALITA or (datetime.now() >= APERTURA_MERCATO)

ADMIN_SQUADRE = ["Liverpool Football Club", "Villarreal", "Reggina Calcio 1914", "Siviglia"]

try:
    TOKEN = st.secrets["GITHUB_TOKEN"]
    REPO_NAME = st.secrets["REPO_NAME"]
    g = Github(TOKEN)
    repo = g.get_repo(REPO_NAME)
except:
    st.error("Errore configurazione GitHub nei Secrets.")
    st.stop()

# --- 2. FUNZIONI UTILITY ---
def pulisci_nome(nome):
    """Pulisce il nome rimuovendo TUTTO ciò che non è una lettera all'inizio"""
    if not nome or pd.isna(nome):
        return ""
    
    nome_pulito = str(nome).strip()
    
    # Rimuovi tutto fino al primo carattere alfabetico (A-Z o a-z)
    match = re.search(r'[A-Za-z]', nome_pulito)
    if match:
        nome_pulito = nome_pulito[match.start():]
    
    # Se il nome inizia con una lettera minuscola, rendila maiuscola
    if nome_pulito and nome_pulito[0].islower():
        nome_pulito = nome_pulito[0].upper() + nome_pulito[1:]
    
    # Rimuovi spazi multipli
    nome_pulito = re.sub(r'\s+', ' ', nome_pulito).strip()
    
    # Se il nome è vuoto o troppo corto, restituisci l'originale
    if not nome_pulito or len(nome_pulito) < 2:
        return str(nome).strip()
    
    return nome_pulito

def get_team_display_name(squadra):
    """Restituisce il nome della squadra pulito per la visualizzazione"""
    return pulisci_nome(squadra)

# --- 3. FUNZIONI GITHUB ---
@st.cache_data(ttl=300)
def carica_csv(file_name):
    try:
        content = repo.get_contents(file_name)
        return pd.read_csv(StringIO(content.decoded_content.decode("utf-8")))
    except: 
        return pd.DataFrame()

def salva_file_github(path, df, msg):
    time.sleep(0.5)
    csv_buffer = df.to_csv(index=False)
    try:
        f = repo.get_contents(path)
        repo.update_file(path, msg, csv_buffer, f.sha)
    except Exception as e:
        st.error(f"Errore salvataggio: {e}")
        raise

def salva_clausola_singola(squadra, dati_stringa):
    path = "clausole_segrete.csv"
    nuova_riga = f"{squadra},{dati_stringa}"
    try:
        f = repo.get_contents(path)
        contenuto = f.decoded_content.decode("utf-8")
        righe = [r for r in contenuto.splitlines() if not r.startswith(f"{squadra},")]
        righe.append(nuova_riga)
        repo.update_file(path, f"Update {squadra}", "\n".join(righe), f.sha)
    except:
        repo.create_file(path, "Inizializzazione", nuova_riga)

def carica_clausole_salvate():
    """Legge clausole_segrete.csv e restituisce {squadra: 'id:nome:valore;id:nome:valore'}"""
    salvati = {}
    try:
        f = repo.get_contents("clausole_segrete.csv")
        for riga in f.decoded_content.decode("utf-8").splitlines():
            if riga.strip() and "," in riga:
                s, d = riga.split(",", 1)
                salvati[s] = d
    except:
        pass
    return salvati

LIMITE_CLAUSOLE_PAGATE = 3

def conta_clausole_pagate(squadra):
    """Conta quante clausole ha già pagato (con successo) questa squadra, leggendo
    lo storico reale su richieste_scippo.csv invece di fidarsi di un contatore in sessione."""
    df_sc = carica_csv("richieste_scippo.csv")
    if df_sc.empty or 'Acquirente' not in df_sc.columns or 'Stato' not in df_sc.columns:
        return 0
    mask = (df_sc['Acquirente'] == squadra) & (df_sc['Stato'].astype(str).isin(['APPROVATO', 'APPROVATO_AUTO']))
    return int(mask.sum())

def registra_richiesta_clausola(acquirente, proprietario, player_id, nome, costo):
    time.sleep(0.5)
    path = "richieste_scippo.csv"
    orario = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    nuova_riga = f"{acquirente},{proprietario},{player_id},{nome},{costo},PENDENTE,{orario}\n"
    try:
        f = repo.get_contents(path)
        contenuto = f.decoded_content.decode("utf-8") + nuova_riga
        repo.update_file(path, f"Clausola Rescissoria: {nome} alle {orario}", contenuto, f.sha)
    except:
        header = "Acquirente,Proprietario,Id,Nome,Costo,Stato,Orario\n"
        repo.create_file(path, "Init Richieste", header + nuova_riga)

def esegui_trasferimento_clausola(acquirente, proprietario, player_id, nome, costo):
    """Esegue immediatamente lo scambio di crediti e il trasferimento del giocatore,
    senza passare per un'approvazione admin. Registra comunque un log per lo storico."""
    if not (FORZA_MODALITA or datetime.now() >= APERTURA_MERCATO):
        return False, f"Il mercato non è ancora aperto ai pagamenti. Si apre alle {APERTURA_MERCATO.strftime('%H:%M del %d/%m/%Y')}."

    # Controllo limite: conteggio fresco al momento dell'esecuzione, non quello
    # calcolato all'apertura della pagina (potrebbe essere cambiato nel frattempo)
    if conta_clausole_pagate(acquirente) >= LIMITE_CLAUSOLE_PAGATE:
        return False, f"Hai già raggiunto il limite di {LIMITE_CLAUSOLE_PAGATE} clausole pagate. Nessun credito è stato mosso."

    df_ros = carica_csv("fantamanager-2021-rosters.csv")
    proprietario_pulito = pulisci_nome(proprietario)
    riga_giocatore = df_ros[
        (df_ros['Id'].astype(str) == str(player_id)) & (df_ros['Squadra_LFM'] == proprietario_pulito)
    ]

    # Controllo di sicurezza: il giocatore potrebbe essere già stato trasferito
    # nel frattempo (pagina non aggiornata, doppio click, due manager in contemporanea)
    if riga_giocatore.empty:
        return False, "Questo giocatore non appartiene più a questa squadra: probabilmente è già stato trasferito. Nessun credito è stato mosso."

    df_l = carica_csv("leghe.csv")
    df_l.loc[df_l['Squadra'] == acquirente, 'Crediti'] -= int(costo)
    df_l.loc[df_l['Squadra'] == proprietario, 'Crediti'] += int(costo)
    salva_file_github("leghe.csv", df_l, f"Pagata clausola rescissoria {nome}")

    # IMPORTANTE: confronto con pulisci_nome(proprietario), non il nome grezzo —
    # Squadra_LFM è già ripulito (es. prima lettera maiuscola forzata), un nome
    # scritto tutto minuscolo in leghe.csv altrimenti non troverebbe mai match.
    # Filtro anche per Squadra_LFM, non solo per Id — lo stesso Id (stesso
    # giocatore reale) esiste in righe distinte per ogni Lega diversa
    df_ros.loc[
        (df_ros['Id'].astype(str) == str(player_id)) & (df_ros['Squadra_LFM'] == proprietario_pulito),
        'Squadra_LFM'
    ] = acquirente
    salva_file_github("fantamanager-2021-rosters.csv", df_ros, f"Trasferimento {nome}")

    path = "richieste_scippo.csv"
    orario = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    nuova_riga = f"{acquirente},{proprietario},{player_id},{nome},{costo},APPROVATO_AUTO,{orario}\n"
    try:
        f = repo.get_contents(path)
        contenuto = f.decoded_content.decode("utf-8") + nuova_riga
        repo.update_file(path, f"Clausola Rescissoria (auto): {nome} alle {orario}", contenuto, f.sha)
    except:
        header = "Acquirente,Proprietario,Id,Nome,Costo,Stato,Orario\n"
        repo.create_file(path, "Init Richieste", header + nuova_riga)

    return True, None

def parse_orario_pagamento(orario_str):
    """Prova a interpretare il campo Orario come data+ora completa. Restituisce None
    se il formato non è quello atteso (es. voci vecchie salvate solo con l'ora)."""
    try:
        return datetime.strptime(str(orario_str).strip(), "%Y-%m-%d %H:%M:%S")
    except (ValueError, TypeError):
        return None

def get_controriscatti_disponibili(squadra):
    """Clausole subite da 'squadra' ancora rispondibili con controriscatto:
    dentro la finestra di calendario (ultime 48h di agosto) E entro 24h dal pagamento."""
    ora = datetime.now()
    if not (FINESTRA_CONTRORISCATTO_INIZIO <= ora <= FINESTRA_CONTRORISCATTO_FINE):
        return pd.DataFrame()

    df_sc = carica_csv("richieste_scippo.csv")
    if df_sc.empty or 'Proprietario' not in df_sc.columns:
        return pd.DataFrame()

    subite = df_sc[
        (df_sc['Proprietario'] == squadra) &
        (df_sc['Stato'].astype(str) == 'APPROVATO_AUTO')
    ].copy()
    if subite.empty:
        return subite

    def entro_24h(orario_str):
        dt_pagamento = parse_orario_pagamento(orario_str)
        if dt_pagamento is None:
            return False  # formato vecchio senza data: non calcolabile, escluso per sicurezza
        return ora <= dt_pagamento + timedelta(hours=24)

    return subite[subite['Orario'].apply(entro_24h)]

def esegui_controriscatto(proprietario, acquirente, player_id, nome, costo_originale):
    """Il proprietario originale riprende il giocatore pagando il 110% della clausola;
    l'acquirente riceve indietro solo l'importo originale (il 10% extra non va a nessuno)."""
    ora = datetime.now()
    if not (FINESTRA_CONTRORISCATTO_INIZIO <= ora <= FINESTRA_CONTRORISCATTO_FINE):
        return False, "Il diritto di controriscatto è esercitabile solo nelle ultime 48 ore di agosto."

    df_sc = carica_csv("richieste_scippo.csv")
    riga = df_sc[
        (df_sc['Proprietario'] == proprietario) & (df_sc['Acquirente'] == acquirente) &
        (df_sc['Id'].astype(str) == str(player_id)) & (df_sc['Stato'].astype(str) == 'APPROVATO_AUTO')
    ]
    if riga.empty:
        return False, "Transazione non trovata o già gestita in precedenza."
    idx = riga.index[0]

    dt_pagamento = parse_orario_pagamento(riga.loc[idx, 'Orario'])
    if dt_pagamento is None or ora > dt_pagamento + timedelta(hours=24):
        return False, "Sono passate più di 24 ore dal pagamento: il controriscatto non è più esercitabile per questo giocatore."

    df_ros = carica_csv("fantamanager-2021-rosters.csv")
    acquirente_pulito = pulisci_nome(acquirente)
    riga_giocatore = df_ros[
        (df_ros['Id'].astype(str) == str(player_id)) & (df_ros['Squadra_LFM'] == acquirente_pulito)
    ]
    if riga_giocatore.empty:
        return False, "Il giocatore non è più presso questa squadra: il controriscatto non è più valido. Nessun credito è stato mosso."

    penale_totale = math.ceil(float(costo_originale) * 1.10)

    df_l = carica_csv("leghe.csv")
    df_l.loc[df_l['Squadra'] == proprietario, 'Crediti'] -= penale_totale
    df_l.loc[df_l['Squadra'] == acquirente, 'Crediti'] += int(costo_originale)
    salva_file_github("leghe.csv", df_l, f"Controriscatto: {nome} torna a {proprietario}")

    # IMPORTANTE: confronto con pulisci_nome(acquirente) — Squadra_LFM è già
    # ripulito, un nome grezzo tutto minuscolo altrimenti non troverebbe match.
    # Filtro anche per Squadra_LFM, non solo per Id — lo stesso Id esiste in
    # righe distinte per ogni Lega diversa
    df_ros.loc[
        (df_ros['Id'].astype(str) == str(player_id)) & (df_ros['Squadra_LFM'] == acquirente_pulito),
        'Squadra_LFM'
    ] = proprietario
    salva_file_github("fantamanager-2021-rosters.csv", df_ros, f"Controriscatto {nome}")

    df_sc.at[idx, 'Stato'] = 'CONTRORISCATTATO'
    salva_file_github("richieste_scippo.csv", df_sc, f"Controriscatto eseguito su {nome}")

    return True, None

def calcola_tassa(valore):
    if valore <= 200: 
        tassa = valore * 0.10
    elif valore <= 300: 
        tassa = 20 + (valore - 200) * 0.15
    else: 
        tassa = 20 + 15 + (valore - 300) * 0.20
    return math.ceil(tassa)

def get_squadre_e_tasse():
    """Calcola, per ogni squadra con una bozza salvata, la tassa totale di
    blindaggio sui 3 valori salvati. Funzione pura, nessuna scrittura:
    calcola_tassa è deterministica quindi il totale è sempre ricostruibile
    dai soli valori già salvati in clausole_segrete.csv."""
    salvati = carica_clausole_salvate()
    righe = []
    for squadra, dati in salvati.items():
        tot_tasse = 0
        for p in dati.split(";"):
            if not p.strip():
                continue
            try:
                _, _, valore = p.split(":")
                tot_tasse += calcola_tassa(int(valore))
            except ValueError:
                continue
        eccedenza = max(0, tot_tasse - 60)
        righe.append({'Squadra': squadra, 'TotaleTasse': tot_tasse, 'Eccedenza': eccedenza})
    return pd.DataFrame(righe)

def applica_tasse_blindaggio():
    """Deduzione UNA TANTUM della tassa di blindaggio (parte eccedente il Bonus
    Lega di 60cr) dal budget di ogni squadra con una bozza salvata. Protetta da
    un log che rende l'operazione non ripetibile: se il log esiste già, l'app
    rifiuta di eseguirla una seconda volta."""
    log_esistente = carica_csv("tasse_blindaggio.csv")
    if not log_esistente.empty:
        return False, "Le tasse di blindaggio risultano già applicate in precedenza. Operazione non ripetibile."

    df_tasse = get_squadre_e_tasse()
    if df_tasse.empty:
        return False, "Nessuna bozza salvata trovata: nulla da applicare."

    df_l = carica_csv("leghe.csv")
    orario = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    log_righe = []
    for _, r in df_tasse.iterrows():
        squadra_pulita = pulisci_nome(r['Squadra'])
        mask = (df_l['Squadra'] == r['Squadra']) | (df_l['Squadra'].apply(pulisci_nome) == squadra_pulita)
        if mask.any():
            df_l.loc[mask, 'Crediti'] -= int(r['Eccedenza'])
        log_righe.append({
            'Squadra': r['Squadra'], 'TotaleTasse': int(r['TotaleTasse']),
            'Eccedenza': int(r['Eccedenza']), 'Orario': orario
        })

    salva_file_github("leghe.csv", df_l, "Applicazione tasse di blindaggio")
    salva_file_github("tasse_blindaggio.csv", pd.DataFrame(log_righe), "Log tasse di blindaggio applicate")
    return True, None

# --- 4. UI E CSS ---
st.set_page_config(
    page_title="LFM - Portale Clausole", 
    page_icon="🛡️", 
    layout="wide",
    initial_sidebar_state="expanded"
)

st.markdown("""
<style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800;900&display=swap');
    
    html, body, [class*="css"], p, span, div, label, h1, h2, h3, h4, h5, h6,
    button, input, textarea, select, .stMarkdown, .stButton, .stMetric,
    div[data-testid="stExpander"] summary {
        font-family: 'Inter', sans-serif;
    }

    /* Le icone di sistema Streamlit (menu in alto a destra, frecce expander, */
    /* pulsante hamburger) usano un font a legature: qui va ripristinato */
    /* ESPLICITAMENTE, "unset" non basta perché eredita Inter dal genitore. */
    [data-testid="stIconMaterial"],
    [data-testid="stExpanderToggleIcon"],
    [data-testid="baseButton-header"],
    [data-testid="stHeaderActionElements"],
    [data-testid="stHeaderActionElements"] *,
    [data-testid="stToolbarActions"],
    [data-testid="stToolbarActions"] *,
    [data-testid="stMainMenu"],
    [data-testid="stMainMenu"] *,
    [data-testid="stSidebarCollapseButton"],
    [data-testid="stSidebarCollapseButton"] *,
    span[class*="material-symbols"],
    span[class*="material-icons"],
    i[class*="material-symbols"],
    i[class*="material-icons"] {
        font-family: 'Material Symbols Rounded', 'Material Symbols Outlined', 'Material Icons', sans-serif !important;
    }

    .stApp {
        background: linear-gradient(135deg, #0a0e1a 0%, #141b2d 50%, #1a2338 100%);
    }
    
    .player-card {
        background: linear-gradient(145deg, #1a2338, #0f1628);
        border-radius: 20px;
        padding: 24px;
        margin-bottom: 20px;
        border: 1px solid rgba(255, 215, 0, 0.15);
        box-shadow: 0 8px 32px rgba(0,0,0,0.4);
        transition: all 0.3s ease;
    }
    
    .player-card:hover {
        border-color: rgba(255, 215, 0, 0.3);
        transform: translateY(-2px);
        box-shadow: 0 12px 40px rgba(0,0,0,0.5);
    }
    
    .player-name {
        background: linear-gradient(135deg, #FFD700, #FFA500, #FFD700);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
        background-clip: text;
        font-size: 2.4rem !important;
        font-weight: 900 !important;
        text-transform: uppercase;
        letter-spacing: 1px;
        margin-bottom: 4px;
        text-align: center;
    }
    
    .fvm-sub {
        color: #94a3b8 !important;
        font-size: 1rem !important;
        margin-bottom: 20px;
        padding-bottom: 16px;
        border-bottom: 1px solid rgba(255,215,0,0.1);
        text-align: center;
    }
    
    div[data-baseweb="input"] {
        background: #0f1628 !important;
        border: 2px solid rgba(255, 215, 0, 0.3) !important;
        border-radius: 14px !important;
        transition: all 0.3s ease;
    }
    
    div[data-baseweb="input"]:focus-within {
        border-color: #FFD700 !important;
        box-shadow: 0 0 20px rgba(255, 215, 0, 0.1);
    }
    
    input[type="number"] {
        font-size: 2.8rem !important;
        font-weight: 900 !important;
        color: #FFD700 !important;
        text-align: center !important;
        background: transparent !important;
    }
    
    .stProgress > div > div {
        background: linear-gradient(90deg, #FFD700, #FF6B00) !important;
        border-radius: 10px !important;
        height: 8px !important;
    }
    
    .badge-safe {
        background: rgba(34, 197, 94, 0.15);
        border: 1px solid rgba(34, 197, 94, 0.3);
        border-radius: 12px;
        padding: 12px 16px;
        text-align: center;
        color: #4ade80;
        font-weight: 700;
    }
    
    .badge-danger {
        background: rgba(239, 68, 68, 0.15);
        border: 1px solid rgba(239, 68, 68, 0.3);
        border-radius: 12px;
        padding: 12px 16px;
        text-align: center;
        color: #f87171;
        font-weight: 700;
    }
    
    .budget-box {
        background: linear-gradient(145deg, #1a2338, #0f1628);
        border-radius: 16px;
        padding: 20px 24px;
        border: 1px solid rgba(255, 215, 0, 0.2);
        margin-bottom: 24px;
        box-shadow: 0 4px 20px rgba(0,0,0,0.3);
    }
    
    div[data-testid="stMetric"] {
        background: linear-gradient(145deg, #1a2338, #0f1628);
        border-radius: 14px;
        padding: 16px 20px;
        border: 1px solid rgba(255, 215, 0, 0.1);
    }
    
    div[data-testid="stMetricLabel"] {
        color: #94a3b8 !important;
        font-weight: 600 !important;
    }
    
    div[data-testid="stMetricValue"] {
        color: #FFD700 !important;
        font-weight: 800 !important;
    }
    
    div[data-testid="stExpander"] {
        background: linear-gradient(145deg, #1a2338, #0f1628) !important;
        border: 1px solid rgba(255, 215, 0, 0.12) !important;
        border-radius: 16px !important;
        margin-bottom: 12px !important;
        box-shadow: 0 4px 16px rgba(0,0,0,0.3) !important;
    }
    
    div[data-testid="stExpander"] summary {
        font-weight: 700 !important;
        color: #FFD700 !important;
        padding: 12px 4px !important;
        font-size: 1.4rem !important;
        text-align: center !important;
        text-shadow: 0 0 30px rgba(255,215,0,0.15) !important;
        letter-spacing: 0.5px !important;
    }
    
    div[data-testid="stExpander"] summary:hover {
        color: #FFE44D !important;
        text-shadow: 0 0 50px rgba(255,215,0,0.3) !important;
    }
    
    .stButton > button {
        background: linear-gradient(135deg, #FFD700, #F59E0B) !important;
        color: #0f1628 !important;
        font-weight: 700 !important;
        border: none !important;
        border-radius: 12px !important;
        padding: 0.6rem 1.5rem !important;
        transition: all 0.3s ease !important;
        box-shadow: 0 4px 16px rgba(255, 215, 0, 0.2) !important;
    }
    
    .stButton > button:hover {
        transform: translateY(-2px) !important;
        box-shadow: 0 8px 24px rgba(255, 215, 0, 0.3) !important;
    }
    
    section[data-testid="stSidebar"] {
        background: linear-gradient(180deg, #0f1628, #0a0e1a) !important;
        border-right: 1px solid rgba(255, 215, 0, 0.1) !important;
    }
    
    section[data-testid="stSidebar"] * {
        color: #e2e8f0 !important;
    }
    
    h1, h2, h3 {
        color: #e2e8f0 !important;
        font-weight: 800 !important;
        text-align: center !important;
    }
    
    hr {
        border-color: rgba(255, 215, 0, 0.15) !important;
        margin: 24px 0 !important;
    }
    
    p, span, label, .stMarkdown {
        color: #94a3b8 !important;
    }
    
    .stAlert {
        border-radius: 12px !important;
        border: none !important;
    }
    
    .stAlert > div {
        background: rgba(255, 215, 0, 0.05) !important;
    }
    
    .player-row {
        display: flex;
        align-items: center;
        justify-content: space-between;
        padding: 8px 0;
        border-bottom: 1px solid rgba(255,215,0,0.06);
    }
    
    .player-row:last-child {
        border-bottom: none;
    }
    
    .player-row .p-name {
        color: #e2e8f0 !important;
        font-weight: 600 !important;
    }
    
    .player-row .p-value {
        background: rgba(255, 215, 0, 0.12);
        color: #FFD700;
        font-weight: 700;
        padding: 4px 14px;
        border-radius: 20px;
        font-size: 0.9rem;
    }
    
    .header-bar {
        display: flex;
        align-items: center;
        gap: 16px;
        margin-bottom: 24px;
        padding: 16px 24px;
        background: linear-gradient(145deg, #1a2338, #0f1628);
        border-radius: 16px;
        border: 1px solid rgba(255,215,0,0.15);
    }
    
    .status-badge {
        display: inline-block;
        padding: 4px 16px;
        border-radius: 20px;
        font-size: 0.85rem;
        font-weight: 700;
    }
    
    .status-open {
        background: rgba(34, 197, 94, 0.2);
        color: #4ade80;
        border: 1px solid rgba(34, 197, 94, 0.3);
    }
    
    .status-closed {
        background: rgba(239, 68, 68, 0.2);
        color: #f87171;
        border: 1px solid rgba(239, 68, 68, 0.3);
    }
    
    button[data-testid="baseButton-header"] {
        font-size: 0 !important;
    }
    button[data-testid="baseButton-header"]::before {
        content: "☰" !important;
        font-size: 1.5rem !important;
    }
    
    .login-container {
        background: #1a2338;
        padding: 30px;
        border-radius: 20px;
        border: 1px solid rgba(255,215,0,0.1);
    }
    
    .login-title {
        text-align: center;
        padding: 30px 0 20px 0;
    }
    .login-title .icon {
        font-size: 4rem;
    }
    .login-title h1 {
        font-size: 2.8rem;
        margin: 0;
        background: linear-gradient(135deg, #FFD700, #FFA500);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
    }
    .login-title p {
        color: #94a3b8;
        font-size: 1.1rem;
        margin-top: 8px;
    }
    
    .terminal-header {
        text-align: center;
        padding: 16px 0;
        margin-bottom: 24px;
    }
    .terminal-header .title {
        font-size: 2.2rem;
        font-weight: 900;
        color: #FFD700;
    }
    .terminal-header .subtitle {
        color: #94a3b8;
        font-size: 1rem;
        margin-top: 4px;
    }
</style>
""", unsafe_allow_html=True)

# --- 5. STATO SESSIONE ---
if 'loggato' not in st.session_state:
    st.session_state.loggato = False
    st.session_state.squadra = None

if 'portale_aperto_override' not in st.session_state:
    st.session_state.portale_aperto_override = None  # None = nessun override, segue la data reale

# Risincronizza SEMPRE con la data reale a ogni rerun, a meno che l'admin non
# abbia forzato manualmente una modalità in QUESTA sessione col toggle qui sotto.
# Senza questo, chi tiene la scheda del browser aperta da prima della scadenza
# resterebbe bloccato sulla modalità "fotografata" al primo caricamento della
# pagina, anche ore dopo che la scadenza reale è scattata.
if st.session_state.portale_aperto_override is not None:
    st.session_state.portale_aperto = st.session_state.portale_aperto_override
else:
    st.session_state.portale_aperto = PORTALE_APERTO

# --- 6. CARICAMENTO DATI ---
df_leghe = carica_csv("leghe.csv")

# Pulisci i nomi delle squadre nel DataFrame
if not df_leghe.empty:
    df_leghe['Squadra_Pulita'] = df_leghe['Squadra'].apply(pulisci_nome)

# --- 7. FUNZIONE PER OTTENERE SQUADRE PULITE ---
def get_clean_teams(lega=None):
    """Restituisce un dizionario {nome_pulito: nome_originale} per le squadre"""
    if lega:
        df_filtered = df_leghe[df_leghe['Lega'] == lega]
    else:
        df_filtered = df_leghe
    
    teams = {}
    for _, row in df_filtered.iterrows():
        original = row['Squadra']
        clean = row.get('Squadra_Pulita', pulisci_nome(original))
        if not clean:
            clean = original
        teams[clean] = original
    return teams

# --- 8. LOGIN ---
if not st.session_state.loggato:
    st.markdown("""
    <div class="login-title">
        <div class="icon">🛡️</div>
        <h1>LFM - Accesso Portale</h1>
        <p>Inserisci le tue credenziali per accedere</p>
    </div>
    """, unsafe_allow_html=True)
    
    if not df_leghe.empty:
        col1, col2, col3 = st.columns([1, 1.5, 1])
        with col2:
            with st.container():
                st.markdown('<div class="login-container">', unsafe_allow_html=True)
                
                lega = st.selectbox("📋 Lega", df_leghe['Lega'].unique())
                teams_dict = get_clean_teams(lega)
                clean_team_names = list(teams_dict.keys())
                selected_clean = st.selectbox("🏟️ Squadra", clean_team_names)
                squadra = teams_dict[selected_clean]
                pin = st.text_input("🔑 PIN Segreto", type="password")
                
                if st.button("🚀 ACCEDI", use_container_width=True):
                    match = df_leghe[df_leghe['Squadra'] == squadra]
                    if match.empty:
                        squadre_lega = df_leghe[df_leghe['Lega'] == lega]['Squadra'].tolist()
                        st.error(
                            f"❌ Squadra '{squadra}' non trovata in leghe.csv per la lega '{lega}'. "
                            f"Squadre disponibili in questa lega: {squadre_lega}"
                        )
                    else:
                        pin_r = match['PIN'].values[0]
                        if str(pin).strip() == str(pin_r).strip():
                            st.session_state.loggato = True
                            st.session_state.squadra = squadra
                            st.rerun()
                        else:
                            st.error("❌ PIN errato. Riprova.")
                
                st.markdown('</div>', unsafe_allow_html=True)

# --- 9. AREA LOGGATO ---
else:
    # Header
    if not st.session_state.portale_aperto:
        status_text = "🛡️ TERMINALE BLINDAGGI"
        status_class = "status-closed"
    elif not MERCATO_PAGABILE:
        status_text = "👁️ CLAUSOLE VISIBILI (non ancora pagabili)"
        status_class = "status-closed"
    else:
        status_text = "🔓 MERCATO APERTO"
        status_class = "status-open"
    squadra_display = get_team_display_name(st.session_state.squadra)
    
    st.markdown(f"""
    <div class="header-bar">
        <div style="font-size: 2.8rem;">🛡️</div>
        <div style="flex: 1;">
            <div style="color: #94a3b8; font-size: 0.9rem;">LFM · Portale Clausole</div>
            <div style="font-size: 1.4rem; font-weight: 800; color: #FFD700;">{squadra_display}</div>
        </div>
        <div>
            <span class="status-badge {status_class}">{status_text}</span>
        </div>
    </div>
    """, unsafe_allow_html=True)

    # --- 10. SIDEBAR ADMIN ---
    if st.session_state.squadra in ADMIN_SQUADRE:
        with st.sidebar:
            st.markdown("### 🕵️ PANNELLO ADMIN")
            st.markdown("---")
            
            nuova_modalita = st.toggle(
                "🔓 Modalità Mercato (forza ANTEPRIMA, solo per te)", 
                value=st.session_state.portale_aperto,
                help="Forza la modalità solo nella tua sessione, per test. Non segue più la data reale finché non premi 'Segui data reale'."
            )
            if nuova_modalita != st.session_state.portale_aperto:
                st.session_state.portale_aperto_override = nuova_modalita
                st.rerun()

            if st.session_state.portale_aperto_override is not None:
                st.caption("⚠️ Stai forzando la modalità manualmente, non stai seguendo la data reale.")
                if st.button("↩️ Segui data reale"):
                    st.session_state.portale_aperto_override = None
                    st.rerun()
            
            st.markdown("---")
            
            st.markdown("#### 📝 Stato Blindaggi")
            salvati_admin = carica_clausole_salvate()
            consegnate = list(salvati_admin.keys())
            mancanti = [s for s in df_leghe['Squadra'].unique() if s not in consegnate]

            col1, col2 = st.columns(2)
            col1.metric("Consegnate", f"{len(consegnate)}")
            col2.metric("Mancanti", f"{len(mancanti)}")
            if st.checkbox("👀 Vedi chi manca"):
                for m in mancanti:
                    st.text(f"❌ {get_team_display_name(m)}")
            
            st.markdown("---")

            st.markdown("#### 💰 Tasse di Blindaggio")
            if datetime.now() < SCADENZA:
                st.caption(f"🔒 Disponibile dal raggiungimento della scadenza ({SCADENZA.strftime('%d/%m/%Y %H:%M')}).")
            else:
                log_tasse = carica_csv("tasse_blindaggio.csv")
                if not log_tasse.empty:
                    st.success("✅ Tasse già applicate.")
                    st.dataframe(log_tasse, use_container_width=True, hide_index=True)
                    st.download_button(
                        "⬇️ Scarica resoconto CSV", log_tasse.to_csv(index=False),
                        file_name="tasse_blindaggio.csv", mime="text/csv"
                    )
                else:
                    anteprima = get_squadre_e_tasse()
                    if anteprima.empty:
                        st.info("Nessuna bozza salvata trovata.")
                    else:
                        st.caption("Anteprima — nessun credito ancora mosso:")
                        st.dataframe(anteprima, use_container_width=True, hide_index=True)
                        st.download_button(
                            "⬇️ Scarica anteprima CSV", anteprima.to_csv(index=False),
                            file_name="anteprima_tasse_blindaggio.csv", mime="text/csv"
                        )
                        conferma_tasse = st.checkbox("Confermo di voler applicare le tasse (operazione unica, non ripetibile).")
                        if conferma_tasse and st.button("💸 APPLICA TASSE DI BLINDAGGIO"):
                            ok, motivo = applica_tasse_blindaggio()
                            if ok:
                                st.success("✅ Tasse applicate e registrate.")
                                st.rerun()
                            else:
                                st.error(f"❌ {motivo}")
            
            st.markdown("---")
            
            st.markdown("#### 💸 Clausole Rescissorie")
            if st.checkbox("📥 GESTISCI RICHIESTE"):
                df_sc = carica_csv("richieste_scippo.csv")
                if not df_sc.empty:
                    pendenti = df_sc[df_sc['Stato'].astype(str).str.contains('PENDENTE', na=False)]
                    if pendenti.empty:
                        st.info("✅ Nessuna richiesta pendente")
                    else:
                        st.warning(f"📬 {len(pendenti)} richieste in attesa")
                        for i, r in pendenti.iterrows():
                            acquirente_clean = get_team_display_name(r['Acquirente'])
                            proprietario_clean = get_team_display_name(r['Proprietario'])
                            with st.expander(f"🕒 {r['Orario']} - {r['Nome']}"):
                                st.write(f"**Acquirente:** {acquirente_clean}")
                                st.write(f"**Proprietario:** {proprietario_clean}")
                                st.write(f"**Costo:** {r['Costo']} cr")
                                c_adm1, c_adm2 = st.columns(2)
                                if c_adm1.button("✅ APPROVA", key=f"ok_{i}", use_container_width=True):
                                    df_l = carica_csv("leghe.csv")
                                    df_l.loc[df_l['Squadra'] == r['Acquirente'], 'Crediti'] -= int(r['Costo'])
                                    df_l.loc[df_l['Squadra'] == r['Proprietario'], 'Crediti'] += int(r['Costo'])
                                    salva_file_github("leghe.csv", df_l, f"Pagata clausola rescissoria {r['Nome']}")
                                    df_ros = carica_csv("fantamanager-2021-rosters.csv")
                                    df_ros.loc[df_ros['Id'].astype(str) == str(r['Id']), 'Squadra_LFM'] = r['Acquirente']
                                    salva_file_github("fantamanager-2021-rosters.csv", df_ros, f"Trasferimento {r['Nome']}")
                                    df_sc.at[i, 'Stato'] = 'APPROVATO'
                                    salva_file_github("richieste_scippo.csv", df_sc, "Richiesta approvata")
                                    st.rerun()
                                if c_adm2.button("❌ RIFIUTA", key=f"no_{i}", use_container_width=True):
                                    df_sc.at[i, 'Stato'] = 'RIFIUTATO'
                                    salva_file_github("richieste_scippo.csv", df_sc, "Richiesta rifiutata")
                                    st.rerun()
                else:
                    st.info("📭 Nessuna richiesta presente")

    # --- 11. LOGICA PRINCIPALE ---
    
    # SEZIONE MERCATO (PORTALE APERTO)
    if st.session_state.portale_aperto:
        st.markdown("""
        <div style="text-align: center; padding: 10px 0 20px 0;">
            <h2 style="font-size: 2.5rem; color: #FFD700; text-shadow: 0 0 40px rgba(255,215,0,0.3);">🔓 Mercato Clausole Rescissorie</h2>
            <p style="color: #94a3b8; font-size: 1.1rem;">Acquista i giocatori pagando la loro clausola rescissoria</p>
        </div>
        """, unsafe_allow_html=True)
        
        lega_view = st.selectbox("📋 Filtra Lega", df_leghe['Lega'].unique())
        my_cred = df_leghe[df_leghe['Squadra'] == st.session_state.squadra]['Crediti'].values[0]
        clausole_pagate = conta_clausole_pagate(st.session_state.squadra)
        clausole_esaurite = clausole_pagate >= LIMITE_CLAUSOLE_PAGATE

        if not MERCATO_PAGABILE:
            attesa = APERTURA_MERCATO - datetime.now()
            ore_attesa = attesa.seconds // 3600
            minuti_attesa = (attesa.seconds % 3600) // 60
            st.warning(
                f"👁️ Le clausole sono visibili ma **non ancora pagabili**. "
                f"Si apre alle **{APERTURA_MERCATO.strftime('%H:%M del %d/%m/%Y')}** "
                f"(tra {attesa.days}g {ore_attesa}h {minuti_attesa}m)."
            )

        st.sidebar.markdown(f"""
        <div style="background: linear-gradient(145deg, #1a2338, #0f1628); padding: 20px; border-radius: 16px; border: 1px solid rgba(255,215,0,0.2); text-align: center; margin-bottom: 20px;">
            <div style="color: #94a3b8; font-weight: 600; font-size: 0.9rem;">💰 IL TUO BUDGET</div>
            <div style="color: #FFD700; font-weight: 900; font-size: 2.4rem;">{my_cred} cr</div>
        </div>
        """, unsafe_allow_html=True)
        st.sidebar.metric("💸 Clausole pagate", f"{clausole_pagate} / {LIMITE_CLAUSOLE_PAGATE}")
        if clausole_esaurite:
            st.sidebar.warning("Hai raggiunto il limite di clausole pagabili.")

        df_r = carica_csv("fantamanager-2021-rosters.csv")
        df_q = carica_csv("quot.csv")
        
        # PULIZIA NOMI
        if not df_r.empty and 'Squadra_LFM' in df_r.columns:
            df_r['Squadra_LFM'] = df_r['Squadra_LFM'].astype(str).str.strip()
            df_r['Squadra_LFM'] = df_r['Squadra_LFM'].apply(pulisci_nome)
        
        if not df_q.empty and 'Nome' in df_q.columns:
            df_q['Nome'] = df_q['Nome'].apply(pulisci_nome)
        
        df_q['Id'] = df_q['Id'].astype(str)
        salvati = carica_clausole_salvate()

        # Mappa Id -> proprietario ATTUALE, per filtrare giocatori già trasferiti
        # (una clausola salvata su clausole_segrete.csv non si aggiorna da sola
        # quando il giocatore viene comprato: senza questo controllo resterebbe
        # "acquistabile" sotto la squadra vecchia anche dopo il trasferimento)
        #
        # IMPORTANTE: la mappa va limitata alle sole squadre della Lega selezionata.
        # Lo stesso Id (stesso giocatore reale) può appartenere legittimamente a
        # squadre diverse in leghe diverse (40 squadre su 4 campionati, stessi
        # giocatori Serie A duplicati per ogni lega) — una mappa globale Id->Squadra
        # sovrascriverebbe silenziosamente 3 proprietari su 4.
        #
        # Le chiavi/valori usano pulisci_nome(): Squadra_LFM è già ripulito da
        # quella funzione (es. prima lettera forzata maiuscola), mentre i nomi
        # grezzi di leghe.csv (sq) non lo sono — un nome scritto tutto minuscolo
        # nel CSV originale altrimenti non troverebbe mai corrispondenza.
        squadre_lega_view = set(pulisci_nome(s) for s in df_leghe[df_leghe['Lega'] == lega_view]['Squadra'])
        proprietario_attuale = {}
        if not df_r.empty and 'Id' in df_r.columns and 'Squadra_LFM' in df_r.columns:
            df_r_lega_view = df_r[df_r['Squadra_LFM'].isin(squadre_lega_view)]
            proprietario_attuale = df_r_lega_view.astype({'Id': str}).set_index('Id')['Squadra_LFM'].to_dict()

        # Mostra squadre
        for sq in df_leghe[df_leghe['Lega'] == lega_view]['Squadra']:
            sq_pulito = pulisci_nome(sq)
            sq_clean = get_team_display_name(sq)
            sq_c = df_leghe[df_leghe['Squadra'] == sq]['Crediti'].values[0]
            
            team_title = f"🏟️  {sq_clean.upper()}  ·  💰 {sq_c} cr"
            
            with st.expander(team_title):
                if sq in salvati:
                    giocatori = []
                    for p in salvati[sq].split(";"):
                        if not p.strip():
                            continue
                        pid, pnm, pvl = p.split(":")
                        giocatori.append((pid, pnm, int(pvl)))
                else:
                    st.caption("⚠️ Clausole d'ufficio applicate (Valore FVM)")
                    ids = df_r[df_r['Squadra_LFM'] == sq_pulito]['Id'].astype(str).tolist()
                    top_giocatori = df_q[df_q['Id'].isin(ids)].nlargest(3, 'FVM')
                    giocatori = [(row['Id'], row['Nome'], int(row['FVM'])) for _, row in top_giocatori.iterrows()]

                # Esclude i giocatori già trasferiti nel frattempo: la clausola
                # salvata potrebbe essere obsoleta se il giocatore è stato comprato
                giocatori = [
                    (pid, pnm, pvl) for pid, pnm, pvl in giocatori
                    if proprietario_attuale.get(str(pid)) == sq_pulito
                ]

                if not giocatori:
                    st.caption("— Nessun giocatore attualmente disponibile —")

                for pid, pnm, pvl in giocatori:
                    pnm_clean = get_team_display_name(pnm)
                    
                    col1, col2, col3 = st.columns([3, 1, 1.5])
                    with col1:
                        st.markdown(f"<div class='player-row' style='margin-bottom:0; border:none; padding:6px 0;'><span class='p-name'>⚽ {pnm_clean}</span></div>", unsafe_allow_html=True)
                    with col2:
                        st.markdown(f"<span class='p-value'>💰 {pvl} cr</span>", unsafe_allow_html=True)
                    if sq != st.session_state.squadra:
                        with col3:
                            if not MERCATO_PAGABILE:
                                st.caption("👁️ Non ancora pagabile")
                            elif clausole_esaurite:
                                st.caption(f"🔒 Limite {LIMITE_CLAUSOLE_PAGATE}/{LIMITE_CLAUSOLE_PAGATE} raggiunto")
                            elif st.button("💸 PAGA", key=f"a_{pid}", use_container_width=True):
                                if my_cred >= pvl:
                                    with st.spinner("⏳ Trasferimento in corso..."):
                                        ok, motivo = esegui_trasferimento_clausola(st.session_state.squadra, sq, pid, pnm, pvl)
                                    if ok:
                                        st.success(f"✅ Clausola pagata! {pnm_clean} è ora nella tua rosa.")
                                        st.balloons()
                                        st.rerun()
                                    else:
                                        st.error(f"❌ {motivo}")
                                        st.rerun()
                                else:
                                    st.error("❌ Budget insufficiente!")

        # --- DIRITTO DI CONTRORISCATTO: solo nelle ultime 48 ore di agosto ---
        if FINESTRA_CONTRORISCATTO_INIZIO <= datetime.now() <= FINESTRA_CONTRORISCATTO_FINE:
            st.divider()
            st.markdown("### 🔁 Diritto di Controriscatto")
            st.caption(
                "Puoi annullare l'acquisto di un tuo giocatore entro 24 ore dal pagamento della clausola, "
                "pagando una penale del 10%. A chi ti ha scippato il giocatore torna solo l'importo originale."
            )
            controriscatti = get_controriscatti_disponibili(st.session_state.squadra)
            if controriscatti.empty:
                st.info("Nessuna clausola subita ancora rispondibile con controriscatto in questo momento.")
            else:
                for idx, r in controriscatti.iterrows():
                    dt_pagamento = parse_orario_pagamento(r['Orario'])
                    scadenza = dt_pagamento + timedelta(hours=24)
                    rimanente = scadenza - datetime.now()
                    ore_rim = rimanente.seconds // 3600
                    min_rim = (rimanente.seconds % 3600) // 60
                    penale_totale = math.ceil(float(r['Costo']) * 1.10)
                    acquirente_clean = get_team_display_name(r['Acquirente'])
                    nome_clean = get_team_display_name(r['Nome'])

                    with st.expander(f"⚠️ {nome_clean} — scippato da {acquirente_clean}"):
                        st.write(f"Costo originale della clausola: **{r['Costo']} cr**")
                        st.write(f"Penale totale da pagare per riprenderlo: **{penale_totale} cr**")
                        st.caption(f"⏳ Tempo rimanente per rispondere: {ore_rim}h {min_rim}m")
                        if st.button("🔁 Esercita Controriscatto", key=f"cr_{idx}", use_container_width=True):
                            with st.spinner("⏳ Controriscatto in corso..."):
                                ok, motivo = esegui_controriscatto(
                                    st.session_state.squadra, r['Acquirente'], r['Id'], r['Nome'], r['Costo']
                                )
                            if ok:
                                st.success(f"✅ {nome_clean} torna nella tua rosa.")
                                st.rerun()
                            else:
                                st.error(f"❌ {motivo}")
                                st.rerun()

    # SEZIONE TERMINALE BLINDAGGI (PORTALE CHIUSO)
    else:
        squadra_display = get_team_display_name(st.session_state.squadra)
        
        st.markdown(f"""
        <div class="terminal-header">
            <div class="title">🛡️ {squadra_display.upper()}</div>
            <div class="subtitle">Imposta le clausole per blindare i tuoi giocatori</div>
        </div>
        """, unsafe_allow_html=True)
        
        # --- Tabella manutenzione stadi (condivisa) ---
        LIVELLI_STADIO = [10, 20, 30, 40, 50, 60, 70, 80, 90, 100]
        MANUTENZIONE_STADIO = {10: 45, 20: 25, 30: 35, 40: 50, 50: 70,
                                60: 90, 70: 120, 80: 150, 90: 185, 100: 215}
        df_stadi = carica_csv("stadi.csv")

        def get_costo_stadio(nome_squadra):
            if df_stadi.empty or 'Squadra' not in df_stadi.columns or 'Stadio' not in df_stadi.columns:
                return 0
            match = df_stadi[df_stadi['Squadra'] == nome_squadra]
            if match.empty:
                return 0
            cap = pd.to_numeric(match['Stadio'].values[0], errors='coerce')
            if pd.isna(cap):
                return 0
            livello_vicino = min(LIVELLI_STADIO, key=lambda x: abs(x - cap))
            return MANUTENZIONE_STADIO[livello_vicino]

        # VERIFICA CHE LA SQUADRA ESISTA
        squadra_found = False
        if not df_leghe.empty:
            squadra_match = df_leghe[df_leghe['Squadra'] == st.session_state.squadra]
            if not squadra_match.empty:
                squadra_found = True
                crediti_totali = squadra_match['Crediti'].values[0]
                mia_lega = squadra_match['Lega'].values[0]

                rivali = df_leghe[
                    (df_leghe['Squadra'] != st.session_state.squadra) &
                    (df_leghe['Lega'] == mia_lega)
                ].copy()
                if not rivali.empty:
                    rivali['CreditiNetti'] = rivali.apply(
                        lambda r: r['Crediti'] - get_costo_stadio(r['Squadra']), axis=1
                    )
                    max_rivale = rivali['CreditiNetti'].max()
                else:
                    max_rivale = 0
            else:
                st.error(f"⚠️ Squadra '{st.session_state.squadra}' non trovata nel database.")
                if st.button("🔄 TORNA AL LOGIN"):
                    st.session_state.loggato = False
                    st.session_state.squadra = None
                    st.rerun()
                st.stop()
        
        if squadra_found:
            st.markdown("<div class='budget-box'>", unsafe_allow_html=True)
            c1, c2, c3 = st.columns(3)
            c1.metric("💰 Budget Attuale", f"{crediti_totali} cr")
            c2.metric("🔝 Massimo Rivali", f"{max_rivale} cr")
            c2.caption("Netto della sola manutenzione stadio (unico costo certo per tutti); ingaggi non sottratti perché non noti a priori per le altre squadre.")
            c3.info(f"Soglia Blindaggio: > {max_rivale} cr")
            st.markdown("</div>", unsafe_allow_html=True)

            df_r = carica_csv("fantamanager-2021-rosters.csv")
            df_q = carica_csv("quot.csv")
            
            if df_r.empty or df_q.empty:
                st.error("⚠️ Dati dei giocatori non disponibili.")
                st.stop()
            
            # PULIZIA NOMI
            if 'Squadra_LFM' not in df_r.columns:
                st.error(
                    f"⚠️ Il file 'fantamanager-2021-rosters.csv' non contiene la colonna "
                    f"'Squadra_LFM'. Colonne trovate: {df_r.columns.tolist()}. "
                    f"Controlla l'intestazione del file su GitHub (spazi, maiuscole, delimitatore)."
                )
                st.stop()
            df_r['Squadra_LFM'] = df_r['Squadra_LFM'].astype(str).str.strip()
            df_r['Squadra_LFM'] = df_r['Squadra_LFM'].apply(pulisci_nome)

            if 'Nome' in df_q.columns:
                df_q['Nome'] = df_q['Nome'].apply(pulisci_nome)

            df_q['Id'] = df_q['Id'].astype(str)
            ids_miei = df_r[df_r['Squadra_LFM'] == pulisci_nome(st.session_state.squadra)]['Id'].astype(str).tolist()
            
            if not ids_miei:
                st.warning("⚠️ Nessun giocatore trovato per la tua squadra.")
                st.stop()

            # --- BUDGET NETTO: crediti - ingaggi rosa (Qt.I) - manutenzione stadio ---
            if 'Qt.I' not in df_q.columns:
                st.error(
                    f"⚠️ Il file 'quot.csv' non contiene la colonna 'Qt.I'. "
                    f"Colonne trovate: {df_q.columns.tolist()}. "
                    f"Controlla l'intestazione del listone su GitHub (spazi, punteggiatura, delimitatore)."
                )
                st.stop()
            df_q['Qt.I'] = pd.to_numeric(df_q['Qt.I'], errors='coerce').fillna(0)
            costo_ingaggi = df_q[df_q['Id'].isin(ids_miei)]['Qt.I'].sum()

            costo_stadio = get_costo_stadio(st.session_state.squadra)
            capacita_stadio = None
            if not df_stadi.empty and 'Squadra' in df_stadi.columns and 'Stadio' in df_stadi.columns:
                stadio_match = df_stadi[df_stadi['Squadra'] == st.session_state.squadra]
                if not stadio_match.empty:
                    capacita_stadio = pd.to_numeric(stadio_match['Stadio'].values[0], errors='coerce')

            budget_netto = crediti_totali - costo_ingaggi - costo_stadio

            st.markdown("<div class='budget-box'>", unsafe_allow_html=True)
            n1, n2, n3, n4 = st.columns(4)
            n1.metric("💼 Ingaggi Rosa", f"-{int(costo_ingaggi)} cr", help="Somma di Qt.I (quot.csv) di tutti i giocatori in rosa")
            if capacita_stadio is not None and pd.notna(capacita_stadio):
                n2.metric("🏟️ Manutenzione Stadio", f"-{costo_stadio} cr", help=f"Capacità: {int(capacita_stadio)}.000 posti (stadi.csv)")
            else:
                n2.metric("🏟️ Manutenzione Stadio", "N/D", help="Squadra non trovata in stadi.csv")
            n3.metric("💰 Budget Netto Proiettato", f"{int(budget_netto)} cr")
            if budget_netto < 0:
                n4.error("⚠️ Negativo")
            else:
                n4.success("✅ In equilibrio")
            st.markdown("</div>", unsafe_allow_html=True)

            top_3 = df_q[df_q['Id'].isin(ids_miei)].copy()
            top_3['FVM'] = pd.to_numeric(top_3['FVM'], errors='coerce').fillna(0)
            top_3 = top_3.nlargest(3, 'FVM')

            # Carica l'eventuale bozza già salvata da questa squadra, per pre-riempire i campi
            bozza_salvata = carica_clausole_salvate().get(st.session_state.squadra, "")
            bozza_dict = {}
            if bozza_salvata:
                for p in bozza_salvata.split(";"):
                    if p.strip():
                        b_pid, b_nome, b_val = p.split(":")
                        bozza_dict[b_pid] = int(b_val)

            if bozza_dict:
                st.info("💾 Hai già una bozza salvata: i valori qui sotto sono quelli dell'ultimo salvataggio. Puoi modificarli liberamente fino alla scadenza.")
            else:
                st.caption("ℹ️ Nessuna bozza salvata finora: i campi partono dal valore FVM di default.")

            tot_tasse = 0
            dati_invio = []

            for i, (_, row) in enumerate(top_3.iterrows()):
                nome, fvm, p_id = row['Nome'], int(row['FVM']), row['Id']
                nome_clean = get_team_display_name(nome)
                valore_default = bozza_dict.get(str(p_id), fvm)
                
                st.markdown("<div class='player-card'>", unsafe_allow_html=True)
                st.markdown(f"<div class='player-name'>{nome_clean}</div>", unsafe_allow_html=True)
                st.markdown(f"<div class='fvm-sub'><span style='color:#94a3b8;'>Valore di Mercato (FVM):</span> <span style='color:#FFD700; font-weight:700;'>{fvm} cr</span></div>", unsafe_allow_html=True)
                
                col1, col2 = st.columns([1.8, 1.5])
                with col1:
                    val = st.number_input(
                        "💎 CLAUSOLA", 
                        min_value=1, 
                        value=valore_default, 
                        key=f"c_{p_id}",
                        help="Inserisci l'importo della clausola rescissoria"
                    )
                    progress = min(1.0, val / max_rivale) if max_rivale > 0 else 0
                    st.progress(progress)
                    if val > max_rivale:
                        st.caption(f"✅ Superata la soglia di {max_rivale} cr")
                    
                with col2:
                    st.write("")
                    t = calcola_tassa(val)
                    tot_tasse += t
                    c_t, c_s = st.columns(2)
                    with c_t:
                        st.metric("📊 Tassa", f"{t} cr")
                    with c_s:
                        if val <= max_rivale:
                            st.markdown("<div class='badge-danger'>🔓 VULNERABILE</div>", unsafe_allow_html=True)
                        else:
                            st.markdown("<div class='badge-safe'>🛡️ BLINDATO</div>", unsafe_allow_html=True)
                
                st.markdown("</div>", unsafe_allow_html=True)
                dati_invio.append(f"{p_id}:{nome}:{val}")

            st.markdown("---")
            st.markdown("### 📊 Riepilogo Clausole")
            
            extra = max(0, tot_tasse - 60)
            budget_residuo = crediti_totali - extra

            if tot_tasse <= 60:
                st.success(f"✅ Il Bonus Lega di 60cr copre interamente le tue tasse ({tot_tasse} cr). Il tuo budget resta intatto.")
            else:
                st.warning(f"⚠️ Il Bonus Lega copre le tue tasse fino a 60cr. Eccedi il bonus di **{extra} crediti** (Tasse totali: {tot_tasse} cr), che verranno scalati dal tuo budget.")

            c_fin1, c_fin2, c_fin3 = st.columns(3)
            c_fin1.metric("💰 Totale Tasse", f"{tot_tasse} cr")
            c_fin2.metric("🎁 Franchigia Bonus", "- 60 cr")
            c_fin3.metric("💳 Budget Rimanente", f"{budget_residuo} cr", delta=-extra if extra > 0 else 0)

            st.caption(f"🗓️ Potrai modificare questa bozza quante volte vuoi fino al {SCADENZA.strftime('%d/%m/%Y')}. Dopo quella data il Terminale si chiude e l'ultima bozza salvata diventa la clausola definitiva.")

            if st.button("📥 REGISTRA CLAUSOLE TEMPORANEAMENTE (PUOI MODIFICARLE FINO ALLA DEADLINE)", type="primary", use_container_width=True):
                with st.spinner("⏳ Salvataggio in corso..."):
                    try:
                        salva_clausola_singola(st.session_state.squadra, ";".join(dati_invio))
                        st.success(f"✅ Bozza salvata! Puoi tornare a modificarla in qualsiasi momento prima del {SCADENZA.strftime('%d/%m/%Y')}.")
                        st.balloons()
                    except Exception as e:
                        st.error(f"❌ Errore durante il salvataggio: {e}")
