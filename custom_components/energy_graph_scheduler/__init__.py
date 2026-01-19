from __future__ import annotations

import logging
from typing import Any

import voluptuous as vol

from homeassistant.components import websocket_api
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.dispatcher import async_dispatcher_connect, async_dispatcher_send
from homeassistant.helpers.storage import Store

from .const import DOMAIN, STORAGE_KEY, STORAGE_VERSION

CONFIG_SCHEMA = cv.config_entry_only_config_schema(DOMAIN)

_LOGGER = logging.getLogger(__name__)


def _signal_sections(entity_id: str) -> str:
    return f"{DOMAIN}_sections_updated::{entity_id}"


def _signal_settings(entity_id: str) -> str:
    return f"{DOMAIN}_settings_updated::{entity_id}"


def _normalize_sections(raw: Any) -> list[dict[str, Any]]:
    if not isinstance(raw, list):
        return []

    out: list[dict[str, Any]] = []
    for item in raw:
        if not isinstance(item, dict):
            continue
        name = str(item.get("name") or "").strip()
        if not name:
            continue
        try:
            hours = int(item.get("hours", 1))
        except Exception:
            hours = 1
        if hours < 1:
            hours = 1
        if hours > 24:
            hours = 24
        out.append({"name": name, "hours": hours})

    # Keep stable order; de-dupe by name (first wins)
    seen: set[str] = set()
    uniq: list[dict[str, Any]] = []
    for s in out:
        nm = s["name"]
        if nm in seen:
            continue
        seen.add(nm)
        uniq.append(s)

    # Avoid unbounded growth
    return uniq[:100]


def _normalize_settings(raw: Any) -> dict[str, Any]:
    if not isinstance(raw, dict):
        raw = {}

    interval_minutes = raw.get("interval_minutes")
    try:
        interval_minutes = int(interval_minutes)
    except Exception:
        interval_minutes = 60

    if interval_minutes not in (15, 60):
        interval_minutes = 60

    return {"interval_minutes": interval_minutes}


