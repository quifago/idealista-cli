# idealista-cli

Small CLI helper for the Idealista API (v3.5). It wraps OAuth2, paging, and basic stats.

This repo also includes a Clawdbot skill file at `skill/SKILL.md` so agents can call the CLI.

## Setup

Request access + credentials: https://developers.idealista.com/access-request

Use env vars:

```
export IDEALISTA_API_KEY="..."
export IDEALISTA_API_SECRET="..."
```

Or store them in a config file:

```
python3 -m idealista_cli config set --api-key "..." --api-secret "..."
```

## Examples

### Natural language (via the Skill + an AI agent)

If you use the Clawdbot skill (`skill/SKILL.md`) and wire it into an AI agent, you can ask for real-estate info in natural language and have the agent translate it into CLI calls.

Example prompts:
- "Find a flat in A Coruña under 200.000€"
- "Tell me the average price of a house around here: 39°34'33.5\"N 0°30'10.0\"W"
- "Búscame un apartamento de 3 habs en Tapia de Casariego para comprar"
- "Cuanto vale mi actual vivienda? Dame una estimacion de precios"

### CLI commands

Get a token (with retries/timeout):

```
python3 -m idealista_cli token --retries 3 --timeout 30
```

Search homes for sale near Betera (center + distance in meters):

```
python3 -m idealista_cli search \
  --center "39.594,-0.458" \
  --distance 5000 \
  --operation sale \
  --property-type homes \
  --all-pages \
  --format summary
```

Compute averages grouped by property type:

```
python3 -m idealista_cli avg \
  --center "39.594,-0.458" \
  --distance 5000 \
  --operation sale \
  --property-type homes \
  --group-by propertyType
```

Pass extra API filters:

```
python3 -m idealista_cli search \
  --center "40.123,-3.242" \
  --distance 2000 \
  --filter maxPrice=400000 \
  --filter minSize=80
```

Handle rate limits / transient errors:

```
python3 -m idealista_cli search \
  --center "39.594,-0.458" \
  --distance 5000 \
  --operation sale \
  --property-type homes \
  --retries 5 \
  --timeout 30 \
  --format summary
```

## Notes

- The API expects multipart form data for search.
- Token caching lives at `~/.cache/idealista-cli/token.json`.
- Config lives at `~/.config/idealista-cli/config.json`.
