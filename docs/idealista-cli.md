# idealista-cli (reference)

This is a short reference for the local `idealista-cli` helper.

## Run

From your local `idealista-cli` folder (example: `~/idealista-cli`):

```bash
python3 -m idealista_cli --help
```

## Credentials

Recommended (env vars):

```bash
export IDEALISTA_API_KEY="<CLIENT_ID>"
export IDEALISTA_API_SECRET="<CLIENT_SECRET>"
```

Or persist locally:

```bash
python3 -m idealista_cli config set --api-key "<CLIENT_ID>" --api-secret "<CLIENT_SECRET>"
```

Config path:
- `~/.config/idealista-cli/config.json`

Token cache:
- `~/.cache/idealista-cli/token.json`

## Commands

### token

```bash
python3 -m idealista_cli token
python3 -m idealista_cli token --refresh
```

### search

```bash
python3 -m idealista_cli search --help
```

Example:

```bash
python3 -m idealista_cli search \
  --center "39.594,-0.458" \
  --distance 5000 \
  --operation sale \
  --property-type homes \
  --all-pages \
  --format summary
```
