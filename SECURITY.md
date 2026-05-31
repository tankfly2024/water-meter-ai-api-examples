# Security

## Public API Only

This repository contains public API usage examples only.

Do not add:

- Private service endpoints
- AI service source code
- Dispatch or backend source code
- Model files
- API keys, tokens, or `.env` files
- Logs, uploaded images, or recognition result files

## API Keys

API keys must be stored outside Git, for example in a local `.env` file or your deployment platform's secret manager.

Do not expose API keys in browser JavaScript or public client applications.
