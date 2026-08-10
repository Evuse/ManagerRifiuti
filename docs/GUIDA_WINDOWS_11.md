# Guida completa per Windows 11

Questa procedura parte da zero e usa Python 3.12 per evitare incompatibilità
con le librerie OCR. I comandi vanno eseguiti in Windows PowerShell.

## 1. Azzerare il calendario importato in Home Assistant

Apri PowerShell e incolla, una riga alla volta:

```powershell
$webhook = Read-Host "Incolla qui l'ID importazione Manager Rifiuti"
$payload = @{ year = 2026; collections = @() } | ConvertTo-Json
Invoke-RestMethod -Method Post -Uri "http://homeassistant.local:8123/api/webhook/$webhook" -ContentType "application/json" -Body $payload
Remove-Variable webhook, payload
```

Questo azzera solo i dati dell'integrazione Manager Rifiuti. Non rimuove
dispositivi, dashboard o altre integrazioni. Se `homeassistant.local` non viene
risolto, sostituiscilo con l'indirizzo IP del Raspberry.

## 2. Preparare una copia aggiornata

Scarica il repository da GitHub con **Code → Download ZIP**, estrailo in una
nuova cartella e apri PowerShell dentro la cartella che contiene
`pyproject.toml`. Non riutilizzare il vecchio ambiente `.venv`.

Controlla che Python 3.12 sia disponibile:

```powershell
py -3.12 --version
```

Il risultato deve iniziare con `Python 3.12`. Poi esegui:

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\python.exe -m pip install --upgrade pip
.\.venv\Scripts\python.exe -m pip install -e ".[build]"
```

## 3. Provare l'app aggiornata

```powershell
.\.venv\Scripts\python.exe -m manager_rifiuti
```

Trascina la fotografia nella finestra, premi **Analizza le immagini** e verifica
che la revisione mostri 149 raccolte. Dopo la conferma viene creato
automaticamente un JSON in `Documenti\ManagerRifiuti\backup`.

## 4. Reimportare in Home Assistant

Inserisci l'indirizzo di Home Assistant e l'ID importazione, quindi premi
**Invia 149 raccolte a Home Assistant**. Una nuova importazione sostituisce i
dati precedenti; non si somma a essi.

## 5. Creare la versione Windows standalone

Chiudi l'app e, nella stessa PowerShell, esegui:

```powershell
.\.venv\Scripts\python.exe -m PyInstaller manager-rifiuti.spec --clean --noconfirm
```

Al termine avvia:

```powershell
.\dist\ManagerRifiuti\ManagerRifiuti.exe
```

Questa versione non richiede Python, ma deve rimanere insieme alla sottocartella
`_internal`. Per creare uno ZIP distribuibile:

```powershell
Compress-Archive -Path ".\dist\ManagerRifiuti" -DestinationPath ".\ManagerRifiuti-Windows-x64.zip" -Force
```

Su un altro PC basta estrarre interamente lo ZIP e fare doppio clic su
`ManagerRifiuti.exe`. Windows SmartScreen può mostrare un avviso perché il file
non è firmato digitalmente: scegli **Ulteriori informazioni → Esegui comunque**
solo se il pacchetto proviene dal tuo repository.

## 6. Aggiornare una build precedente

Chiudi la vecchia app ed elimina o rinomina la vecchia cartella portabile, poi
usa tutta la nuova cartella `dist\ManagerRifiuti`. Non sovrascrivere soltanto
l'eseguibile. Tema, URL e cartella dei backup restano salvati nelle impostazioni
del profilo Windows; l'ID di importazione non viene memorizzato su disco.
