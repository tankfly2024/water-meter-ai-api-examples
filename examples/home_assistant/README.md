# WaterMeter AI for Home Assistant

[简体中文](README.zh-CN.md) · [Website](https://watermeterai.com/) · [API documentation](https://watermeterai.com/en/api-docs) · [Get an API key](https://watermeterai.com/en/api-keys)

Use an existing Home Assistant camera to read a water meter through the WaterMeter AI cloud API. Display a cumulative reading, review questionable changes, and prepare a water sensor for the Energy dashboard. Supported service capabilities include pointer and mechanical digit meters; LED recognition is not promised.

**Visit [watermeterai.com](https://watermeterai.com/) to try water meter recognition, [register for free](https://watermeterai.com/en/login?flow=register), and [create an API key for free](https://watermeterai.com/en/api-keys).** Ordinary free accounts include **20 recognitions per day**, shared across the website, this integration, and other API clients. Use your website account's key here; actual account-specific quotas apply. Start with the [API documentation](https://watermeterai.com/en/api-docs).

**Status: 0.1.0 local prototype, for testing.** State-engine and loopback HTTP tests are available. Installation in a real Home Assistant instance, camera capture, configuration UI, statistics, and production API recognition still need end-to-end verification. This is a manually installed custom integration, with no claim of official Home Assistant inclusion or HACS distribution. The adapter references Home Assistant 2026.11.2 APIs; other releases are not certified.

## What it does

- Select an existing `camera` entity and enter your own API key in the configuration UI.
- Press **Read meter** to capture and upload one JPEG, PNG, or WEBP image (maximum 20 MB). It does not schedule reads or upload photos on startup.
- First readings and forward changes above your configured threshold become pending readings. **Confirm pending reading** accepts them; **Discard pending reading** leaves the previous total intact.
- Smaller forward changes can update the total automatically after the initial confirmation. These remain AI estimates: choose the threshold carefully for your meter and reading frequency.
- Backwards readings, rejected quality results, and failed tasks keep the previous total. Invalid readings are never converted to zero. Meter replacement, rollover, and resetting statistics are outside this prototype's scope.
- Persist the accepted value, pending candidate, task ID, and image digest in Home Assistant storage. After a polling timeout or restart, press **Read meter** to query the saved task without uploading again. Identical consecutive image bytes are not submitted again.
- Show the server's free-account daily quota after recognition. Website and all clients share the same allowance: ordinary free accounts have **20 recognitions per day**, reset on the server's calendar day (normally Asia/Shanghai), with no rollover. Custom and paid account policies take precedence. Installing the integration does not create additional quota or grant a partnership allowance.

## Manual installation

You need an existing Home Assistant instance, a working camera entity showing a supported water meter, internet access, and an API key with quota-read, task-submit, and task-read access. This integration does not add a camera driver or run the recognition model locally.

1. Back up your Home Assistant configuration.
2. Copy the entire `custom_components/watermeter_ai` folder into your Home Assistant configuration directory. The final path must be `<config>/custom_components/watermeter_ai/manifest.json`. If using the installation ZIP, extract it first and copy that folder.
3. Restart Home Assistant.
4. Open **Settings → Devices & services → Add integration → WaterMeter AI**.
5. Enter your API key, choose the camera, choose the unit represented by the API reading (`m³` or `L`), and set the maximum automatic increase. The default threshold is `10` in that unit. The integration does not infer or convert the returned reading's unit: check it against the physical meter before confirming.
6. Open the new device, press **Read meter**, compare its pending reading with the physical meter, then confirm or discard it.

The device exposes four sensors (total, pending reading, recognition status, free recognitions remaining today) and three buttons (read, confirm, discard). Entity IDs are assigned by Home Assistant and may differ from examples. The total is initially unknown until you confirm a reading. Paid accounts do not display a fabricated free daily balance.

## Water statistics and optional automation

The accepted total declares `device_class: water`, `state_class: total`, and your selected volume unit. Once live-host checks are complete, it is intended for selection under **Settings → Dashboards → Energy → Water consumption**. The first accepted lifetime reading becomes a baseline; it is not the amount used today. Verify statistics in your actual installation before relying on the chart. See the [Home Assistant water guide](https://www.home-assistant.io/docs/energy/water/) and [sensor state-class reference](https://contributors.home-assistant.io/core/entities/sensor/).

[examples/automation.yaml](examples/automation.yaml) illustrates two reads per day, using the Home Assistant timezone. Replace its button entity ID and add it yourself if needed. It is not installed or enabled automatically. Allow room in the shared daily quota for website use and manual retries. If a reading needs review, subsequent automated reads remain blocked until you confirm or discard it.

## Errors, persistence, and privacy

- An API key is stored in Home Assistant's native configuration entry. It is absent from sensors and this plugin's meter-state storage, but Home Assistant configuration files and backups contain the credential. Protect access to them.
- Captured photos go to `https://watermeterai.com` for recognition when a read is explicitly requested. The plugin does not save photo bytes to disk; normal Home Assistant camera behavior and the service's data policies apply separately.
- Setup checks the key using only a quota GET. No recognition is triggered by setup or restart. Quota is refreshed after recognition rather than polled continuously; the displayed balance can be stale after activity in another client.
- A rejected upload (for example HTTP 429) requires a manual retry; the client does not loop uploads. A timeout, broken response, or cancellation during submission can mean the server accepted the task without returning its ID. In that case the status says **Check website task history**, and further uploads are blocked to avoid duplicate charges. Check the website history first. This prototype has no in-UI recovery for an unknown submission or a deleted task; after resolving it on the website, remove and add the integration again to start a new local entry. Do not recreate the entry while a submission remains uncertain.
- Invalid credentials during an active recognition start Home Assistant reauthentication. Updating the key preserves local meter state and saved task IDs; the replacement key must access the same account's task.
- To stop future scheduled uploads, disable any automation you created. Removing the integration does not cancel cloud tasks already submitted.

## Build and test

The engine, transport tests, and packaging script require only Python 3.9+ standard libraries. The complete integration needs the Python version and dependencies of your Home Assistant installation.

```bash
python -B -m unittest discover -s tests -v
python -B package.py --output watermeter-ai-0.1.0.zip
```

Tests use fake readings and an actual loopback HTTP server, with no production API calls. The optional Home Assistant import check is skipped if the host is not installed; passing that check alone would still not establish live-host compatibility. The ZIP contains only custom-integration source, translations, instructions, and an example automation. It contains no model, credential, image, or server code.

For batch image review and spreadsheet export, use the separate [WaterMeter Image-to-CSV client](../python/image_to_csv/README.md).
