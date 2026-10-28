# ekg_views

Package fornito e attivo di default: visualizzatori **Grafo**, **Statistiche** e **Interrogazioni**
ed exporter **JSON del grafo** per gli oggetti di kind `ekg`, con i punti di estensione
`ekg.graph_views`, `ekg.queries` ed `ekg.json_parts`. Contratti, azioni e formati sono descritti
nella sezione "Viste dell'EKG" di [../README.md](../README.md).

`requires: ["ekg", "soup_base"]`, `requires_tools: ["memgraph", "storage"]`. Ogni contributo
chiama prima `ensure_loaded(obj, tools)` del package `ekg`.

Ogni vista, interrogazione e parte dichiara i kind a cui si applica (`kinds`, `kinds.py`): quelle di
ekg_views valgono per `ekg` ed `ekg_class` (il grafo aggregato contiene anche l'EKG del padre).
Interrogazioni e JSON del grafo accettano `ekg_class` solo mentre un package (`ekg_class_graph`)
contribuisce qualcosa di dedicato a quel kind; Grafo e Statistiche restano per `ekg`.

## Come sono scritte le query

- **Etichette e tipi nel pattern**, come il vecchio `MATCH (e1:Event)-[r:DF]->(e2:Event) ... LIMIT`:
  `MATCH (n:`Event`)`, `MATCH (a:`Event`)-[r:`DF`]->(b:`Event`)`, `MATCH ()-[r:`CORR`]->()`, così
  Memgraph legge solo i nodi e gli archi che servono. Vengono **solo da liste chiuse**: le
  `relationships` di una `EdgeListGraphView` (`{tipo: (etichetta sorgente, etichetta destinazione)}`)
  e i `node_label`/`relationship`/`source_label`/`target_label` di `CountQuery`, `NodeListQuery`,
  `RelationshipListQuery`, `NodesPart` e `RelationshipsPart`, sempre attraverso `ident()`.
- **Le scelte dell'utente** (relazioni visibili, etichetta dei nodi cercati) vengono prima
  confrontate con quella lista (`ValidationError`, cioè `400`, se non ci sono) e servono solo a
  scegliere quale pattern costruire; più tipi diventano `[r:`DF`|`CORR`]`, e un estremo è
  etichettato quando tutti i tipi scelti concordano (DF e CORR partono entrambi da `Event`).
- **I valori** (testo della ricerca, id, offset, filtri delle interrogazioni) e il `LIMIT` restano
  parametri: `$text`, `$id`, `$offset`, `$limit`.
- **Niente `ORDER BY` globale** sugli archi del grafo e nei conteggi: `MATCH ... LIMIT $limit`.
  `ORDER BY` resta solo dove si pagina con un offset: la ricerca incrementale del Grafo e le
  tabelle paginate di `NodeListQuery` e `RelationshipListQuery`.

## Test

- `pytest` da `soup-server/` raccoglie `tests/test_*.py` (FakeDatabase, niente Docker): blocchi di
  ogni interrogazione, pattern etichettato atteso nel testo di ogni query generata e nessun valore
  dell'utente, relazioni ed etichette non dichiarate rifiutate con `400`, nomi da quotare passati
  da `ident()`, estensibilità con un package di prova scritto su disco.
- `npm test` dalla radice di `soup-packages`: gli elementi `<soup-pkg-ekg-graph>`,
  `<soup-pkg-ekg-stats>`, `<soup-pkg-ekg-queries>` con un context finto.
- `tests/memgraph_smoke.py` (non raccolto da pytest) esegue ogni query generata contro un Memgraph
  vero, su un piccolo EKG di esempio, e riporta quelle che falliscono (codice di uscita 1):

  ```sh
  docker run -d --rm --name ekg-views-smoke -p 17687:7687 memgraph/memgraph-mage:3.13.2
  cd soup-server
  python ../soup-packages/ekg_views/tests/memgraph_smoke.py            # default bolt://localhost:17687
  docker stop ekg-views-smoke
  ```

  Lo script **svuota il database**: non va mai puntato su un Memgraph con dati da conservare.
  L'immagine è la stessa di `docker-compose.yaml` (`memgraph/memgraph-mage:3.13.2`, Memgraph 3.13.2): se si
  aggiorna il tag lì, va aggiornato anche qui e lo script rieseguito (lo controlla
  `soup-server/tests/test_cypher_compatibility.py`). Ultima esecuzione: `43/43 queries ok` (anche su
  `memgraph/memgraph-platform` 2.14.1).

## Verifica con Memgraph

Passi manuali con l'intero stack (`docker compose` dalla radice del repository):

1. `docker compose up --build`, poi apri `http://localhost:4200`. In `/packages`, `ekg_views` è
   `active` e il suo bundle è caricato senza errori.
2. **Import.** In `/import` trascina un CSV di event log (per esempio
   `soup-server/tests/fixtures/sample_event_log.csv`), scegli **CSV come event log (EKG su
   Memgraph)**, indica `event_id`, `timestamp`, `activity` e almeno una colonna in `entities`, poi
   importa. Nel workspace compare un oggetto `ekg`.
3. **I tre visualizzatori.** Apri l'oggetto: compaiono **Grafo**, **Statistiche** e
   **Interrogazioni** (e nessun visualizzatore EKG su un oggetto `table` o `text`).
   - **Grafo**: viene disegnato con al massimo 200 archi DF e la barra indica il massimo mostrabile.
     Cambia il limite, attiva CORR (compaiono le entità), torna alla sola DF, cambia la forma dei
     nodi. Dopo il primo disegno, tornando al workspace, l'oggetto ha l'anteprima. "Esporta SVG"
     scarica `<nome>.svg`.
   - **Statistiche**: conteggi uguali a quelli della config del dataset, primo e ultimo timestamp,
     attività distinte, tipi di entità con l'avviso "N nodi hanno valore NaN." dove ci sono valori
     nulli, la torta della composizione e, se l'import ha salvato i tempi, quella dei tempi.
4. **Ricerca di nodi e archi.** Nel Grafo apri "Cerca": cerca un'attività tra i **Nodi** e scorri i
   risultati (le pagine successive arrivano scorrendo); seleziona un risultato non disegnato e
   verifica che il pannello mostri le sue proprietà. Passa ad **Archi**, cerca un tipo di entità e
   passa col mouse su un risultato per evidenziarne i nodi.
5. **Ogni interrogazione.** In **Interrogazioni** esegui una per una tutte le 20 voci di tutti i
   gruppi (Nodi, Relazioni, Conteggi, Attività, Entità, Tempo, Grafo), compilando i campi
   obbligatori (un tipo di entità, un'attività), cambiando `Righe` e `Dalla riga` nelle tabelle
   paginate: nessuna risponde con un errore e i conteggi coincidono con le Statistiche.
6. **Export JSON.** Dal menu di export dell'oggetto scegli **JSON del grafo** con tutte le parti:
   il file ha le chiavi `Event nodes`, `Entity nodes`, `CORR relationships` (`corr_data`,
   `corr_count`) e `DF relationships` (`df_data`, `df_count`), con i `Timestamp` come testo. Ripeti
   con una sola parte: il file ha solo quella chiave.
7. In Memgraph Lab (`http://localhost:3300`) puoi controllare i conteggi con
   `MATCH (n:Event) RETURN count(n)` e `MATCH ()-[r:DF]->() RETURN count(r)`.
