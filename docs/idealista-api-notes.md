# Idealista API notes (OAuth2 + Property Search v3.5)

## OAuth2 token

Endpoint:
- `POST https://api.idealista.com/oauth/token`

Headers:
- `Authorization: Basic <base64(client_id:client_secret)>`
- `Content-Type: application/x-www-form-urlencoded;charset=UTF-8`

Body:
- `grant_type=client_credentials`
- `scope=read` (optional)

Response includes:
- `access_token`, `token_type`, `expires_in`, `scope`

## Property search

Endpoint:
- `POST https://api.idealista.com/3.5/{country}/search`

Auth:
- `Authorization: Bearer <token>`
- `Content-Type: multipart/form-data`

Required params:
- `country` (`es`, `it`, `pt`)
- `operation` (`sale`, `rent`)
- `propertyType` (`homes`, `offices`, `premises`, `garages`, `bedrooms`)

Common filters:
- `center` (`lat,lon`)
- `distance` (meters)
- `locationId`
- `maxItems` (max 50)
- `numPage`
- `minPrice`, `maxPrice`
- `sinceDate` (`W`, `M`, `T`, `Y`)
- `order` (varies by property type)

Notes:
- The API uses **application-only authentication** (OAuth2 client credentials).
- Results contain `elementList` entries with fields such as `price`, `priceByArea`, `propertyType`, `municipality`, `district`, `url`, etc.
