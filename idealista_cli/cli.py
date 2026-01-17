import argparse
import json
import statistics
import sys

from .client import (
    IdealistaClient,
    cache_path,
    config_path,
    load_config,
    save_config,
)


def _parse_kv(text):
    if "=" not in text:
        raise argparse.ArgumentTypeError("Expected key=value")
    key, value = text.split("=", 1)
    return key.strip(), value.strip()


def _add_search_args(parser):
    parser.add_argument("--country", default="es")
    parser.add_argument("--operation", default="sale", help="sale or rent")
    parser.add_argument("--property-type", default="homes", help="homes, offices, premises, garages, bedrooms")
    parser.add_argument("--center", help="lat,lon")
    parser.add_argument("--distance", type=int, help="meters")
    parser.add_argument("--location-id")
    parser.add_argument("--locale")
    parser.add_argument("--max-items", type=int, default=50)
    parser.add_argument("--num-page", type=int, default=1)
    parser.add_argument("--pages", type=int, help="limit pages when using --all-pages")
    parser.add_argument("--all-pages", action="store_true")
    parser.add_argument("--filter", action="append", default=[], type=_parse_kv, help="extra filter key=value")
    parser.add_argument("--timeout", type=int, default=30, help="request timeout seconds")
    parser.add_argument("--retries", type=int, default=3, help="retries for rate limits / transient errors")


def _build_params(args):
    params = {
        "operation": args.operation,
        "propertyType": args.property_type,
        "center": args.center,
        "distance": args.distance,
        "locationId": args.location_id,
        "locale": args.locale,
        "maxItems": args.max_items,
        "numPage": args.num_page,
    }
    for key, value in args.filter:
        params[key] = value
    return params


def _validate_search_args(args, parser):
    if not args.center and not args.location_id:
        parser.error("Provide --center or --location-id")


def _compute_stats(values):
    values = [v for v in values if v is not None]
    if not values:
        return None
    return {
        "count": len(values),
        "avg": sum(values) / len(values),
        "median": statistics.median(values),
        "min": min(values),
        "max": max(values),
    }


def _render_table(rows, headers):
    widths = [len(h) for h in headers]
    for row in rows:
        for idx, cell in enumerate(row):
            widths[idx] = max(widths[idx], len(cell))
    lines = []
    header = "  ".join(h.ljust(widths[i]) for i, h in enumerate(headers))
    lines.append(header)
    lines.append("  ".join("-" * w for w in widths))
    for row in rows:
        lines.append("  ".join(row[i].ljust(widths[i]) for i in range(len(headers))))
    return "\n".join(lines)


def _fmt_number(value, digits=2):
    if value is None:
        return "-"
    return f"{value:.{digits}f}"


def cmd_config(args):
    if args.action == "set":
        if not args.api_key or not args.api_secret:
            raise SystemExit("Both --api-key and --api-secret are required")
        path = save_config(args.api_key, args.api_secret)
        print(f"Saved config to {path}")
        return

    cfg = load_config()
    masked_secret = "***" if cfg.get("api_secret") else "(missing)"
    print("Config path:", config_path())
    print("API key:", cfg.get("api_key", "(missing)"))
    print("API secret:", masked_secret)


def cmd_token(args):
    client = IdealistaClient(timeout=args.timeout, max_retries=args.retries)
    token = client.get_token(scope=args.scope, refresh=args.refresh)
    print(token)


def cmd_search(args, parser):
    _validate_search_args(args, parser)
    client = IdealistaClient(timeout=args.timeout, max_retries=args.retries)
    params = _build_params(args)

    if args.all_pages:
        data = client.search_all(country=args.country, pages=args.pages, **params)
    else:
        data = client.search(country=args.country, **params)

    if args.format == "json":
        print(json.dumps(data, indent=2))
        return

    if args.format == "summary":
        summary = data.get("summary")
        total = data.get("total")
        total_pages = data.get("totalPages")
        print(f"total={total} pages={total_pages} summary={summary}")
        return

    elements = data.get("elementList", [])
    limit = args.limit if args.limit is not None else len(elements)
    fields = args.fields.split(",") if args.fields else [
        "price",
        "priceByArea",
        "size",
        "rooms",
        "bathrooms",
        "propertyType",
        "municipality",
        "district",
        "url",
    ]
    rows = []
    for el in elements[:limit]:
        row = []
        for field in fields:
            value = el.get(field)
            row.append("-" if value is None else str(value))
        rows.append(row)
    print(_render_table(rows, fields))


def cmd_avg(args, parser):
    _validate_search_args(args, parser)
    client = IdealistaClient(timeout=args.timeout, max_retries=args.retries)
    params = _build_params(args)

    data = client.search_all(country=args.country, pages=args.pages, **params)
    elements = data.get("elementList", [])

    group_by = args.group_by
    if group_by:
        groups = {}
        for el in elements:
            key = el.get(group_by) or "unknown"
            groups.setdefault(key, []).append(el)
    else:
        groups = {"all": elements}

    result = {}
    for key, items in groups.items():
        prices = [el.get("price") for el in items]
        prices_m2 = [el.get("priceByArea") for el in items]
        result[key] = {
            "price": _compute_stats(prices),
            "priceByArea": _compute_stats(prices_m2),
        }

    if args.format == "json":
        print(json.dumps(result, indent=2))
        return

    rows = []
    for key in sorted(result.keys()):
        price = result[key]["price"] or {}
        price_m2 = result[key]["priceByArea"] or {}
        rows.append([
            key,
            str(price.get("count", 0)),
            _fmt_number(price.get("avg"), digits=0),
            _fmt_number(price.get("median"), digits=0),
            _fmt_number(price_m2.get("avg"), digits=0),
            _fmt_number(price_m2.get("median"), digits=0),
        ])
    headers = ["group", "count", "avg_price", "median_price", "avg_price_m2", "median_price_m2"]
    print(_render_table(rows, headers))


def build_parser():
    parser = argparse.ArgumentParser(prog="idealista")
    sub = parser.add_subparsers(dest="command")

    p_config = sub.add_parser("config", help="manage credentials")
    p_config.add_argument("action", choices=["show", "set"], nargs="?", default="show")
    p_config.add_argument("--api-key")
    p_config.add_argument("--api-secret")
    p_config.set_defaults(func=cmd_config)

    p_token = sub.add_parser("token", help="print an oauth token")
    p_token.add_argument("--scope", default="read")
    p_token.add_argument("--refresh", action="store_true")
    p_token.add_argument("--timeout", type=int, default=30, help="request timeout seconds")
    p_token.add_argument("--retries", type=int, default=3, help="retries for rate limits / transient errors")
    p_token.set_defaults(func=cmd_token)

    p_search = sub.add_parser("search", help="search listings")
    _add_search_args(p_search)
    p_search.add_argument("--format", choices=["json", "table", "summary"], default="table")
    p_search.add_argument("--limit", type=int)
    p_search.add_argument("--fields", help="comma-separated list of fields for table output")
    p_search.set_defaults(func=cmd_search)

    p_avg = sub.add_parser("avg", help="compute averages")
    _add_search_args(p_avg)
    p_avg.add_argument("--group-by", choices=["propertyType", "municipality", "district"])
    p_avg.add_argument("--format", choices=["json", "table"], default="table")
    p_avg.set_defaults(func=cmd_avg)

    return parser


def main(argv=None):
    parser = build_parser()
    args = parser.parse_args(argv)
    if not getattr(args, "command", None):
        parser.print_help()
        return 1

    try:
        if args.command in {"search", "avg"}:
            args.func(args, parser)
        else:
            args.func(args)
        return 0
    except Exception as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
