# bioscope-aiodynamo

[![PyPI version](https://img.shields.io/pypi/v/bioscope-aiodynamo.svg)](https://pypi.org/project/bioscope-aiodynamo/)

Asynchronous pythonic DynamoDB client; **2x** faster than `aiobotocore/boto3/botocore`.

## Fork Notice

This is a fork of [HENNGE/aiodynamo](https://github.com/HENNGE/aiodynamo), originally created by Jonas Obrist.

### Changes from upstream

This fork was primarily created to add support for [DynamoDB's new multi-attribute keys](https://docs.aws.amazon.com/amazondynamodb/latest/developerguide/GSI.DesignPattern.MultiAttributeKeys.html)

Additionally, this fork has the following modernizations:

- **Python 3.13+** required (dropped support for 3.8-3.12)
- **Modernized tooling**: uv, ruff, basedpyright (replaced poetry, black, isort, mypy)
- **Modern Python syntax**: `X | None` instead of `Optional[X]`, `list[str]` instead of `List[str]`, etc.

## Installation

```bash
pip install "bioscope-aiodynamo[httpx]"
```

Or with uv:

```bash
uv add "bioscope-aiodynamo[httpx]"
```

## Quick Start

### With httpx

```python
from aiodynamo.client import Client
from aiodynamo.credentials import Credentials
from aiodynamo.http.httpx import HTTPX
from httpx import AsyncClient

async def main():
    async with AsyncClient() as h:
        client = Client(HTTPX(h), Credentials.auto(), "us-east-1")
```

### With aiohttp

```bash
pip install "bioscope-aiodynamo[aiohttp]"
```

```python
from aiodynamo.client import Client
from aiodynamo.credentials import Credentials
from aiodynamo.http.aiohttp import AIOHTTP
from aiohttp import ClientSession

async def main():
    async with ClientSession() as session:
        client = Client(AIOHTTP(session), Credentials.auto(), "us-east-1")
```

## Basic Usage

```python
from aiodynamo.client import Client
from aiodynamo.expressions import F
from aiodynamo.models import Throughput, KeySchema, KeySpec, KeyType

async def main(client: Client):
    table = client.table("my-table")

    # Create table if it doesn't exist
    if not await table.exists():
        await table.create(
            Throughput(read=10, write=10),
            KeySchema(hash_key=KeySpec("key", KeyType.string)),
        )

    # Create or override an item
    await table.put_item({"key": "my-item", "value": 1})

    # Get an item
    item = await table.get_item({"key": "my-item"})
    print(item)

    # Update an item, if it exists
    await table.update_item(
        {"key": "my-item"}, F("value").add(1), condition=F("key").exists()
    )
```

## Multi-Attribute Keys (GSI)

DynamoDB supports up to 4 attributes each for partition and sort keys in Global Secondary Indexes. This fork adds full support for this feature.

### Creating a GSI with Multi-Attribute Keys

```python
from aiodynamo.models import (
    GlobalSecondaryIndex,
    KeySchema,
    KeySpec,
    KeyType,
    PayPerRequest,
    Projection,
    ProjectionType,
)

# Create a GSI with multi-attribute partition and sort keys
gsi = GlobalSecondaryIndex(
    name="tenant-region-date-index",
    schema=KeySchema(
        hash_key=(
            KeySpec("tenant", KeyType.string),
            KeySpec("region", KeyType.string),
        ),
        range_key=(
            KeySpec("date", KeyType.string),
            KeySpec("seq", KeyType.number),
        ),
    ),
    projection=Projection(ProjectionType.all),
    throughput=None,
)

# Create table with the GSI
await client.create_table(
    "my-table",
    PayPerRequest(),
    KeySchema(hash_key=KeySpec("id", KeyType.string)),
    gsis=[gsi],
)
```

### Querying Multi-Attribute Keys

```python
from aiodynamo.expressions import MultiHashKey, RangeKey

# Query with multi-attribute partition key only
async for item in client.query(
    "my-table",
    MultiHashKey(("tenant", "acme"), ("region", "us-east")),
    index="tenant-region-date-index",
):
    print(item)

# Query with partition key + sort key conditions
async for item in client.query(
    "my-table",
    MultiHashKey(("tenant", "acme"), ("region", "us-east"))
    & RangeKey("date").equals("2025-01-01")
    & RangeKey("seq").gt(0),
    index="tenant-region-date-index",
):
    print(item)
```

### Multi-Attribute Key Rules

- **Partition keys**: All attributes must use equality (`=`) conditions
- **Sort keys**: Must be queried left-to-right without gaps
- **Rightmost sort key**: Only the last sort key in a query can use inequality/range/begins_with

## Why aiodynamo

- boto3 and botocore are synchronous. aiodynamo is built for **asynchronous** apps.
- aiodynamo is **fast**. Two times faster than aiobotocore, botocore or boto3 for operations such as query or scan.
- aiobotocore is very low level. aiodynamo provides a **pythonic API**, using modern Python features. For example, paginated APIs are automatically depaginated using asynchronous iterators.
- **Legible source code**. botocore and derived libraries generate their interface at runtime, so it cannot be inspected and isn't typed. aiodynamo is hand written code you can read, inspect and understand.
- **Pluggable HTTP client**. If you're already using an asynchronous HTTP client in your project, you can use it with aiodynamo and don't need to add extra dependencies or run into dependency resolution issues.

## License

This is a modified fork of [aiodynamo](https://github.com/HENNGE/aiodynamo) by HENNGE, licensed under the Apache License 2.0.

See [LICENSE](LICENSE) for the full license text.
