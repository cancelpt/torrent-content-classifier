# Web App

## Run Local

```bash
npm install
npm run dev
```

Open `http://localhost:5173`, then drag and drop a `.torrent` file.

## What It Does

- Parses torrent metadata in-browser using `bencode`.
- Evaluates YAML rules in-browser.
- Shows kind/subtype/confidence and matched rule ids.

## Build

```bash
npm run build
```

## Custom Rules

Use the **Custom Rules YAML** picker on the page to load your own `.yaml` file.
