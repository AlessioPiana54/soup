# SOUP packages

Ogni funzionalità di SOUP arriva in un **package**: una cartella che contiene insieme backend
(importer, operazioni, visualizzatori, exporter, tool) e frontend (bundle dei visualizzatori).
I package di questa cartella sono **forniti** con SOUP; altri si installano a runtime da uno zip.

> **Sicurezza.** Un package esegue codice con i privilegi del server (la parte `server/`, nel
> processo Flask) e del browser (la parte `app/`, caricata nella pagina). Installa solo package di
> cui ti fidi. Per questo l'installazione da zip è disattivata di default e va abilitata con
> `SOUP_ALLOW_PACKAGE_INSTALL=true` (il `docker-compose.yaml` di sviluppo la abilita).

## Struttura

```
soup-packages/<nome>/
  soup-package.json      manifest (obbligatorio)
  server/                modulo Python del package
    __init__.py          obbligatorio
    plugin.py            la classe SoupPlugin indicata nel manifest
    api.py               API pubblica per gli altri package
  app/                   sorgenti frontend (dal commit 5)
    dist/index.js        bundle con i Web Component dei visualizzatori
```

La cartella deve avere lo stesso nome del package.

## Manifest: `soup-package.json`

```json
{
  "name": "csv_reader",
  "version": "1.0.0",
  "api_version": "2.0",
  "label": "CSV reader",
  "description": "Reads flat CSV event logs.",
  "author": "SOUP",
  "requires": [],
  "requires_tools": [],
  "provides_tools": [],
  "extension_points": [],
  "python_dependencies": ["pandas>=2"],
  "server": {"module": "server", "plugin": "plugin:Plugin"},
  "app": {"entry": "dist/index.js"}
}
```

