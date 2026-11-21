# WaterMeter Image-to-CSV

[简体中文](README.zh-CN.md) · [API examples](../../../README.md)

A client project for turning water meter images into reviewable readings and CSV files with the WaterMeter AI public API.

**Get started at [watermeterai.com](https://watermeterai.com/): try recognition on the website, [register for free](https://watermeterai.com/en/login?flow=register), then [create an API key for free](https://watermeterai.com/en/api-keys).** Ordinary free accounts receive **20 recognitions per day**, shared by the website and all API tools. Keep the same account when moving from the website to this client; actual account-specific quotas apply. Read the [API guide](https://watermeterai.com/en/api-docs).

**Status: runnable local prototype.** Image import, task submission and polling, offline demo, manual review, pause/resume, and CSV export are implemented. Automated workflow checks use a local mock API; production recognition has not yet been verified for this client. A packaged desktop installer is not provided.

## Start Locally

Requires Python 3.9 or newer; no additional packages are needed.

```text
python -B run.py
```

Open the local URL printed by the program. Use **Try the offline demo** without an API key, or import your own JPEG, PNG, or WEBP images and connect your own key. Imported images are sent to the API only when you start recognition. Stop the program with Ctrl+C.

Data defaults to `.watermeter-image-to-csv` in your user directory. Use `--data-dir` to choose another local directory and `--port` to select a port. The program binds to the loopback interface only. API keys remain in process memory and are not stored in the review session or browser storage.

## Workflow

1. Select one or more images of pointer or mechanical digit water meters.
2. Submit images for recognition using the user's own API key.
3. Compare each returned reading with its original image and review status.
4. Keep the AI reading and a separate user-confirmed reading.
5. Export filenames, readings, statuses, and notes to CSV, retaining unreadable items for review.

The application uses the public quota, task submission, and task polling endpoints. API usage follows the account's current server-side quota and service terms. Demo illustrations and saved values are explicitly labeled and are never submitted for live recognition.

Ordinary free accounts receive **20 recognitions per day**, shared with the website. The allowance resets each server-side calendar day (normally Asia/Shanghai); unused calls do not roll over. Account-specific, paid, and cooperation quotas follow the server response. The client shows the actual daily limit, used calls, and remaining calls, and refreshes quota after processing. Status polling and the offline demo do not consume recognition allowance.

CSV retains original AI readings separately from user-confirmed values, including leading zeros and decimals. Import reading columns as Text in spreadsheet software to prevent automatic numeric conversion. Failed and unreadable rows remain in the export.

Pause/resume reuses existing task IDs. Uncertain submission responses are never automatically retried: check the account's task history before resubmitting. Images imported after a run starts wait for the next manual run.

## Project Layout

```text
image_to_csv/
  README.md
  README.zh-CN.md
  run.py
  .gitignore
  src/              Application source
  tests/            Client tests
  docs/             User and developer documentation
```

User images, exported tables, credentials, and logs belong in a separate local data directory outside the source tree. The local ignore rules also exclude common private inputs and outputs placed here accidentally.

## Tests and Further Help

```text
python -B tests/test_client.py
```

Tests use temporary local data and a mock API, with no production requests. See the [Chinese user guide](docs/使用说明.md) for the full workflow and recovery behavior.

## Single-Image API Example

The existing [Python single-image example](../recognize.py) and its [dependencies](../requirements.txt) remain available while this client is being developed. Follow the repository's [quick start](../../../README.md#quick-start) to use that example.

- Website: https://watermeterai.com/
- API documentation: https://watermeterai.com/en/api-docs
- API Keys: https://watermeterai.com/en/api-keys
