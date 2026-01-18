# Energy Graph Scheduler — Sync

[![Downloads](https://img.shields.io/github/downloads/qlerup/energy-graph-scheduler-sync/total)](https://github.com/qlerup/energy-graph-scheduler-sync/releases)


<img width="1044" height="136" alt="image" src="https://github.com/user-attachments/assets/52267b4b-617d-4752-9d60-a4cba7b89a35" />


This setup consists of two separate parts:

1. The Lovelace card (installed separately):
  - https://github.com/qlerup/energy-graph-scheduler-card
2. The Home Assistant backend integration (this repo / your HA config):
  - `custom_components/energy_graph_scheduler/`

The integration provides syncing of the card’s “cheapest time” sections between all users/devices via Home Assistant `.storage`.

## What is synced?

The card’s **sections** (the items you add under “Billigste tider”, e.g. “Dishwasher 3 hours”).

They are synced **per selected electricity price entity** (e.g. `sensor.electricity_price`).

## Domain

- Integration domain: `energy_graph_scheduler`

## Installation / Setup

1. Install the card (separately):
  - Follow the instructions in: https://github.com/qlerup/energy-graph-scheduler-card

2. Install the sync integration (this part):
  - Ensure this folder exists in your HA config:
    - `custom_components/energy_graph_scheduler/`

3. Restart Home Assistant.

4. Add the integration:
   - Settings → Devices & Services → Add Integration → **Energy Graph Scheduler**

5. In the card configuration/editor, enable **Sync** (see below).

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

