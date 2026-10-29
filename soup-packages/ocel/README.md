# ocel

Package fornito e attivo di default: i file **OCEL 2.0** in JSON (`.json`, `.jsonocel`) come tabelle
(kind `ocel_tables`) o come EKG su Memgraph (kind `ekg`), i visualizzatori **Tabelle OCEL** e
**Riepilogo OCEL**, l'operazione **Scomponi in EKG** e l'exporter **OCEL 2.0 JSON**. Contratti e
formati sono descritti nella sezione "OCEL 2.0" di [../README.md](../README.md).

`requires: ["soup_base", "ekg", "ekg_views", "tool_storage"]`, `requires_tools: ["memgraph", "storage"]`,
`api_version: "4.1"`.

## Qualifier e relazioni oggetto-oggetto nell'EKG

Un EKG fatto da un log OCEL (importer **OCEL 2.0 come EKG su Memgraph** o **Scomponi in EKG**) ha,
oltre a eventi, entità, `:CORR` e `:DF`:

- la proprietà `qualifier` sulla `:CORR` di ogni relazione evento-oggetto che ne ha uno (se un evento
  è legato due volte allo stesso oggetto con qualifier diversi, vale il primo: la `:CORR` è una);
- una `(:Entity)-[:REL {qualifier}]->(:Entity)` per ogni relazione oggetto-oggetto, tra le entità dei
  due oggetti (un oggetto a cui nessun evento si riferisce non ha un `:Entity`, e le sue relazioni
  restano fuori). Il tipo è sempre `REL`: il qualifier è testo libero e sta solo nella proprietà,
  mai nel testo della query.

`graph.py` scrive due file nel dataset, accanto ai CSV canonici (`build_ekg(..., extra_files=...)`,
salvati come `<dataset>_ocel_qualifiers.csv` e `<dataset>_ocel_o2o.csv` ed elencati nella config):
`ocel_qualifiers.csv` (`event_id`, `object_id`, `object_type`, `qualifier`) e `ocel_o2o.csv`
(`source_id`, `source_type`, `target_id`, `target_type`, `qualifier`), con id e tipi normalizzati
come li scrive il package `ekg` (`normalize_text`). Li legge con `LOAD CSV` lo step
`OcelRelationshipsStep` (`step.py`), che ocel contribuisce a `ekg.build_steps`: alla prima
costruzione e a ogni ricostruzione del grafo. Senza i due file (un CSV) lo step non si applica.
`meta.ocel.in_graph` conta le `:CORR` con qualifier e le `:REL` dopo la costruzione.

### Ordine dello step: 420

| order | step | package |
|---|---|---|
| 100 | eventi (`LOAD CSV` → `:Event`) | ekg |
| 200 | entità (`LOAD CSV` → `:Entity`) | ekg |
| 300 | indici | ekg |
| 400 | `:CORR` | ekg |
| **420** | **qualifier sulle `:CORR`, `:REL` tra le entità** | **ocel** |
| 450 | `:DF` causale | causal_df |
| 500 | `:DF` | ekg |

Lo step ha bisogno delle `:Entity` (200) e delle `:CORR` (400) su cui mette il qualifier, quindi viene
dopo la 400; i passi `:DF` (450, 500) non leggono né `qualifier` né `:REL`, quindi può venire prima
di loro. 420 non è usato da nessun altro step: `soup-server/tests/test_build_step_orders.py`
controlla che gli `order` degli step dei package forniti siano tutti diversi, così la sequenza non
dipende mai dall'ordine di caricamento dei package.

### EKG importati prima

Gli EKG creati da un log OCEL prima di questa versione non hanno i due file nel dataset: restano
senza `:REL` e senza qualifier anche quando vengono ricostruiti. Per averli bisogna **reimportare il
file** con **OCEL 2.0 come EKG su Memgraph** o rifare **Scomponi in EKG** dalle sue tabelle. Le
**Statistiche** di questi oggetti lo dicono con un avviso (`OcelRelationshipsNotice`, contribuito a
`ekg.stats_notices` di ekg_views).

## Viste

In ekg_views: la vista **Grafo degli oggetti** (`object`) mostra le `:REL` (un colore per qualifier)
e, a richiesta, le `:CORR` con il loro qualifier; l'interrogazione **Qualifier delle relazioni**
(gruppo Relazioni) conta `:REL` e `:CORR` per qualifier; il **JSON del grafo** ha la parte
`REL relationships`.

## Test

- `pytest` da `soup-server/` (`tests/test_ocel_*.py`, FakeDatabase e storage locale in una cartella
  temporanea): i due file nel dataset, le query dello step dopo quelle delle `:CORR` e prima di quelle
  dei `:DF`, alla costruzione e alla ricostruzione, nessun qualifier nel testo delle query, nessuna
  query dello step per un CSV, l'avviso delle Statistiche per un EKG senza i file.
- `soup-packages/ekg_views/tests/memgraph_smoke.py` esegue le query dello step su un Memgraph vero
  (con le righe come parametro invece dei file) e controlla qualifier e `:REL`.

Con `docker compose`: importa `ordini.jsonocel` con **OCEL 2.0 come EKG su Memgraph**; nel **Grafo**
scegli **Grafo degli oggetti**: compaiono le relazioni `contains`, `shipped in`, `bills`, `pays`,
`placed by`; **Interrogazioni** → **Qualifier delle relazioni** dà i conteggi per qualifier.
