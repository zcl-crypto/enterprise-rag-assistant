# Security Policy

## Supported version

Only the latest version on the `main` branch is supported.

## Reporting a vulnerability

Please do not disclose a vulnerability in a public issue. Contact the repository
owner privately through the contact method shown on the GitHub profile and include
reproduction steps, affected components, and the expected impact.

## Deployment notice

This repository is a local portfolio project, not a hosted service. Before any
shared or public deployment:

- replace every `change-me` value in `.env`;
- use a dedicated, least-privilege model API key;
- enable TLS and an external authentication layer;
- review uploaded documents for confidential information;
- add rate limiting, backup, monitoring, and a production secret manager.

Never commit `.env`, model credentials, database volumes, uploaded files, or
production documents.