| Campo | Significato |
|---|---|
| `name` | Lettere minuscole, cifre e `_`, inizia con una lettera (né `""`, né `..`, né separatori, né `_` iniziale). Diventa anche il nome del modulo Python `soup_pkg_<name>`. |
| `version` | Versione PEP 440 (`1.0.0`). Serve per gli aggiornamenti. |
| `api_version` | Versione dei contratti del core per cui il package è scritto, `"MAGGIORE.MINORE"`. È compatibile se ha lo stesso numero maggiore di `CONTRACTS_API_VERSION` dell'host e un minore uguale o inferiore: un host `"2.1"` accetta `"2.0"` e `"2.1"`, rifiuta `"2.2"`, `"1.x"` e `"3.0"`. |
| `label`, `description`, `author` | Testi mostrati all'utente; `label` vale `name` se assente. |
| `requires` | Package che devono essere attivi prima di questo. |
| `requires_tools` | Tool usati (catalogo, Memgraph, storage, preferenze...). Un package non può usare un tool che non dichiara qui. |
| `provides_tools` | Tool che il package aggiunge con `ctx.add_tool`. Registrare un tool non dichiarato qui è un errore. |
| `extension_points` | Punti di estensione che il package apre con `ctx.add_extension_point` (es. `"ekg.build_steps"`). Aprirne uno non dichiarato è un errore. |
| `python_dependencies` | Requisiti PEP 508 (`"pandas>=2"`). Vengono **verificati**, mai installati: se una libreria manca o ha la versione sbagliata il package viene escluso con un messaggio che lo dice. Le librerie vanno aggiunte all'immagine del server (`soup-server/requirements.txt`). |
| `server.module` | Cartella del modulo Python, relativa al package (di solito `server`). |
| `server.plugin` | `"modulo:Attributo"` dentro `server.module`: una sottoclasse (o un'istanza) di `SoupPlugin`. |
| `app.entry` | Facoltativo: bundle del frontend, relativo a `app/`. |

Il manifest è la **fonte di verità**: nome, versione, `api_version`, `requires`, `requires_tools`,
`provides_tools` ed `extension_points` vengono impostati sull'istanza del plugin, che quindi non li
ripete:

```python
from soup.core.contracts import PluginContext, SoupPlugin

from .reader import CsvEventLogReader


class Plugin(SoupPlugin):
    def register(self, ctx: PluginContext) -> None:
        ctx.add_input_reader(CsvEventLogReader.format_id, CsvEventLogReader())
```

## Nomi dei contributi

- Importer, operazioni, visualizzatori ed exporter hanno un `id` unico **solo dentro il package**:
  il core li registra con la chiave `"<package>.<id>"` (es. `csv_reader.csv`), ed è questa chiave
  completa che usano i router, le API e `created_by.contributor_id` degli oggetti. Due package
  possono quindi offrire entrambi un importer `csv`: per un file `.csv` compaiono tutti e due e
  sceglie l'utente.
- Tool e punti di estensione hanno invece un **nome globale**, perché servono a più package
  (`memgraph`, `storage`, `ekg.build_steps`): vanno dichiarati nel manifest, e due package attivi
  non possono dichiarare lo stesso nome. Il conflitto viene rilevato prima di importare codice e
  nomina entrambi i package; il primo caricato (o quello già attivo) mantiene il nome.

## Regole per il codice del package

- Dell'host si importa solo `soup.core.contracts`; i file interni del package si importano con
  import relativi (`from .reader import ...`).
- Il modulo `server/` viene importato con un nome isolato, `soup_pkg_<nome>`, quindi due package
  possono avere file con lo stesso nome.
- Un altro package si usa solo tramite la sua API pubblica, `soup_pkg_<altro>.api`, e solo se
  `<altro>` è elencato in `requires` (così viene caricato prima). Altrimenti si comunica tramite
  tool, punti di estensione (`add_extension_point` / `contribute`) ed eventi (`EventBus`).
- La parte `app/` non importa codice dell'host: ogni visualizzatore è un custom element che riceve
  `data` e `context` e comunica con l'host tramite `context` ed eventi DOM.

## Dove vengono cercati

- `SOUP_PACKAGES_PATH`: elenco di cartelle separate da `os.pathsep` (`:` su Linux e in Docker, `;`
  su Windows). Default: questa cartella e la cartella dei package installati.
- `SOUP_INSTALLED_PACKAGES_DIR`: dove `install` estrae gli zip e dove si salva lo stato
  (`_state.json`); viene sempre aggiunta al path. Default `soup-server/instance/packages`, in Docker
  `/data/soup-packages` (volume `soup-installed-packages`).
- Se lo stesso nome compare in due cartelle vince la versione più alta.
- `SOUP_PACKAGES`: elenco esplicito dei package da attivare all'avvio (vuoto = nessuno). Se
  assente, sono attivi tutti quelli trovati tranne quelli disabilitati dall'utente.
  `SOUP_PLUGINS` è ancora letto come vecchio nome.

## Ciclo di vita

All'avvio, prima di importare qualsiasi codice, il `PackageManager` verifica manifest,
`api_version`, `python_dependencies` e `requires` (con ordinamento topologico e rilevamento dei
cicli). Un package che fallisce finisce nel report con il motivo e non blocca gli altri (salvo
`SOUP_STRICT=true`).

Install, enable, disable e uninstall avvengono mentre il server risponde ad altre richieste: i
registri del core sono copy-on-write, quindi chi legge vede sempre uno stato coerente.

A runtime, via `/api/v3/packages`:

| Operazione | HTTP | Note |
|---|---|---|
| Elenco | `GET /api/v3/packages` | stato `active`, `disabled` o `failed`, con errore e dipendenti |
| Installa | `POST /api/v3/packages` (multipart `file`) | Zip con il manifest alla radice o in un'unica cartella di primo livello. Rifiutati: zip oltre 50 MB (200 MB estratti), percorsi che escono dalla cartella, link simbolici, manifest non validi, librerie Python mancanti, `requires` non attivi. Un nome già usato da un package fornito richiede una versione superiore e `allow_override=true`; un package installato si aggiorna solo a una versione superiore. Il package viene caricato subito; se il caricamento fallisce si torna alla versione precedente. |
| Disabilita | `POST /api/v3/packages/<nome>/disable` | Toglie i contributi senza riavvio. `409` con `dependents` se altri package attivi ne hanno bisogno; `cascade=true` disabilita anche quelli. |
| Abilita | `POST /api/v3/packages/<nome>/enable` | `409` se un package richiesto non è attivo. |
| Disinstalla | `DELETE /api/v3/packages/<nome>` | Solo package installati (quelli forniti si disabilitano). Gli oggetti creati dal package restano nel workspace, segnalati come `package_status: "missing"`. |

Un oggetto il cui package non è attivo (disabilitato o disinstallato) non si cancella normalmente,
perché nessuno può eliminarne i dati: la cancellazione risponde `409` con l'elenco dei package
coinvolti. Si può riattivare il package, oppure usare `force=true`, che toglie l'oggetto solo dal
catalogo e lo annota in `<cartella dei package installati>/orphaned-data.json` (oggetto con la sua
`meta`, package, contributore e data), così i dati rimasti si possono ripulire in seguito.

Installazione e disinstallazione rispondono `403` se `SOUP_ALLOW_PACKAGE_INSTALL` non è `true`.
Lo stato abilitato/disabilitato si conserva tra i riavvii.

## Creare uno zip

```sh
cd soup-packages && zip -r my_package.zip my_package -x '*/__pycache__/*'
curl -F file=@my_package.zip http://localhost:8080/api/v3/packages
```
