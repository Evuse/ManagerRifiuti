# Guida completa: Mac Intel + Home Assistant OS

Questa guida parte da zero. Non è necessario lasciare il Mac acceso dopo
l'importazione: calendario e promemoria vengono conservati ed eseguiti dal
Raspberry Pi con Home Assistant OS.

## Prima di cominciare

Servono:

- il Mac Intel e il Raspberry Pi collegati alla stessa rete locale;
- Home Assistant raggiungibile dal browser (normalmente
  `http://homeassistant.local:8123`);
- l'app Home Assistant Companion già associata a ogni telefono destinatario;
- una fotografia JPG o PNG che mostri interamente il foglio semestrale;
- un backup recente di Home Assistant.

La soluzione contiene **due elementi distinti**:

1. `ManagerRifiuti.app`, da eseguire sul Mac;
2. `custom_components/manager_rifiuti`, da copiare una sola volta nel Raspberry.

## 1. Scaricare i due pacchetti

### Se sono disponibili gli artifact GitHub Actions

1. Apri su GitHub il repository di Manager Rifiuti.
2. Seleziona **Actions**.
3. Apri l'ultima esecuzione verde chiamata **Build portatile**.
4. In fondo alla pagina, in **Artifacts**, scarica:
   - `ManagerRifiuti-macos-intel`;
   - `HomeAssistant-custom-component`.
5. Fai doppio clic sui due ZIP nella cartella `Download`.

Gli artifact di GitHub possono scadere. Se non sono presenti, il proprietario
del repository deve aprire **Actions → Build portatile → Run workflow** e
attendere che tutti i job diventino verdi.

### Se hai ricevuto direttamente gli ZIP

Estrai entrambi e verifica di trovare `ManagerRifiuti.app` e la cartella
`custom_components`.

> Non scaricare il solo ZIP del codice sorgente pensando che contenga già
> l'app: l'eseguibile è nell'artifact `ManagerRifiuti-macos-intel`.

## 2. Avviare l'app sul Mac Intel

1. Sposta `ManagerRifiuti.app` in una cartella a tua scelta, per esempio
   `Applicazioni`. Non viene eseguito un installer.
2. Fai doppio clic sull'app.
3. Se macOS impedisce l'apertura perché l'app non è firmata:
   - apri **Impostazioni di Sistema → Privacy e Sicurezza**;
   - scorri fino al messaggio relativo a Manager Rifiuti;
   - scegli **Apri comunque** e conferma.
4. Lascia aperta l'app: prima dobbiamo preparare Home Assistant.

L'avviso di macOS è previsto per una build privata non notarizzata. Non
disattivare Gatekeeper globalmente e non usare comandi come `sudo spctl`.

## 3. Fare un backup di Home Assistant

1. Apri Home Assistant dal browser.
2. Vai in **Impostazioni → Sistema → Backup**.
3. Crea un backup manuale prima di copiare la custom integration.
4. Attendi che il backup risulti completato.

## 4. Copiare la custom integration nel Raspberry

Il risultato finale sul Raspberry deve essere esattamente:

```text
/config/custom_components/manager_rifiuti/manifest.json
/config/custom_components/manager_rifiuti/__init__.py
/config/custom_components/manager_rifiuti/config_flow.py
...altri file dell'integrazione...
```

Non creare un livello doppio come
`manager_rifiuti/manager_rifiuti/manifest.json`.

### Metodo consigliato: add-on Samba share

1. In Home Assistant apri **Impostazioni → Componenti aggiuntivi → Store dei
   componenti aggiuntivi**.
2. Cerca e installa **Samba share**.
3. Imposta una password robusta nella configurazione dell'add-on.
4. Avvialo. Non è necessario abilitare “Avvia all'avvio” dopo aver concluso la
   copia.
5. Sul Mac apri Finder e scegli **Vai → Connessione al server…**.
6. Inserisci `smb://homeassistant.local` e premi **Connetti**.
7. Accedi con le credenziali configurate nell'add-on e apri la condivisione
   `config`.
8. Se `custom_components` non esiste, creala in `config`.
9. Copia dentro `custom_components` la cartella `manager_rifiuti` estratta
   dall'artifact.

