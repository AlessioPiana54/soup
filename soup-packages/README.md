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
  "name": "csv_ekg",
  "version": "1.0.0",
  "api_version": "3.0",
  "label": "CSV come event log (EKG)",
  "description": "Imports CSV files as event logs and builds their EKG on Memgraph.",
  "author": "SOUP",
  "requires": ["ekg", "soup_base", "csv_table"],
  "requires_tools": ["memgraph", "storage"],
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
| `api_version` | Versione dei contratti del core per cui il package è scritto, `"MAGGIORE.MINORE"`. È compatibile se ha lo stesso numero maggiore di `CONTRACTS_API_VERSION` dell'host e un minore uguale o inferiore: un host `"3.1"` accetta `"3.0"` e `"3.1"`, rifiuta `"3.2"`, `"2.x"` e `"4.0"`. L'host attuale è `"3.0"`: il passaggio da `"2.0"` (commit 8) ha tolto da `PluginContext` `add_input_reader`, `add_input_handler` e `add_build_step`, quindi un package `"2.x"` va aggiornato (gli step EKG si contribuiscono a `ekg.build_steps`). |
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

from .contributions import CsvEkgImporter, TableToEkg


class Plugin(SoupPlugin):
    def register(self, ctx: PluginContext) -> None:
        ctx.add_importer(CsvEkgImporter())
        ctx.add_operation(TableToEkg())
