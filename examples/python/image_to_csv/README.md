# WaterMeter Image-to-CSV

[简体中文](README.zh-CN.md) · [API examples](../../../README.md)

A client project for turning water meter images into reviewable readings and CSV files with the WaterMeter AI public API.

**Status: project initialization.** The directory layout and planned scope are recorded. Application features, a launcher, and a downloadable release are not implemented yet.

## Planned Workflow

1. Select one or more images of pointer or mechanical digit water meters.
2. Submit images for recognition using the user's own API key.
3. Compare each returned reading with its original image and review status.
4. Keep the AI reading and a separate user-confirmed reading.
5. Export filenames, readings, statuses, and notes to CSV, retaining unreadable items for review.

The application will use the public status, quota, task submission, and task polling endpoints. API usage follows the account's current server-side quota and service terms.

## Project Layout

```text
image_to_csv/
  README.md
  README.zh-CN.md
  .gitignore
  src/              Application source
  tests/            Client tests
  docs/             User and developer documentation
```

User images, exported tables, credentials, and logs belong in a separate local data directory outside the source tree. The local ignore rules also exclude common private inputs and outputs placed here accidentally.

## Existing Working Example

The existing [Python single-image example](../recognize.py) and its [dependencies](../requirements.txt) remain available while this client is being developed. Follow the repository's [quick start](../../../README.md#quick-start) to use that example.

- Website: https://watermeterai.com/
- API documentation: https://watermeterai.com/en/api-docs
- API Keys: https://watermeterai.com/en/api-keys