### Alternativa: Studio Code Server o Terminal & SSH

Puoi copiare la stessa cartella sotto `/config/custom_components/` usando uno
di questi add-on. Non modificare i singoli file a mano e non copiare la cartella
desktop `manager_rifiuti`: serve quella che si trova sotto `custom_components`.

## 5. Riavviare Home Assistant

1. Vai in **Impostazioni → Sistema**.
2. Dal menu di alimentazione in alto a destra scegli **Riavvia Home Assistant**.
3. Attendi il riavvio completo e ricarica il browser.

Se l'integrazione non appare al passo successivo, controlla il percorso indicato
nel passo 4 e poi consulta **Impostazioni → Sistema → Registri** cercando
`manager_rifiuti`.

## 6. Aggiungere Manager Rifiuti dalla GUI

1. Vai in **Impostazioni → Dispositivi e servizi**.
2. Premi **Aggiungi integrazione**.
3. Cerca **Manager Rifiuti** e selezionala.
4. Conferma la creazione dell'integrazione.
5. Apri il dispositivo o le entità appena create.
6. Cerca il sensore **ID importazione Manager Rifiuti**.
7. Copia esattamente il suo valore: è una chiave casuale, non la password di
   Home Assistant.

Conserva privatamente questo ID: chi lo conosce e può raggiungere Home Assistant
in rete locale può sostituire il calendario importato.

## 7. Individuare i servizi dei telefoni

Per ogni telefono:

1. Apri almeno una volta l'app Home Assistant Companion sul telefono.
2. In Home Assistant vai in **Strumenti per sviluppatori → Azioni**.
3. Cerca `notify.mobile_app`.
4. Annota il nome completo relativo al telefono, per esempio:

```text
notify.mobile_app_iphone_mario
notify.mobile_app_iphone_lucia
```

Se un telefono non compare, verifica dall'app Companion che sia collegato allo
stesso server e che le notifiche siano autorizzate nel sistema operativo.

## 8. Configurare notifiche e secondo promemoria

1. Torna in **Impostazioni → Dispositivi e servizi**.
2. Nella scheda di Manager Rifiuti premi **Configura**.
3. Nel campo dei servizi `notify`, inserisci **un servizio completo per riga**:

```text
notify.mobile_app_iphone_mario
notify.mobile_app_iphone_lucia
```

4. Inserisci l'orario della prima notifica nel formato `HH:MM:SS`, per esempio
   `20:00:00`.
5. Per un secondo promemoria inserisci un altro orario, per esempio `22:00:00`.
   Lascialo vuoto per disabilitarlo.
6. Nel campo tipologie abilitate usa i codici separati da virgola:

```text
O,I,TS,V,M,P,C,S
```

   Puoi rimuovere ciò che non interessa, per esempio `O,I,P,C`.
7. Salva. L'integrazione viene ricaricata con le nuove impostazioni.

Le raccolte multiple producono notifiche separate. Premendo **Rifiuti già
portati fuori** su una notifica viene annullato il successivo promemoria per
quella specifica tipologia.

## 9. Collegare l'app desktop

Nella parte inferiore di Manager Rifiuti sul Mac inserisci:

- **Indirizzo Home Assistant:** `http://homeassistant.local:8123`;
- **ID webhook:** il valore copiato al passo 6.

Se il nome locale non funziona, usa l'indirizzo IP del Raspberry, per esempio
`http://192.168.1.50:8123`. Non aggiungere `/api/webhook/`: lo fa l'app.

## 10. Preparare la fotografia

Per ridurre gli errori:

1. appoggia il calendario su una superficie piana;
2. includi tutti e quattro i bordi del foglio;
3. evita riflessi e ombre sui simboli;
4. scatta perpendicolarmente al foglio e con la massima risoluzione disponibile;
5. non ritagliare intestazioni dei mesi o righe dei giorni.

Puoi caricare un solo semestre oppure due immagini. JPG e PNG sono i formati
consigliati.

## 11. Analizzare e revisionare il calendario

