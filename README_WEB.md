# Protocol Manager Web

První webová verze aplikace.

Cíl této fáze je převést aktuální desktopové GUI do prohlížeče bez databáze.
Zákazníci zatím zůstávají v `data/customers.json` a PDF se stále generuje přes ReportLab.

## Instalace

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

## Spuštění

```bash
uvicorn web.main:app --reload
```

Potom otevři:

```text
http://127.0.0.1:8000
```

## Co je hotové

- Webové rozhraní v tmavém stylu původní desktop aplikace
- Formulář pro vytvoření předávacího protokolu
- Načítání zákazníků z `customers.json`
- Načítání dopravců a zákazníků pro pole `Převzal`
- Generování PDF přes stávající `src/pdf/generator.py`
- Náhled PDF v prohlížeči
- Tisk přes prohlížeč otevřením PDF
- Ukládání jména uživatele a výchozího čísla protokolu do `data/config.json`

## Co zatím není součástí této fáze

- Databáze
- Historie protokolů
- Přihlašování zaměstnanců
- Role pro účetní
- Automatické číslování protokolů

Tyto věci patří do další fáze po dokončení webového převodu.