```

## Nomi dei contributi

- Importer, operazioni, visualizzatori ed exporter hanno un `id` unico **solo dentro il package**:
  il core li registra con la chiave `"<package>.<id>"` (es. `csv_ekg.csv`), ed è questa chiave
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
| `text` | Importer **Testo** (`.txt`, `.md`, `.log`, kind `text`): il file resta com'è nello spazio `text` dello storage, la `meta` ha dimensione, righe e codifica (UTF-8, altrimenti Latin-1). Visualizzatore **Testo** (`<soup-pkg-text-viewer>`): `<soup-text>` o, per i `.md`, `<soup-markdown>`; blocchi di righe con l'azione `lines` `{from, count}` e ricerca in tutto il file con `search` `{query}`. Exporter **File originale** (scarica `<nome>.txt`: l'estensione di un exporter è fissa). |
| `csv_table` | Importer **CSV come tabella** (`.csv`, `.tsv`, kind `table`, modulo `csv`): separatore (`comma`, `semicolon`, `tab`) e intestazione proposti da `csv.Sniffer`; la tabella è salvata come CSV canonico nello spazio `csv_table`. Visualizzatori **Tabella CSV** (`<soup-pkg-csv-table-viewer>`, paginazione remota con l'azione `page` `{offset, limit, sort: {column, direction}, filter: [{column, value}], search}`, colonne per indice, ordinamento e un filtro per colonna) e **Profilo colonne** (`<soup-pkg-csv-profile>`, valori distinti, celle vuote, esempi e il grafico di `distribution` `{column, top}`). Operazione **Distribuzione di una colonna** (`table` → `report` con un grafico a barre e una tabella). Exporter **CSV** con separatore e intestazione a scelta. |
| `ekg` | Solo server. L'event log (`Table` e conversioni pandas, `EventLogData` piatto o separato, `ColumnMapping`, `EventLog` con normalizzazione, millisecondi, entità e CSV canonici), i dataset sul volume (`/soup/<nome>/<nome>.csv`, `_entity.csv`, `_config.json`, `Analyses/`) e l'EKG su Memgraph: step di costruzione 100-500, il punto di estensione `ekg.build_steps`, lo stato del grafo degli oggetti `ekg` (`ensure_loaded`, `ekg.state_providers`), gli eventi `ekg.before_reset` ed `ekg.built`, l'operazione **Carica in Memgraph**. All'avvio aggiunge al catalogo i dataset già presenti sul volume. Vedi sotto. |
| `csv_ekg` | Importer **CSV come event log (EKG su Memgraph)** (`.csv`, kind `ekg`): anteprima, campi `event_id`, `timestamp`, `activity`, `entities`, `values`, `trigger_target`, `save_process_times` e, con almeno due colonne entità, il grafo delle molteplicità (1 a 1, 1 a N, N a 1, N a N). Operazione **Converti in EKG** (`table` di `csv_table` → `ekg` figlio). Serve anche `POST /api/v2/graph`. |
| `causal_df` | Lo step del `:DF` causale per le coppie trigger/target, contribuito a `ekg.build_steps` con order 450. |

`text` e `csv_table` usano solo la libreria standard di Python e il tool `storage` (`requires:
["soup_base", "tool_storage"]`, `requires_tools: ["storage"]`, niente pandas né Memgraph): sono
l'esempio di un package che tiene i propri dati in uno spazio dello storage, li rilegge nelle azioni
dei visualizzatori e li rimuove in `dispose`.

Per non rileggere il file a ogni pagina, ordinamento, filtro o blocco di righe (con
`DockerVolumeStorage` ogni lettura copia il file fuori dal container), ognuno dei due tiene una cache
in memoria del contenuto già analizzato (`server/cache.py`: righe decodificate per `text`, colonne e
righe per `csv_table`), con chiave l'id dell'oggetto. È una LRU limitata per numero di oggetti e per
dimensione stimata, thread-safe, creata dal `Plugin` in `register()` e condivisa dai suoi contributi:
non c'è stato globale di modulo, e un disable/enable riparte da una cache vuota (`on_shutdown` la
svuota). `dispose` e ogni scrittura del file invalidano l'oggetto; un file la cui stima supera il
limite di dimensione non entra in cache e si legge ogni volta. Limiti: `SOUP_TEXT_CACHE_OBJECTS`,
`SOUP_TEXT_CACHE_MB`, `SOUP_CSV_TABLE_CACHE_OBJECTS`, `SOUP_CSV_TABLE_CACHE_MB` (default 8 oggetti e
200 MB per package; un valore non intero positivo fa fallire il caricamento del package con un
messaggio che lo dice). L'`api.py` dei due package espone i contributi e la cache. Nota per chi scrive campi `select`: un valore fatto solo
di spazi (come `"\t"`) è considerato vuoto dalla validazione del core, per questo il separatore di
`csv_table` usa i nomi `comma`, `semicolon`, `tab`.

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
| `tool_storage` | `storage` | `space(namespace)` → `read`, `write`, `exists`, `delete`, `list` relativi a `<root>/<namespace>/`, e `subspace(nome)` per una cartella al suo interno; `path_for(namespace, name)`; `delete_space(namespace)`; `namespaces()`, le voci della radice con un nome valido. | `SOUP_STORAGE_KIND` (`docker` o `local`), `SOUP_CONTAINER_NAME` (`soup-database`), `SOUP_LOCAL_STORAGE_ROOT` (`/soup`) |
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

## EKG: il package `ekg`

Un oggetto di kind `ekg` è un grafo su Memgraph. La `meta` di un oggetto **radice** (un import, una
conversione) ha `dataset` (la cartella sul volume), `graph_key` (lo stato del tool `memgraph` quando
il suo grafo è quello caricato: un uuid generato da `build_ekg` o dall'adozione), `columns`, `mapping` (`event_id`, `timestamp`,
`activity`, `entities`, `values`), `trigger_target`, `counts`, `process_info` (stessa forma della
vecchia config), `date_created` e `source_format`. Un oggetto **derivato** (per esempio un'analisi)
ha kind `ekg`, tra i `parents` il suo oggetto `ekg` di partenza, e in `meta.state`
`{provider, spec}`: `provider` è la chiave di un `StateProvider` contribuito a `ekg.state_providers`,
che sa applicare `spec` al grafo del genitore.

L'API (`soup_pkg_ekg.api`, per chi elenca `ekg` in `requires`; chi chiama dichiara `memgraph` e
`storage` in `requires_tools` e passa i propri `tools`):

| Nome | |
|---|---|
| `build_ekg(obj, data, mapping, tools, *, dataset, description, all_columns, trigger_target, source_format, save_process_times)` | Normalizza `data` (`EventLogData`), salva il dataset (cartella `dataset` o, se assente, il nome dell'oggetto reso unico con `_2`, `_3`...), costruisce l'EKG e restituisce la `meta`. Lo stato del tool `memgraph` diventa una chiave nuova, restituita in `meta.graph_key`, anche con un `ObjectDraft` (da un'operazione, che non ha ancora un id): la prima apertura dell'oggetto non ricostruisce. Se la costruzione fallisce i file vengono rimossi. |
| `ensure_loaded(obj, tools, force=False)` | Lo stato di `obj` è `meta.graph_key`, o il suo id per un derivato o un oggetto senza chiave (`graph_key_of(obj)`). Se non è lo stato attivo (o con `force`): pubblica `ekg.before_reset`, ricostruisce il dataset della radice (risalendo i `parents`), applica in ordine gli stati dei derivati fino a `obj`, salva conteggi e tempi nella config e imposta di nuovo la stessa chiave. Restituisce `True` se ha ricostruito. |
| `dispose(obj, tools)` | Se `obj` è attivo pubblica `ekg.before_reset` e svuota il grafo; per una radice rimuove la cartella del dataset. |
| `BUILD_STEPS_POINT` (`"ekg.build_steps"`) | Step `EkgBuildStep` (`key`, `order`, `phase`, `applies(ctx)`, `execute(ctx, db)`) contribuiti con `ctx.contribute(BUILD_STEPS_POINT, step, key=step.key, order=step.order)`. Gli step del package: 100 eventi, 200 entità, 300 indici, 400 `:CORR`, 500 `:DF` (salta i tipi in `ctx.df_handled_types`). `phase` (`event`, `entity`, `corr`, `df`) decide in quali tempi della `process_info` finisce lo step. |
| `STATE_PROVIDERS_POINT` (`"ekg.state_providers"`) | `StateProvider` (`key`, `apply(spec, db)`). |
| `EKG_BEFORE_RESET`, `EKG_BUILT` | `"ekg.before_reset"` `{object, active, reason: build\|load\|dispose}` prima di svuotare o ricostruire; `"ekg.built"` `{object, dataset, counts}` dopo una costruzione. |
| `EKG_KIND`, `EventLogData`, `Table`, `ColumnMapping`, `EventLog`, `from_dataframe`, `to_dataframe`, `Query`, `ident` | |

All'avvio il package aggiunge al catalogo, come oggetti `ekg` creati dall'importer `csv_ekg.csv`, le
cartelle `/soup/<nome>/` con un `<nome>_config.json` non ancora presenti nel catalogo (stesso
`meta.dataset`), leggendo la `meta` dalla config; un errore (per esempio storage irraggiungibile)
finisce nel log e non ferma il package.

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
