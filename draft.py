import pandas as pd

def avvia_draft_agosto(file_roster, file_quot_nuovo, file_quot_vecchio):
    # 1. Caricamento e Pulizia
    roster = pd.read_csv(file_roster).dropna(subset=['Id'])
    roster = roster[pd.to_numeric(roster['Id'], errors='coerce').notna()]
    roster['Id'] = roster['Id'].astype(int)

    quot_nuova = pd.read_csv(file_quot_nuovo)
    quot_vecchia = pd.read_csv(file_quot_vecchio) # Necessaria per i dati di chi sparisce

    # 2. Identificazione Asteriscati
    # Giocatori in rosa ma NON nel nuovo listone
    ids_nuovi = set(quot_nuova['Id'])
    asteriscati_base = roster[~roster['Id'].isin(ids_nuovi)]
    
    # Recuperiamo Ruolo e Quotazione dal vecchio listone per la priorità
    asteriscati = pd.merge(asteriscati_base, quot_vecchia[['Id', 'Nome', 'R', 'Qt.I']], on='Id', how='left')

    # 3. Identificazione Svincolati
    # Giocatori nel nuovo listone ma NON in nessuna rosa
    ids_occupati = set(roster['Id'])
    svincolati = quot_nuova[~quot_nuova['Id'].isin(ids_occupati)]

    # 4. Creazione Ordine di Scelta (Priorità per Qt.I più alta)
    priorita = asteriscati.sort_values(by='Qt.I', ascending=False)

    print(f"--- DRAFT DI AGOSTO: {len(priorita)} SOSTITUZIONI DA FARE ---")
    
    risultati = []
    for _, perso in priorita.iterrows():
        # Cerchiamo i sostituti validi (Stesso Ruolo e Quotazione <=)
        validi = svincolati[(svincolati['R'] == perso['R']) & (svincolati['Qt.I'] <= perso['Qt.I'])]
        validi = validi.sort_values(by='Qt.I', ascending=False).head(5) # Primi 5 consigliati
        
        risultati.append({
            "Squadra": perso['Squadra_LFM'],
            "Perso": perso['Nome'],
            "Ruolo": perso['R'],
            "Quot.": perso['Qt.I'],
            "Sostituti_Consigliati": ", ".join(validi['Nome'].tolist())
        })

    return pd.DataFrame(risultati)

# Nota: Per far funzionare il codice dovrai avere il file del listone precedente
# Qui ti mostro come invocare la funzione:
# df_draft = avvia_draft_agosto('fantamanager-2021-rosters.csv', 'quot_nuovo.csv', 'quot_vecchio.csv')
# print(df_draft)
