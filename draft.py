import pandas as pd

def genera_draft_per_lega(file_roster, file_leghe, file_quot_nuovo, file_quot_vecchio):
    # 1. Caricamento Dati
    df_rosters = pd.read_csv(file_roster)
    df_leghe = pd.read_csv(file_leghe)
    df_nuovo = pd.read_csv(file_quot_nuovo)
    df_vecchio = pd.read_csv(file_quot_vecchio)

    # Pulizia (rimuoviamo i simboli '$' o righe vuote)
    df_rosters = df_rosters[pd.to_numeric(df_rosters['Id'], errors='coerce').notna()].copy()
    df_rosters['Id'] = df_rosters['Id'].astype(int)
    
    # Uniamo le rose con la loro lega di appartenenza
    roster_completo = pd.merge(df_rosters, df_leghe[['Squadra', 'Lega']], 
                               left_on='Squadra_LFM', right_on='Squadra', how='left')

    elenco_leghe = roster_completo['Lega'].unique()
    report_finale = []

    for lega in elenco_leghe:
        if pd.isna(lega): continue
        
        # Filtriamo i dati per la lega corrente
        roster_lega = roster_completo[roster_completo['Lega'] == lega]
        ids_occupati = set(roster_lega['Id'])
        
        # 2. Identificazione Asteriscati in questa Lega
        ids_nuovi = set(df_nuovo['Id'])
        persi_ids = roster_lega[~roster_lega['Id'].isin(ids_nuovi)]
        
        # Recupero info da listone vecchio
        asteriscati = pd.merge(persi_ids, df_vecchio[['Id', 'Nome', 'R', 'Qt.I']], on='Id', how='left')
        
        # 3. Identificazione Svincolati per questa Lega
        svincolati = df_nuovo[~df_nuovo['Id'].isin(ids_occupati)]

        # 4. Ordinamento Priorità (Regolamento: Qt.I più alta)
        asteriscati = asteriscati.sort_values(by='Qt.I', ascending=False)

        for _, p in asteriscati.iterrows():
            # Filtro sostituti validi (stesso ruolo e quota <=)
            sost_validi = svincolati[(svincolati['R'] == p['R']) & (svincolati['Qt.I'] <= p['Qt.I'])]
            migliori = sost_validi.sort_values(by='Qt.I', ascending=False).head(3)['Nome'].tolist()
            
            report_finale.append({
                "Campionato": lega,
                "Squadra": p['Squadra_LFM'],
                "Giocatore Perso": p['Nome'],
                "Ruolo": p['R'],
                "Quot. Origine": p['Qt.I'],
                "Consigli Svincolati": ", ".join(migliori)
            })

    return pd.DataFrame(report_finale)

# Esempio d'uso:
# df_risultato = genera_draft_per_lega('fantamanager-2021-rosters.csv', 'leghe.csv', 'quot_agosto.csv', 'quot_luglio.csv')
# df_risultato.to_excel("Draft_Agosto_Completo.xlsx", index=False)mport pandas as pd

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
