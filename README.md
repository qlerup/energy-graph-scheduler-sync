# Energy Graph Scheduler — Sync

<img width="1024" height="125" alt="image" src="https://github.com/user-attachments/assets/c80bb31b-6c66-4228-9ceb-321b30022abf" />

This repo includes a Lovelace card (`energy-graph-scheduler-card.js`) that can sync “cheapest time” sections between all users/devices using a small Home Assistant backend integration.

## What is synced?

The card’s **sections** (the items you add under “Billigste tider”, e.g. “Dishwasher 3 hours”).

They are synced **per selected electricity price entity** (e.g. `sensor.electricity_price`).

## Domain

- Integration domain: `energy_graph_scheduler`

## Installation / Setup

1. Ensure these files are present:
   - `custom_components/energy_graph_scheduler/`
   - `www/energy-graph-scheduler-card.js`

2. Restart Home Assistant.

3. Add the integration:
   - Settings → Devices & Services → Add Integration → **Energy Graph Scheduler**

4. Add the card as a Lovelace resource (if you haven’t already):
   - URL: `/local/energy-graph-scheduler-card.js`
   - Type: `JavaScript module` (or `JavaScript` if you load it as a classic resource — the card avoids ESM imports)

## Enable sync in the card

In the card editor there is a toggle:

- **Sync (optional)** → “Share cheapest times between users”

When `sync` is enabled:

- The card loads sections from the HA backend (`.storage`).
- Changes are pushed live to other devices (websocket subscription).
- A polling fallback runs every 10 seconds, so updates still appear without a hard refresh even if websocket events don’t arrive (common on some mobile setups).

## Storage

The integration stores data in Home Assistant `.storage` using `homeassistant.helpers.storage.Store`.

Filename:
- `energy_graph_scheduler.json`

Data format (example):

```json
{
  "sections_by_entity": {
    "sensor.electricity_price": [
      {"name": "Dishwasher", "hours": 3},
      {"name": "Electric Car", "hours": 5}
    ]
  }
}
```

## Websocket API (internal)

The card uses these websocket calls:

- `energy_graph_scheduler/get_sections`
  - payload: `{ "entity_id": "sensor.electricity_price" }`
  - response: `{ "sections": [...] }`

- `energy_graph_scheduler/set_sections`
  - payload: `{ "entity_id": "sensor.electricity_price", "sections": [...] }`
  - response: `{ "ok": true }`

- `energy_graph_scheduler/subscribe_sections`
  - payload: `{ "entity_id": "sensor.electricity_price" }`
  - events: `{ "type": "event", "event": { "entity_id": ..., "sections": [...] } }`

## Troubleshooting

- If another device does not show updates:
  - Confirm **Sync** is enabled on that specific card.
  - Confirm the integration is added (Devices & Services).
  - If the JS file is cached on mobile: change the resource URL by adding a query parameter, e.g.
    - `/local/energy-graph-scheduler-card.js?v=20260109`

- If the backend does not respond:
  - Check Home Assistant logs for errors loading the custom component.