1. Premi **Scegli una o due immagini…**.
2. Seleziona il foglio luglio–dicembre, oppure entrambi i semestri.
3. Premi **Analizza localmente** e attendi. La foto non viene inviata né a Home
   Assistant né a servizi cloud.
4. Nella revisione controlla ogni data e ogni codice.
5. Correggi le celle con doppio clic, rimuovi righe errate e aggiungi eventuali
   raccolte mancanti.
6. Controlla l'anno e seleziona **Confermo che l'anno selezionato è corretto**.
7. Se l'app segnala mesi non riconosciuti, verifica le date e conferma anche il
   relativo controllo.
8. Premi **OK** soltanto dopo il confronto con la fotografia originale.

La revisione è importante: il riconoscimento fotografico non può garantire
accuratezza assoluta in presenza di sfocatura, prospettiva o riflessi.

## 12. Creare un backup e importare

1. Dall'app scegli **File → Esporta backup JSON…** e conserva il file.
2. Premi **Invia il calendario a Home Assistant**.
3. Attendi il messaggio **Importazione completata**.

Una nuova importazione sostituisce il calendario precedente e azzera gli stati
“già portati fuori”.

## 13. Verificare il risultato in Home Assistant

Controlla in **Impostazioni → Dispositivi e servizi → Entità**:

- `calendar.raccolta_rifiuti`;
- `sensor.raccolta_oggi`;
- `sensor.raccolta_domani`;
- `button.rifiuti_gia_portati_fuori`.

Apri il calendario Home Assistant e verifica alcune date confrontandole con la
foto. Se sono errate, correggile nella revisione desktop e ripeti l'importazione.

## 14. Aggiungere il pulsante alla dashboard

1. Apri la dashboard desiderata.
2. Seleziona **Modifica dashboard → Aggiungi scheda**.
3. Aggiungi una scheda **Pulsante**.
4. Come entità scegli **Rifiuti già portati fuori**.
5. Salva.

Il pulsante dashboard completa tutte le tipologie previste per domani. Il
pulsante dentro una notifica completa invece soltanto la tipologia indicata.

## 15. Collaudo senza aspettare domani

Per un test realistico:

1. importa temporaneamente una raccolta con la data di domani dalla schermata di
   revisione;
2. imposta la prima notifica a cinque minuti dall'ora attuale;
3. salva le opzioni e attendi senza chiudere Home Assistant;
4. verifica che ogni telefono riceva la notifica;
5. premi **Rifiuti già portati fuori**;
6. controlla che il secondo promemoria non arrivi;
7. reimporta infine il calendario corretto e ripristina gli orari desiderati.

## Risoluzione dei problemi

### L'app non si apre sul Mac

- Verifica di avere scaricato `macos-intel`, non `macos-apple-silicon`.
- Estrai completamente lo ZIP prima di avviare l'app.
- Usa **Privacy e Sicurezza → Apri comunque**; non disabilitare Gatekeeper.

### “Invio non riuscito”

- Apri l'indirizzo di Home Assistant nel browser dello stesso Mac.
- Prova l'IP locale al posto di `homeassistant.local`.
- Ricopia l'ID senza spazi iniziali o finali.
- Verifica che la custom integration sia ancora caricata.
- VPN, rete ospiti e isolamento Wi-Fi possono impedire al Mac di raggiungere il
  Raspberry.

### L'integrazione non compare

- Il file `manifest.json` deve trovarsi direttamente in
  `/config/custom_components/manager_rifiuti/`.
- Riavvia completamente Home Assistant dopo la copia.
- Controlla i registri per errori riferiti a `manager_rifiuti`.

### Nessuna notifica

- Usa il nome completo `notify.mobile_app_*`, uno per riga.
- Verifica le autorizzazioni notifiche sul telefono.
- Controlla fuso orario e ora in **Impostazioni → Sistema → Generale**.
- Assicurati che esista una raccolta per domani e che non sia già completata.

### Il secondo promemoria arriva comunque

Premi l'azione associata alla stessa tipologia, oppure usa il pulsante dashboard
per completare tutte le raccolte di domani. Controlla che l'azione sia stata
ricevuta prima dell'orario del secondo promemoria.

