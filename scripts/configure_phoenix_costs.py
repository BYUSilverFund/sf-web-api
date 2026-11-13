"""Preview/add local Phoenix prices; never connects to AWS or application DBs.

Run from sf-web-api: python -m scripts.configure_phoenix_costs [--apply]
Existing price entries are preserved; conflicting custom prices stop the script.
"""

import argparse
import json
import os
from pathlib import Path
import re
import urllib.request

from dotenv import load_dotenv

from app.observability import collector_endpoint
from app.telemetry_costs import PRICES, PRICE_SOURCE


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--apply",
        action="store_true",
        help="Create missing price entries in LOCAL Phoenix only",
    )
    args = parser.parse_args()
    load_dotenv(Path(__file__).resolve().parents[1] / ".env", override=False)
    endpoint = collector_endpoint(
        os.getenv("PHOENIX_COLLECTOR_ENDPOINT", "http://localhost:6006")
    )
    url = endpoint.removesuffix("/v1/traces") + "/graphql"
    key = os.environ["PHOENIX_API_KEY"]

    def graphql(query, variables=None):
        request = urllib.request.Request(
            url,
            data=json.dumps({"query": query, "variables": variables or {}}).encode(),
            headers={
                "Authorization": f"Bearer {key}",
                "Content-Type": "application/json",
            },
        )
        with urllib.request.urlopen(request, timeout=10) as response:
            payload = json.load(response)
        if payload.get("errors"):
            raise RuntimeError(
                "Phoenix rejected the model-pricing query; check API version/key permissions"
            )
        return payload["data"]

    current = graphql(
        "{generativeModels(first:1000){edges{node{name provider namePattern tokenPrices{tokenType kind costPerMillionTokens}}}}}"
    )["generativeModels"]["edges"]
    print("Price reference:", PRICE_SOURCE)
    for (region, model), rates in PRICES.items():
        costs = [
            {
                "tokenType": "input",
                "kind": "PROMPT",
                "costPerMillionTokens": float(rates[0]),
            },
            {
                "tokenType": "output",
                "kind": "COMPLETION",
                "costPerMillionTokens": float(rates[1]),
            },
        ]
        pattern = "^" + re.escape(model) + "$"
        matches = [
            edge["node"]
            for edge in current
            if edge["node"]["namePattern"] == pattern
            and edge["node"]["provider"] == "aws"
        ]
        if matches:
            actual = {
                p["tokenType"]: p["costPerMillionTokens"]
                for p in matches[0]["tokenPrices"]
            }
            if actual.get("input") != float(rates[0]) or actual.get("output") != float(
                rates[1]
            ):
                raise RuntimeError(
                    "Existing local model pricing differs; review it in Phoenix Settings > Models"
                )
            print("Already configured:", model)
            continue
        print("Create" if args.apply else "Would create", model, region, costs)
        if args.apply:
            result = graphql(
                "mutation($input:CreateModelMutationInput!){createModel(input:$input){model{name}}}",
                {
                    "input": {
                        "name": f"Silver Fund local {model} ({region})",
                        "provider": "aws",
                        "namePattern": pattern,
                        "startTime": "2026-11-11T00:00:00+00:00",
                        "costs": costs,
                    }
                },
            )
            print("Created:", result["createModel"]["model"]["name"])


if __name__ == "__main__":
    main()
