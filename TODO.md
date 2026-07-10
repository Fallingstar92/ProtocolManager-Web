# Protocol Manager Web

## Spuštění

Otevřít WSL.

Přejít do projektu:

```bash
cd ~/ProtocolManager
```

Aktivovat virtuální prostředí:

```bash
source .venv/bin/activate
```

Spustit server:

```bash
python -m uvicorn web.main:app --host 0.0.0.0 --port 8000 --reload
```

---

## Lokální přístup

WSL:

```
http://127.0.0.1:8000
```

Windows:

```
http://192.168.3.241:8000
```

---

## Pokud nejde přístup z jiných počítačů

Zjistit IP WSL:

```bash
hostname -I
```

Například:

```
172.27.17.241
```

Otevřít Windows PowerShell jako správce.

Smazat staré přesměrování:

```powershell
netsh interface portproxy delete v4tov4 listenaddress=192.168.3.241 listenport=8000
```

Vytvořit nové:

```powershell
netsh interface portproxy add v4tov4 listenaddress=192.168.3.241 listenport=8000 connectaddress=172.27.17.241 connectport=8000
```

---

## Firewall

Povolit port 8000:

```powershell
New-NetFirewallRule -DisplayName "Protocol Manager Web" -Direction Inbound -Protocol TCP -LocalPort 8000 -Action Allow
```

---

## Ověření

Ve WSL:

```bash
ss -tlnp | grep 8000
```

Musí být:

```
LISTEN ... 0.0.0.0:8000
```

---

## Databáze

Databáze:

```
data/protocolmanager.db
```

Po vytvoření databáze:

```bash
python -m src.database.init_db
```

Import zákazníků:

```bash
python -m src.database.import_customers
```

Import nastavení:

```bash
PYTHONPATH=src python -m src.database.import_settings
```

---

## Git

Stav:

```bash
git status
```

Commit:

```bash
git add .
git commit -m "Popis změny"
```

Push:

```bash
git push
```