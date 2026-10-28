# Soup

![Angular](https://img.shields.io/badge/Angular-v18.2.0-DD0031?style=for-the-badge&logo=Angular&color=%23e61919)
![Python](https://img.shields.io/badge/Python-3.11.5-3776AB?style=for-the-badge&logo=Python&color=blue)
![Memgraph](https://img.shields.io/badge/Memgraph-v3.13.2-000000?style=for-the-badge&color=orange)

## Description
**SOUP** is a web application for **object-centric process mining**. Starting from a `.csv` file of
object-centric event data, it builds an **Event Knowledge Graph (EKG)** on Memgraph and lets you
explore, filter, aggregate and export it.

Every feature of SOUP comes in a **package**: a folder holding a feature's backend and frontend
together, which can be installed at runtime.

---

## Architecture

```
soup-app/        host frontend (Angular 18): workspace, import, object page, packages page
soup-server/     host backend (Python/Flask)
  soup/core/     the mediator: loads packages, registers their contributions, routes requests,
                 keeps the workspace of objects, the EventBus and the tools
  soup/api/      the HTTP layer (/api/v3), the only module that imports Flask
soup-packages/   the packages (server/ + app/ each) and @soup/sdk, the frontend SDK
```

- **The core is only a mediator.** It knows typed objects, contributions, tools, extension points
  and events. It does not import pandas, neo4j, docker or Flask, and holds no Cypher, event log,
  EKG or filter code. All of that lives in packages.
- **Everything is a typed object** `{id, name, kind, created_by, parents, meta}` in the workspace.
  Each kind of contribution works with objects as follows:

  | Contribution | What it does with objects |
  |---|---|
  | Importer | Creates objects from a file. Several importers can accept the same extension with different results; the user chooses. |
  | Operation | Takes objects of some kinds and produces new objects, derived from them. |
  | Visualizer | Shows objects of the kinds it accepts. |
  | Exporter | Writes objects of the kinds it accepts to a file. |

  For each object only the contributions that accept its kind are offered. When there are
  several, the user chooses.
- **Memgraph, file storage, the object catalog and the preferences are tools** provided by
  packages. A package can only use the tools it declares in `requires_tools`.
- **Packages talk only through:**
  - the core contracts (`soup.core.contracts`);
  - tools;
  - extension points (`add_extension_point` / `contribute`);
  - events (EventBus);
  - the public `api.py` of another package, and only one listed in `requires`.
- **The frontend host contains no visualizer.** Every visualizer is a Web Component (custom
  element) defined in its package's `app/` bundle and loaded at runtime with `import()` from the
  URL the backend serves. It receives `data` and `context` and talks to the host only through
  `context` and DOM events. Packages import only `@soup/sdk`, never host code.

### SOUP and ProM

SOUP follows the plug-in model of [ProM](https://promtools.org/):

| ProM | SOUP |
|---|---|
| Package (plug-ins installed by the Package Manager) | Package in `soup-packages/` or installed from a zip at `/packages` (`soup-package.json`, `server/`, `app/`) |
| Object pool (provenance of the objects) | Workspace (`/workspace`): typed objects with `parents`, derived objects shown under their sources |
| `@Plugin` with input/output types | Operation (`inputs` by kind → `produces` kinds) |
| Import plug-in | Importer (by extension; the user picks among several) |
| `@Visualizer` | Visualizer = Web Component of the package (`/o/:id`, chosen per kind and remembered) |
| Export plug-in | Exporter (download from the object page) |
| Shared services, plug-in extensions | Tools (`requires_tools`), extension points and EventBus events |

### Shipped packages

| Package | Importers | Operations | Visualizers | Exporters | Tools, extension points, events |
|---|---|---|---|---|---|
| `tool_memgraph` | | | | | provides tool `memgraph` (Cypher with `Query`/`ident`, active graph) |
| `tool_storage` | | | | | provides tools `storage`, `catalog`, `preferences` |
| `soup_base` | | | Report (`report`) | Report in JSON | shared elements (`soup-table`, `soup-chart`, `soup-graph-view`, ...) |
| `text` | Text (`.txt`, `.md`, `.log`) | | Text | Original file (with its own extension) | uses `storage` |
| `csv_table` | CSV as table (`.csv`, `.tsv`) | Column distribution | CSV table, Column profile | CSV | uses `storage` |
| `ekg` | | Load into Memgraph | | | extension points `ekg.build_steps`, `ekg.state_providers`; events `ekg.before_reset`, `ekg.built` |
| `csv_ekg` | CSV as event log (EKG on Memgraph): column mapping, trigger/target, multiplicity diagram | Convert to EKG (`table` → `ekg`) | | | uses `memgraph`, `storage` |
| `causal_df` | | | | | contributes the causal `:DF` step to `ekg.build_steps` |
| `ekg_views` | | | Graph, Statistics, Queries | Graph JSON | extension points `ekg.graph_views`, `ekg.queries`, `ekg.json_parts` |
| `ekg_analysis` | | New analysis, Import analysis configuration, Configuration example | Process indicators | Analysis configuration | extension point `ekg.analysis_filters` (6 filters); event `analysis.before_apply` |
| `ocel` | OCEL 2.0 as tables (`.json`, `.jsonocel`, kind `ocel_tables`), OCEL 2.0 as EKG on Memgraph | Decompose into EKG (`ocel_tables` → `ekg`) | OCEL tables, OCEL summary | OCEL 2.0 JSON | uses `storage` (tables), `memgraph` (EKG) |
| `ekg_class_graph` | | Build aggregated graph (`ekg` → `ekg_class`) | Aggregated graph, Aggregated graph statistics | | contributes a view, queries and JSON parts; subscribes to `ekg.before_reset`, `analysis.before_apply` |

Details of every package, of the tools and of the extension points are in
[soup-packages/README.md](soup-packages/README.md). That page also has the guide
"Scrivere un package", with a complete example of each kind of contribution.

---

## Start the tool via Docker

Install [Git](https://git-scm.com/downloads) and [Docker](https://www.docker.com/get-started/), then
from a terminal:

```
git clone https://github.com/soup-ocpm/soup.git
cd soup
docker compose -p soup-tool up --build
```

(Older Docker versions: `docker-compose -p soup-tool up --build`.)

| Container | Description | Access point |
|---|---|---|
| **soup-app** | Frontend (nginx; `/api/` is proxied to the backend) | [http://localhost:4200](http://localhost:4200) |
| **soup-engine** | Backend `/api/v3` and the package bundles | [http://localhost:8080](http://localhost:8080) |
| **soup-database** | Memgraph (`memgraph/memgraph-mage:3.13.2`), with the `soup-volume` volume on `/soup` | `7687` (Bolt), `7444` |
| **soup-lab** | Memgraph Lab (`memgraph/lab:3.13.2`) | [http://localhost:3300](http://localhost:3300) |

### Memgraph

`docker-compose.yaml` pins **Memgraph 3.13.2**: `memgraph/memgraph-mage:3.13.2` (Memgraph with the MAGE
procedures) and `memgraph/lab:3.13.2` (the web interface) as two services. The image used before,
`memgraph/memgraph-platform` without a tag, is deprecated: its `latest` has stayed at Memgraph 2.14.1
(February 2024), which does not implement list and pattern comprehensions (`[x IN list | expr]`).
The packages never use them (`soup-server/tests/test_cypher_compatibility.py` checks it) and run on
2.14.1 too. Update the two tags together, then run the smoke tests of `ekg_views` and `ekg_analysis`
against the new image (their READMEs).

To read the version of the running Memgraph, run `SHOW VERSION;` in Memgraph Lab or with mgconsole:

```sh
echo "SHOW VERSION;" | docker exec -i soup-database mgconsole
```

The `memgraph/memgraph-mage` image runs as the unprivileged `memgraph` user: `tool_storage` runs its
commands in the container as root (`docker exec --user root`), so it can write in the `soup-volume`
volume, and leaves the files readable by Memgraph for `LOAD CSV`. The volume keeps the datasets of an
existing installation; the graph itself is rebuilt from them when an object is opened.

The backend image builds every package frontend (`npm ci && npm run build:packages`). Packages
installed at runtime are stored in the `soup-installed-packages` volume.

**Pages:**

| Page | What it does |
|---|---|
| `/welcome` | Shows the state of the tools (`/api/v3/health`). |
| `/import` | Choose a file and an importer. |
| `/workspace` | The objects: search, rename and describe, delete. |
| `/o/:id` | One object: its visualizers, its operations ("Azioni") and its exporters. |
| `/packages` | Install, enable, disable and remove packages. |

The addresses of the old interface still work as redirects:

| Old address | Goes to |
|---|---|
| `/new-dataset` | `/import` |
| `/datasets` | `/workspace` |
| `/datasets/<name>` and `/datasets/<name>/graph` | `/o/<id>` of that dataset |
| `/datasets/<name>/<analysis>/graph` | `/o/<id>` of that analysis |

---

## Tests

```sh
# backend and the Python tests of the packages (FakeDatabase and in-memory storage: no Docker)
cd soup-server && pip install -r requirements-dev.txt && python -m pytest
# with the coverage, and the static analysis of the backend (pyproject.toml)
python -m pytest --cov
python scripts/lint.py               # ruff, vulture, mypy --strict (soup/ and every package's server/)
python scripts/lint.py --counts      # the number of messages per area
python scripts/metrics.py            # lines, files, ruff warnings, cyclomatic complexity (max, mean, > 10)

# packages: lint (eslint, knip, tsc), unit tests (vitest/jsdom), type check and bundles
cd soup-packages && npm install && npm run lint && npm test && npm run build:packages

# host frontend: lint (ng lint, knip, tsc), build (with type check), unit tests (Chrome headless), end to end (Playwright)
cd soup-app && npm install && npm run lint && npm run build && npm run test:v3 && npm run e2e
```

`soup-server/tests/test_architecture_boundaries.py` checks the boundaries statically:

- the core imports none of pandas, neo4j, docker and Flask;
- `soup/api` is the only module that imports Flask;
- packages import other packages only through the `api.py` of packages they `require`;
- packages use only the tools and libraries they declare;
- `soup-app` imports from `soup-packages` only the SDK;
- no package imports host code;
- no frontend code calls `/api/v2`;
- one `ParsedCache` (soup_base's) and one DOM helper `h()` (the SDK's) for every package.

`tests/test_contributions_contract.py` checks that every contribution of the default packages
honours the contract of its base class (Importer, Operation, Visualizer, Exporter, Tool): declared
attributes, required methods implemented, overrides with the parameters of the base, unknown
actions answered with `NotFoundError`, valid `file_type()` and `health()`.
`tests/test_cypher_compatibility.py` checks that no query uses what the Memgraph of
`docker-compose.yaml` does not implement.

The limits of the code (ruff: complexity 10, PL rules; eslint: `complexity` 10 and
`max-lines-per-function` 60, not for tests) are reported by the lint scripts; the exceptions are
marked in the code with `noqa` and the reason (public signatures, the ekg runtime, the imports of
the storage backends chosen at runtime).

`tests/test_legacy_routes.py` compares the served routes with `tests/fixtures/api_v3_routes.json`.
To regenerate the fixture: `python -m tests.tools.dump_v3_routes`.

---

## Environment variables

| Variable | Default | Read by | Meaning |
|---|---|---|---|
| `SOUP_PACKAGES` | absent: every package found | host | Comma-separated packages to activate at startup (empty = none). |
| `SOUP_PACKAGES_PATH` | `soup-packages/` + installed dir | host | Folders where packages are searched (`os.pathsep`-separated). |
| `SOUP_INSTALLED_PACKAGES_DIR` | `soup-server/instance/packages` (Docker: `/data/soup-packages`) | host | Where zips are extracted and the enabled/disabled state is kept. |
| `SOUP_ALLOW_PACKAGE_INSTALL` | `false` (`true` in `docker-compose.yaml`) | host | Allows installing and uninstalling packages at runtime. |
| `SOUP_STRICT` | `false` | host | A package that fails to load stops the startup. |
| `SOUP_MAX_UPLOAD_MB` | `200` | host | Maximum request body of `/api/v3` (413 above). |
| `MEMGRAPH_HOST`, `MEMGRAPH_PORT` | `memgraph`, `7687` | `tool_memgraph` | Memgraph connection. |
| `SOUP_STORAGE_KIND` | `docker` | `tool_storage` | `docker` (files in the Memgraph container volume `/soup`, so `LOAD CSV` reads them) or `local`. |
| `SOUP_CONTAINER_NAME` | `soup-database` | `tool_storage` | Container of the `docker` storage. |
| `SOUP_LOCAL_STORAGE_ROOT` | `/soup` | `tool_storage` | Root of the `local` storage. |
| `SOUP_EKG_VIEWS_MAX_LIMIT` | `2000` | `ekg_views` | Maximum number of graph elements drawn. |
| `SOUP_TEXT_CACHE_OBJECTS`, `SOUP_TEXT_CACHE_MB` | `8`, `200` | `text` | In-memory cache of the decoded files. |
| `SOUP_CSV_TABLE_CACHE_OBJECTS`, `SOUP_CSV_TABLE_CACHE_MB` | `8`, `200` | `csv_table` | In-memory cache of the parsed tables. |
| `SOUP_OCEL_CACHE_OBJECTS`, `SOUP_OCEL_CACHE_MB` | `8`, `200` | `ocel` | In-memory cache of the tables of the OCEL logs. |

---

## Security of runtime installation

A package runs code with the privileges of the server (its `server/` part, in the Flask process)
and of the browser (its `app/` part, loaded in the page). **Install only packages you trust.**

- **Installation is off by default.** Installing or uninstalling answers `403` unless
  `SOUP_ALLOW_PACKAGE_INSTALL=true`. The development `docker-compose.yaml` enables it; turn it off
  for a shared deployment.
- **Zips are validated before any code is imported.** Rejected:
  - zips over 50 MB, or over 200 MB extracted;
  - paths that leave the package folder, and symbolic links;
  - invalid manifests and invalid names (no `""`, `..`, separators or leading `_`);
  - an incompatible `api_version` (the contracts are at `4.0`);
  - missing `python_dependencies` (checked, never installed);
  - `requires` that are not active.
- **Overriding a shipped package** requires a higher version and `allow_override=true`. A failed
  load rolls back to the previous version.
- **Only a package's `app/dist` is served to the browser.** A path leaving it answers `404`.
- **Inside a package**, the core enforces at runtime:
  - a tool not declared in `requires_tools` cannot be reached (`ToolNotDeclaredError`);
  - an extension point or tool not declared in the manifest cannot be registered.
- **Package code must follow these rules:**
  - Cypher always travels as a `Query` with parameters;
  - identifiers go through `ident()`;
  - operators come from closed lists;
  - `LIMIT` is a parameter.

---

> [!TIP]
> Please refer to the project [wiki](https://github.com/soup-ocpm/soup/wiki) for all the details; you can also download some event logs [here](https://github.com/soup-ocpm/soup-validation).

> [!WARNING]
> Make sure your `.csv` file **does not contain spaces** in the column headers to avoid parsing issues.

> [!NOTE]
> **Timestamp Format Requirements**: Memgraph accepts the following timestamp formats (with optional milliseconds): `YYYY-MM-DDThh:mm:ss` or `YYYY-MM-DDThh:mm` or `YYYYMMDDThhmmss` or `YYYYMMDDThhmm` or `YYYYMMDDThh`.

## Note
> 💭 Our tool is called _Soup_, with a logo showcasing a mix of rainbow noodles, symbolizing the dynamic and interconnected flow of object-centric process mining, much like the iconic image of rainbow spaghetti.

## Contact
* **Development support**: Alessio Giacché ✉️ ale.giacc.dev@gmail.com

* **Research activities**: Sara Pettinari ✉️ sara.pettinari@gssi.it & Lorenzo Rossi ✉️ lorenzo.rossi@unicam.it

## Feedback
We'd love to hear from you! Please share your feedback by filling out our form ➡️ [here](https://forms.gle/nBgZTeaDefTaYYkk9)
