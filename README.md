# Custom Entity for Home Assistant

Create **any kind of entity** by mirroring the state of another one—then pick which
attributes to inherit, add more from other sensors, and even merge a zone name
with a live sensor value. All configurable from the UI; no YAML required.

## Quick install

1. **Install the integration code**

   [![Install with HACS][(https://my.home-assistant.io/badges/hacs_repository.svg)](https://my.home-assistant.io/redirect/hacs_repository/?repository_url=https://github.com/BitBasherr/Custom-Entitycustom_components/custom_entity
   *(HACS will prompt you to restart Home Assistant once the download finishes.)*

2. **Add the integration via UI**

   [![Add Custom Entity to Home Assistant](https://my.home-assistant.io/badges/config_flow_start.svg)](https://my.home-assistant.io/redirect/config_flow_start?domain=custom_entity)

---

## What it does

* **Mirror any source entity** – `device_tracker`, `sensor`, `media_player`,  
  you name it.
* **Choose the device class** – the new entity reports as temperature, power,
  window, motion … whatever you pick.
* **Inherit only the attributes you want** from the source (multi-select
  during setup).
* **Expose extra attributes** from arbitrary sensors (weight, AQI, W-zever
  travel time…).
* **Optional battery sensor** and **“combine” attribute**  
  (e.g. show *“Home – 20 min”* instead of just *“Home”*).

All options are changeable later via the **Options** dialog; the entity reloads
itself automatically—no restart needed.

---

## Installation

### Quick link

Click the **blue button** at the top of this page while you’re logged in to your
Home Assistant UI.

### HACS

1. **HACS → Integrations → ⋮ → Custom repositories**  
   Add: `https://github.com/BitBasherr/Custom-Entity` | Category: **Integration**
2. Search for **Custom Entity**, click **Install**.
3. Restart Home Assistant once. Updates will show up in HACS.

### Manual

1. Copy the `custom_components/custom_entity/` folder into  
   `<config>/custom_components/` on your HA server.
2. Restart Home Assistant.

---

## Setup

1. **Settings → Devices & Services → + Add Integration → Custom Entity**  
   (or click the blue badge above).
2. **Wizard** steps  
   1. Pick a **source entity** and give your new entity a friendly name.  
   2. Choose a **device class** from the dropdown.  
   3. Tick which **attributes to inherit** from the source.  
   4. Decide whether to merge a **zone name with a sensor value**  
      (e.g. combine *Home* with *sensor.time_to_home*).  
3. Press **Finish** – your new entity appears immediately.

### Options (later)

* **Battery sensor** – maps a sensor’s numeric state to `battery_level`.  
* **Extra attributes** – add “Friendly Name → sensor.entity_id” pairs.  
* **Rename / delete** inherited or extra attributes.  
* Toggle **combine** on/off or point it at a different sensor.

---

## Example use-cases

* Display *“Garage  − 35 °C”* where *Garage* is the zone you’re in and 35 °C
  comes from an external temperature sensor.
* Build a presence entity that also exposes phone battery, Wi-Fi signal, and
  travel time to work as attributes—perfect for automations.
* Mirror a noisy sensor to a clean one that publishes only the two attributes
  you care about, with a meaningful device class and name.

---

## Feedback / Issues

Open an issue or pull request on  
<https://github.com/BitBasherr/Custom-Entity>.
Contributions and suggestions are welcome!