def _register_websocket(hass: HomeAssistant) -> None:
    if hass.data.get(DOMAIN, {}).get("ws_registered"):
        return
    hass.data[DOMAIN]["ws_registered"] = True

    @websocket_api.websocket_command(
        {
            vol.Required("type"): f"{DOMAIN}/get_sections",
            vol.Required("entity_id"): cv.string,
        }
    )
    @websocket_api.async_response
    async def ws_get_sections(hass: HomeAssistant, connection, msg):
        entity_id = str(msg.get("entity_id") or "").strip()
        data = hass.data.get(DOMAIN, {})
        sections_by_entity = data.get("sections_by_entity") or {}
        sections = []
        if entity_id and isinstance(sections_by_entity, dict):
            sections = sections_by_entity.get(entity_id) or []
        connection.send_result(msg["id"], {"sections": _normalize_sections(sections)})

    @websocket_api.websocket_command(
        {
            vol.Required("type"): f"{DOMAIN}/set_sections",
            vol.Required("entity_id"): cv.string,
            vol.Required("sections"): list,
        }
    )
    @websocket_api.async_response
    async def ws_set_sections(hass: HomeAssistant, connection, msg):
        entity_id = str(msg.get("entity_id") or "").strip()
        if not entity_id:
            connection.send_error(msg["id"], "invalid_entity_id", "entity_id is required")
            return

        sections = _normalize_sections(msg.get("sections"))

        data = hass.data.get(DOMAIN, {})
        store: Store | None = data.get("store")
        if store is None:
            connection.send_error(msg["id"], "not_ready", "store not initialized")
            return

        sections_by_entity = data.get("sections_by_entity")
        if not isinstance(sections_by_entity, dict):
            sections_by_entity = {}
        sections_by_entity[entity_id] = sections
        data["sections_by_entity"] = sections_by_entity

        # Preserve settings when saving sections.
        settings_by_entity = data.get("settings_by_entity")
        if not isinstance(settings_by_entity, dict):
            settings_by_entity = {}

        try:
            await store.async_save(
                {"sections_by_entity": sections_by_entity, "settings_by_entity": settings_by_entity}
            )
            async_dispatcher_send(hass, _signal_sections(entity_id))
            connection.send_result(msg["id"], {"ok": True})
        except Exception as e:
            _LOGGER.warning("%s: failed saving store: %s", DOMAIN, e)
            connection.send_error(msg["id"], "save_failed", str(e))

    websocket_api.async_register_command(hass, ws_get_sections)
    websocket_api.async_register_command(hass, ws_set_sections)

    @websocket_api.websocket_command(
        {
            vol.Required("type"): f"{DOMAIN}/get_settings",
            vol.Required("entity_id"): cv.string,
        }
    )
    @websocket_api.async_response
    async def ws_get_settings(hass: HomeAssistant, connection, msg):
        entity_id = str(msg.get("entity_id") or "").strip()
        data = hass.data.get(DOMAIN, {})
        settings_by_entity = data.get("settings_by_entity") or {}
        exists = False
        settings: dict[str, Any]
        if entity_id and isinstance(settings_by_entity, dict) and entity_id in settings_by_entity:
            exists = True
            raw = settings_by_entity.get(entity_id) or {}
            settings = _normalize_settings(raw)
        else:
            settings = _normalize_settings({})
        connection.send_result(msg["id"], {"settings": settings, "exists": exists})

    @websocket_api.websocket_command(
        {
            vol.Required("type"): f"{DOMAIN}/set_settings",
            vol.Required("entity_id"): cv.string,
            vol.Required("settings"): dict,
        }
    )
    @websocket_api.async_response
    async def ws_set_settings(hass: HomeAssistant, connection, msg):
        entity_id = str(msg.get("entity_id") or "").strip()
        if not entity_id:
            connection.send_error(msg["id"], "invalid_entity_id", "entity_id is required")
            return

        settings = _normalize_settings(msg.get("settings"))

        data = hass.data.get(DOMAIN, {})
        store: Store | None = data.get("store")
        if store is None:
            connection.send_error(msg["id"], "not_ready", "store not initialized")
            return

        settings_by_entity = data.get("settings_by_entity")
        if not isinstance(settings_by_entity, dict):
            settings_by_entity = {}
        settings_by_entity[entity_id] = settings
        data["settings_by_entity"] = settings_by_entity

        # Preserve sections when saving settings.
        sections_by_entity = data.get("sections_by_entity")
        if not isinstance(sections_by_entity, dict):
            sections_by_entity = {}

        try:
            await store.async_save(
                {"sections_by_entity": sections_by_entity, "settings_by_entity": settings_by_entity}
            )
            async_dispatcher_send(hass, _signal_settings(entity_id))
            connection.send_result(msg["id"], {"ok": True})
        except Exception as e:
            _LOGGER.warning("%s: failed saving store: %s", DOMAIN, e)
            connection.send_error(msg["id"], "save_failed", str(e))

    websocket_api.async_register_command(hass, ws_get_settings)
    websocket_api.async_register_command(hass, ws_set_settings)

    @websocket_api.websocket_command(
        {
            vol.Required("type"): f"{DOMAIN}/subscribe_sections",
            vol.Required("entity_id"): cv.string,
        }
    )
    @websocket_api.async_response
    async def ws_subscribe_sections(hass: HomeAssistant, connection, msg):
        entity_id = str(msg.get("entity_id") or "").strip()
        msg_id = msg["id"]

        def _current_sections() -> list[dict[str, Any]]:
            data = hass.data.get(DOMAIN, {})
            sections_by_entity = data.get("sections_by_entity") or {}
            if not entity_id or not isinstance(sections_by_entity, dict):
                return []
            return _normalize_sections(sections_by_entity.get(entity_id) or [])

        @callback
        def _send_update() -> None:
            connection.send_message(
                {
                    "id": msg_id,
                    "type": "event",
                    "event": {"entity_id": entity_id, "sections": _current_sections()},
                }
            )

        # Ack first
        connection.send_result(msg_id, {"ok": True})

        # Send initial state
        _send_update()

        # Subscribe to future updates
        unsub = async_dispatcher_connect(hass, _signal_sections(entity_id), _send_update)
        connection.subscriptions[msg_id] = unsub

    websocket_api.async_register_command(hass, ws_subscribe_sections)

    @websocket_api.websocket_command(
        {
            vol.Required("type"): f"{DOMAIN}/subscribe_settings",
            vol.Required("entity_id"): cv.string,
        }
    )
    @websocket_api.async_response
    async def ws_subscribe_settings(hass: HomeAssistant, connection, msg):
        entity_id = str(msg.get("entity_id") or "").strip()
        msg_id = msg["id"]

        def _current_settings_payload() -> dict[str, Any]:
            data = hass.data.get(DOMAIN, {})
            settings_by_entity = data.get("settings_by_entity") or {}
            if not entity_id or not isinstance(settings_by_entity, dict):
                return {"settings": _normalize_settings({}), "exists": False}
            exists = entity_id in settings_by_entity
            return {"settings": _normalize_settings(settings_by_entity.get(entity_id) or {}), "exists": exists}

        @callback
        def _send_update() -> None:
            connection.send_message(
                {
                    "id": msg_id,
                    "type": "event",
                    "event": {"entity_id": entity_id, **_current_settings_payload()},
                }
            )

        # Ack first
        connection.send_result(msg_id, {"ok": True})

        # Send initial state
        _send_update()

        # Subscribe to future updates
        unsub = async_dispatcher_connect(hass, _signal_settings(entity_id), _send_update)
        connection.subscriptions[msg_id] = unsub

    websocket_api.async_register_command(hass, ws_subscribe_settings)


async def async_setup(hass: HomeAssistant, config: dict) -> bool:
    # Optional YAML fallback: energy_graph_scheduler: in configuration.yaml
    if DOMAIN in config:
        hass.async_create_task(
            hass.config_entries.flow.async_init(DOMAIN, context={"source": "import"}, data={})
        )
    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    store = Store(hass, STORAGE_VERSION, f"{STORAGE_KEY}.json")
    data = await store.async_load() or {}

    hass.data.setdefault(DOMAIN, {})
    hass.data[DOMAIN]["store"] = store
    hass.data[DOMAIN]["sections_by_entity"] = data.get("sections_by_entity", {}) if isinstance(data, dict) else {}
    hass.data[DOMAIN]["settings_by_entity"] = data.get("settings_by_entity", {}) if isinstance(data, dict) else {}

    _register_websocket(hass)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    # Nothing to unload besides stored data.
    # Websocket commands are left registered (consistent with other local integrations here).
    dom = hass.data.get(DOMAIN)
    if isinstance(dom, dict):
        dom.pop("store", None)
        dom.pop("sections_by_entity", None)
        dom.pop("settings_by_entity", None)
    return True
