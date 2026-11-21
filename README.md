# Water Meter API Examples

Official example clients for the Water Meter Recognition API using curl, Python, Node.js, Java, .NET, Go, PHP, and PowerShell.

- Website: https://watermeterai.com/
- API documentation: https://watermeterai.com/en/api-docs
- API Keys: https://watermeterai.com/en/api-keys

Use this repository to test image upload, task polling, quota checks, and public AI status checks from your own application.

## Repository Purpose

This public GitHub repository is for Water Meter API examples and website discovery. It is designed to help developers find the API on GitHub, run a small example, and continue on the website.

This repository contains only public API client examples. It does not include AI service code, dispatch code, backend source code, models, private endpoints, deployment details, or internal architecture.

## Photo-to-CSV Client Project

The [WaterMeter Photo-to-CSV client project](examples/python/photo_to_csv/README.md) will provide a photo review and CSV export workflow using the public API. Its project directory and documentation have been initialized; a runnable application is not available yet.

## Quick Start

1. Sign in at https://watermeterai.com/
2. Create an API key at https://watermeterai.com/en/api-keys
3. Copy `.env.example` to `.env` and set:

```text
WATERMETER_API_BASE=https://watermeterai.com
WATERMETER_API_KEY=wm_xxxxxxxxxxxxxxxxx
IMAGE_PATH=./sample-images/example.jpg
```

4. Put a local test image at `IMAGE_PATH`.
5. Run one example client.

## API Flow

The examples use only public API endpoints:

- `GET /api/open/ai-status`
- `GET /api/open/quota`
- `POST /api/open/tasks`
- `GET /api/open/tasks/{task_id}`

Each example uploads one image, stores the returned `task_id`, polls until the task reaches `done` or `failed`, then prints the final result.

## Run Examples

### curl

Requires `curl` and `jq`.

```bash
cd examples/curl
chmod +x single-task.sh
./single-task.sh
```

### Python

```bash
cd examples/python
python -m pip install -r requirements.txt
python recognize.py
```

### Node.js

Requires Node.js 18 or newer.

```bash
cd examples/node
npm install
npm start
```

### Java

Requires JDK 11 or newer.

```bash
cd examples/java
javac Recognize.java
java Recognize
```

### .NET

Requires .NET 8 SDK or newer.

```bash
cd examples/dotnet
dotnet run
```

### Go

```bash
cd examples/go
go run .
```

### PHP

Requires PHP with the curl extension.

```bash
cd examples/php
php recognize.php
```

### PowerShell

Requires PowerShell 7.

```powershell
cd examples/powershell
pwsh ./recognize.ps1
```

## Common HTTP Errors

- `401`: API key is missing or invalid.
- `413`: Image file is too large.
- `415`: Image type or file content is not supported.
- `429`: Quota is exhausted.

## Security

- Never commit `.env`.
- Never commit real API keys or tokens.
- Do not call private backend, dispatch, or AI service endpoints.
- Server-side code should keep the API key on the server. Do not expose API keys in browser JavaScript.

## License

MIT License. You can copy and adapt these examples in your own applications.

## Suggested GitHub Metadata

Recommended repository description:

```text
Water Meter Recognition API examples for curl, Python, Node.js, Java, .NET, Go, PHP, PowerShell, Postman, and OpenAPI.
```

Recommended topics:

```text
water-meter, meter-reading, image-recognition, computer-vision, ai-api, api-examples, python, nodejs, java, dotnet, go, php, postman, openapi
```
