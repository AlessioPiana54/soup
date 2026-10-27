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
  app/                   frontend (facoltativo)
    package.json         workspace npm con le dipendenze (almeno @soup/sdk)
    tsconfig.json
    src/index.ts         definisce i Web Component dei visualizzatori
    dist/index.js        bundle generato da `npm run build:packages`
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
| `app.entry` | Facoltativo: bundle del frontend, relativo a `app/` e dentro `app/dist/` (es. `dist/index.js`): al browser si serve solo `app/dist`. |

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

## Package forniti

| Package | Contenuto |
|---|---|
| `tool_memgraph`, `tool_storage` | I tool (vedi sotto). |
| `soup_base` | Visualizzatore **Report** (kind `report`), exporter **Report in JSON** e gli elementi riusabili `soup-text`, `soup-markdown`, `soup-image`, `soup-table`, `soup-chart`, `soup-keyvalue`, `soup-file-link`, `soup-error`, `soup-report-view`, `soup-graph-view`. Disegna anche l'anteprima dell'import. Un package che usa questi elementi dichiara `requires: ["soup_base"]`. API in [soup_base/README.md](soup_base/README.md). |
| `csv_reader`, `causal_df` | Il lettore CSV e lo step EKG del grafo causale, per le pagine v2. |

## Tool forniti

Memgraph, i file, il catalogo degli oggetti e le preferenze non sono nel core: li forniscono due
package di soli tool (nessuna parte `app/`), attivi di default come tutti i package trovati. Un
package li usa dichiarandoli in `requires_tools` e prendendoli da `ctx.tools` (o dal `tools` passato
a importer, operazioni, visualizzatori ed exporter); chiedere un tool non dichiarato solleva
`ToolNotDeclaredError`. Per usare i tipi (`MemgraphTool`, `Query`, `StorageTool`...) si importa
l'`api.py` del package, che va allora elencato anche in `requires`. Senza uno di questi package il
server parte lo stesso: il report dei package dice quale tool manca e i servizi che ne hanno bisogno
rispondono `503`.

| Package | Tool | Cosa offre | Variabili d'ambiente |
|---|---|---|---|
| `tool_memgraph` | `memgraph` | `run(query) -> list[dict]`, `health()`; grafo attivo: `ensure_loaded(state_key, loader, force=False)`, `current_state()`, `clear()`, `invalidate()`. Un solo driver per processo, creato al primo uso e chiuso quando il package si ferma. | `MEMGRAPH_HOST` (`memgraph`), `MEMGRAPH_PORT` (`7687`) |
| `tool_storage` | `storage` | `space(namespace)` → `read`, `write`, `exists`, `delete`, `list` relativi a `<root>/<namespace>/`; `path_for(namespace, name)`; `delete_space(namespace)`. | `SOUP_STORAGE_KIND` (`docker` o `local`), `SOUP_CONTAINER_NAME` (`soup-database`), `SOUP_LOCAL_STORAGE_ROOT` (`/soup`) |
| `tool_storage` | `catalog` | Gli oggetti del workspace in `<root>/_catalog/objects/<id>.json`, anteprime SVG in `<root>/_catalog/thumbnails/<id>.svg`, `children(id)` per la provenienza. | come sopra |
| `tool_storage` | `preferences` | Chiavi/valori JSON in `<root>/_catalog/preferences.json`. | come sopra |

- **Grafo attivo.** Memgraph contiene un solo dataset alla volta. Chi deve interrogare un oggetto
  chiama `ensure_loaded(state_key, loader)`: se lo stato caricato è diverso da `state_key` (una
  stringa opaca scelta da chi chiama, es. l'id dell'oggetto) o se `force=True`, il tool svuota il
  database e chiama `loader(run)`; altrimenti non fa nulla. Se `loader` fallisce non resta attivo
  nessuno stato e la richiesta successiva ricarica.
- **Spazi dei nomi.** Ogni package usa il proprio spazio (`storage.space("<nome>")`); spazi e nomi di
  file sono validati come i nomi degli oggetti (vietati `""`, `..`, separatori, `_` iniziale), quindi
  `_catalog` è irraggiungibile. `path_for` dà il percorso assoluto per chi lo passa a Memgraph: `LOAD
  CSV` legge dallo stesso volume `/soup`. La cartella di un dataset EKG resta `/soup/<nome>/`.
