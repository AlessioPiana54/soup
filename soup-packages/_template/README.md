# Package di esempio (`_template`)

Package minimo da copiare per crearne uno nuovo: un importer `text` (file `.txt`, produce oggetti
di kind `template.text`), il suo visualizzatore, il Web Component `<soup-template-text>`, e
un'operazione `stats_report` che da un testo produce un oggetto `report` (disegnato da soup_base).
La cartella inizia con `_`, quindi la discovery la ignora: non viene mai caricata così com'è.

```
_template/
  soup-package.json     manifest ("name": "template")
  server/plugin.py      registra importer, visualizzatore e operazione
  server/text.py        TextImporter, TextVisualizer e l'operazione StatsReport
  app/package.json      dipendenze del frontend (@soup/sdk)
  app/tsconfig.json
  app/src/index.ts      il custom element, registrato con defineSoupElement
```

## Creare un package da questo

1. Copia la cartella: `cp -r _template my_package` (il nome della cartella è il nome del package).
2. In `soup-package.json` cambia `name`, `label`, `description`; in `app/package.json` cambia
   `name` (`soup-pkg-my-package-app`: due workspace npm non possono avere lo stesso nome).
3. Cambia gli `id`, il kind prodotto e il tag dell'elemento (`element` in Python e il tag passato
   a `defineSoupElement` devono coincidere e contenere un `-`).
4. Dalla radice di `soup-packages`: `npm install` (collega il nuovo workspace), poi
   `npm run build:packages -- my_package` e, per installarlo su un altro server,
   `npm run pack -- my_package` (crea `dist/my_package-1.0.0.zip`).

Per provare il template su un server: `npm run pack -- _template` e carica
`dist/template-1.0.0.zip` dalla pagina `/packages` (installazione abilitata con
`SOUP_ALLOW_PACKAGE_INSTALL=true`).