- **Cypher.** `Query` e `ident` stanno in `soup_pkg_tool_memgraph.api`; i valori viaggiano sempre come
  parametri, gli identificatori passano da `ident()`.

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
| Elenco | `GET /api/v3/packages` | stato `active`, `disabled` o `failed`, con errore, dipendenti e contributi registrati (`contributions`) |
| Installa | `POST /api/v3/packages` (multipart `file`) | Zip con il manifest alla radice o in un'unica cartella di primo livello. Rifiutati: zip oltre 50 MB (200 MB estratti), percorsi che escono dalla cartella, link simbolici, manifest non validi, librerie Python mancanti, `requires` non attivi. Un nome già usato da un package fornito richiede una versione superiore e `allow_override=true`; un package installato si aggiorna solo a una versione superiore. Il package viene caricato subito; se il caricamento fallisce si torna alla versione precedente. |
| Disabilita | `POST /api/v3/packages/<nome>/disable` | Toglie i contributi senza riavvio. `409` con `dependents` se altri package attivi ne hanno bisogno; `cascade=true` disabilita anche quelli. |
| Abilita | `POST /api/v3/packages/<nome>/enable` | `409` se un package richiesto non è attivo. |
| File del frontend | `GET /api/v3/packages/<nome>/app/<percorso>` | Solo file di `app/dist` di un package attivo; ogni percorso che esce da `app/dist` (anche tramite link simbolici) risponde `404`. ETag basato sulla versione del package. |
| Manifest frontend | `GET /api/v3/frontend/manifest` | `[{name, version, module_url, requires}]` dei package attivi con parte `app`, ognuno dopo i package che richiede: l'host li importa in quest'ordine. |
| Disinstalla | `DELETE /api/v3/packages/<nome>` | Solo package installati (quelli forniti si disabilitano). Gli oggetti creati dal package restano nel workspace, segnalati come `package_status: "missing"`. |

Un oggetto il cui package non è attivo (disabilitato o disinstallato) non si cancella normalmente,
perché nessuno può eliminarne i dati: la cancellazione risponde `409` con l'elenco dei package
coinvolti. Si può riattivare il package, oppure usare `force=true`, che toglie l'oggetto solo dal
catalogo e lo annota in `<cartella dei package installati>/orphaned-data.json` (oggetto con la sua
`meta`, package, contributore e data), così i dati rimasti si possono ripulire in seguito.

Installazione e disinstallazione rispondono `403` se `SOUP_ALLOW_PACKAGE_INSTALL` non è `true`.
Lo stato abilitato/disabilitato si conserva tra i riavvii.

## Frontend: `@soup/sdk`

L'host Angular non contiene visualizzatori. Ogni visualizzatore è un **Web Component** (custom
element) definito nel bundle `app/dist/index.js` del suo package; l'host lo importa a runtime con
`import()` dall'URL `/api/v3/packages/<nome>/app/...`, nell'ordine del manifest frontend (ogni
package dopo quelli che richiede). Un bundle che fallisce non blocca gli altri: l'errore compare
nella pagina `/packages`. La parte `app/` dipende solo da `@soup/sdk` (`sdk/`, solo TypeScript,
nessun framework), mai dal codice dell'host.

- **Tipi condivisi**: `ObjectRef`, `Field` (i 13 tipi di campo), `Block` (i 9 tipi di blocco di
  `report.py`), `FileValue`, `ItemValue`.
- **Visualizzatori**: l'host crea l'elemento con il tag dichiarato in `Visualizer.element`, imposta
  `data` (la risposta di `data()`) e `context`, poi lo inserisce nella pagina. `VisualizerContext`:
  `object`, `theme`, `action(name, params)` (chiama `Visualizer.action` del proprio visualizzatore),
  `openObject(id)`, `notify(message, level)`, `setThumbnail(svg)` (anteprima mostrata nel workspace
  come immagine), `download(filename, mime, data)`.
- **Configurazione degli importer**: un importer con `config_element` sostituisce il form generico
  con un proprio elemento, che riceve un `ConfigContext`: `fields`, `columns` (colonne
  dell'anteprima), `value`, `preview(options)` e `emit(options)` per le opzioni dell'import.
- **Eventi DOM** verso l'host (bubbling, `composed`): `soup-thumbnail` `{svg}`, `soup-open-object`
  `{id}`, `soup-notify` `{message, level}`, `soup-config-change` `{value}`. I metodi del contesto
  li emettono: un elemento può usare indifferentemente gli uni o gli altri.
- **`defineSoupElement(tag, klass)`** registra l'elemento solo se il tag non esiste già, così un
  bundle ricaricato (dopo disable/enable) non fallisce. Un custom element non si può ridefinire: la
  nuova versione di un package già caricato nella pagina si usa dopo aver ricaricato la pagina
  (`/packages` lo segnala).
- Il testo che viene dai dati va inserito con `textContent`, mai come markup.

```ts
import { defineSoupElement, SoupVisualizerElement, VisualizerContext } from '@soup/sdk';

class MyViewer extends HTMLElement implements SoupVisualizerElement<MyData> {
  data!: MyData;
  context!: VisualizerContext;
  connectedCallback() { /* render this.data */ }
}

defineSoupElement('my-package-viewer', MyViewer);
```

## Build e zip

Dalla radice di `soup-packages` (workspace npm: `sdk` e l'`app/` di ogni package):

```sh
npm install                          # una volta, e dopo aver aggiunto un package con app/
npm run lint
npm test                             # unit test vitest (jsdom) di */app/test/
npm run build:packages               # SDK, poi type check + esbuild di ogni app/ -> app/dist/index.js (ES module unico, minificato, con sourcemap)
npm run build:packages -- my_package # solo alcuni package
npm run pack -- my_package           # dist/my_package-<versione>.zip: manifest, server/, app/dist/
curl -F file=@dist/my_package-1.0.0.zip http://localhost:8080/api/v3/packages
```

L'immagine Docker del server esegue `npm ci && npm run build:packages`, quindi i bundle dei package
forniti sono sempre aggiornati. Per partire da un esempio copia [`_template`](_template/README.md)
(un importer di file `.txt` e il suo visualizzatore).
