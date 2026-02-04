from __future__ import annotations

import abc
import asyncio
import datetime
import random
import time
from collections.abc import AsyncIterable, Iterable, Iterator
from dataclasses import dataclass
from enum import Enum, unique
from itertools import count
from typing import (
    Any,
    cast,
)

from .expressions import Parameters, ProjectionExpression
from .types import (
    EncodedGlobalSecondaryIndex,
    EncodedKeySchema,
    EncodedLocalSecondaryIndex,
    EncodedPayPerRequest,
    EncodedProjection,
    EncodedStreamSpecification,
    EncodedThroughput,
    Item,
    Seconds,
    TableName,
)
from .utils import py2dy


@unique
class TimeToLiveStatus(Enum):
    enabling = "ENABLING"
    disabling = "DISABLING"
    enabled = "ENABLED"
    disabled = "DISABLED"


@dataclass(frozen=True)
class TimeToLiveDescription:
    table: str
    attribute: str
    status: TimeToLiveStatus


@dataclass(frozen=True)
class Throughput:
    read: int
    write: int

    def encode(self) -> EncodedThroughput:
        return {
            "ProvisionedThroughput": {
                "ReadCapacityUnits": self.read,
                "WriteCapacityUnits": self.write,
            }
        }


@dataclass(frozen=True)
class PayPerRequest:
    MODE = "PAY_PER_REQUEST"

    def encode(self) -> EncodedPayPerRequest:
        return {"BillingMode": PayPerRequest.MODE}


ThroughputType = Throughput | PayPerRequest


class KeyType(Enum):
    string = "S"
    number = "N"
    binary = "B"


@dataclass(frozen=True)
class KeySpec:
    name: str
    type: KeyType


@dataclass(frozen=True)
class KeySchema:
    """Key schema supporting single or multi-attribute partition and sort keys.

    For backward compatibility, single KeySpec values are accepted. For multi-attribute
    keys (GSIs only), pass a tuple of KeySpec values.

    DynamoDB supports up to 4 attributes each for partition (HASH) and sort (RANGE) keys.
    """

    hash_key: KeySpec | tuple[KeySpec, ...]
    range_key: KeySpec | tuple[KeySpec, ...] | None = None

    def __post_init__(self) -> None:
        hash_keys = self._normalize(self.hash_key)
        if not (1 <= len(hash_keys) <= 4):
            raise ValueError("hash_key must have 1-4 attributes")
        if self.range_key:
            range_keys = self._normalize(self.range_key)
            if len(range_keys) > 4:
                raise ValueError("range_key must have 0-4 attributes")

    @staticmethod
    def _normalize(key: KeySpec | tuple[KeySpec, ...]) -> tuple[KeySpec, ...]:
        return key if isinstance(key, tuple) else (key,)

    def __iter__(self) -> Iterator[KeySpec]:
        yield from self._normalize(self.hash_key)
        if self.range_key:
            yield from self._normalize(self.range_key)

    def to_attributes(self) -> dict[str, str]:
        return {key.name: key.type.value for key in self}

    def encode(self) -> list[EncodedKeySchema]:
        hash_keys = self._normalize(self.hash_key)
        result: list[EncodedKeySchema] = [
            {"AttributeName": k.name, "KeyType": "HASH"} for k in hash_keys
        ]
        if self.range_key:
            range_keys = self._normalize(self.range_key)
            result.extend(
                {"AttributeName": k.name, "KeyType": "RANGE"} for k in range_keys
            )
        return result


class ProjectionType(Enum):
    all = "ALL"
    keys_only = "KEYS_ONLY"
    include = "INCLUDE"


@dataclass(frozen=True)
class Projection:
    type: ProjectionType
    attrs: list[str] | None = None

    def encode(self) -> EncodedProjection:
        encoded: EncodedProjection = {"ProjectionType": self.type.value}
        if self.attrs:
            encoded["NonKeyAttributes"] = self.attrs
        return encoded


@dataclass(frozen=True)
class LocalSecondaryIndex:
    name: str
    schema: KeySchema
    projection: Projection

    def encode(self) -> EncodedLocalSecondaryIndex:
        return {
            "IndexName": self.name,
            "KeySchema": self.schema.encode(),
            "Projection": self.projection.encode(),
        }


@dataclass(frozen=True)
class GlobalSecondaryIndex(LocalSecondaryIndex):
    throughput: Throughput | None

    def encode(self) -> EncodedGlobalSecondaryIndex:
        # mypy really does not like an if/else assignment where the branches have
        # different types, so we need to do some ridiculous casting here.
        # The outer cst is due to https://github.com/python/mypy/issues/4122
        # The two inner casts to Any are because of the if/else with different types
        return cast(
            EncodedGlobalSecondaryIndex,
            {
                **super().encode(),
                **(
                    cast(Any, self.throughput.encode())
                    if self.throughput
                    else cast(Any, {})
                ),
            },
        )


class StreamViewType(Enum):
    keys_only = "KEYS_ONLY"
    new_image = "NEW_IMAGE"
    old_image = "OLD_IMAGE"
    new_and_old_images = "NEW_AND_OLD_IMAGES"


@dataclass(frozen=True)
class StreamSpecification:
    enabled: bool = False
    view_type: StreamViewType = StreamViewType.new_and_old_images

    def encode(self) -> EncodedStreamSpecification:
        spec: EncodedStreamSpecification = {"StreamEnabled": self.enabled}
        if self.enabled:
            spec["StreamViewType"] = self.view_type.value
        return spec


class ReturnValues(Enum):
    none = "NONE"
    all_old = "ALL_OLD"
    updated_old = "UPDATED_OLD"
    all_new = "ALL_NEW"
    updated_new = "UPDATED_NEW"


class TableStatus(Enum):
    creating = "CREATING"
    updating = "UPDATING"
    deleting = "DELETING"
    active = "ACTIVE"


@dataclass(frozen=True)
class TableDescription:
    attributes: dict[str, KeyType] | None
    created: datetime.datetime | None
    item_count: int | None
    key_schema: KeySchema | None
    throughput: ThroughputType | None
    status: TableStatus

    @classmethod
    def from_response(cls, description: dict[str, Any]) -> TableDescription:
        attributes: dict[str, KeyType] | None
        if "AttributeDefinitions" in description:
            attributes = {
                attribute["AttributeName"]: KeyType(attribute["AttributeType"])
                for attribute in description["AttributeDefinitions"]
            }
        else:
            attributes = None
        creation_time: datetime.datetime | None
        if "CreationDateTime" in description:
            creation_time = datetime.datetime.fromtimestamp(
                description["CreationDateTime"], datetime.UTC
            )
        else:
            creation_time = None
        key_schema: KeySchema | None
        if attributes and "KeySchema" in description:
            key_schema = cls._parse_key_schema(description["KeySchema"], attributes)
        else:
            key_schema = None
        throughput: ThroughputType | None
        if (
            "BillingModeSummary" in description
            and description["BillingModeSummary"]["BillingMode"] == PayPerRequest.MODE
        ):
            throughput = PayPerRequest()
        elif "ProvisionedThroughput" in description:
            throughput = Throughput(
                read=description["ProvisionedThroughput"]["ReadCapacityUnits"],
                write=description["ProvisionedThroughput"]["WriteCapacityUnits"],
            )
        else:
            throughput = None
        return TableDescription(
            attributes=attributes,
            created=creation_time,
            item_count=description.get("ItemCount", None),
            key_schema=key_schema,
            throughput=throughput,
            status=TableStatus(description["TableStatus"]),
        )

    @staticmethod
    def _parse_key_schema(
        key_schema_list: list[dict[str, str]],
        attributes: dict[str, KeyType],
    ) -> KeySchema:
        """Parse KeySchema from DynamoDB response, handling multi-attribute keys."""
        hash_keys: list[KeySpec] = []
        range_keys: list[KeySpec] = []

        for key in key_schema_list:
            name = key["AttributeName"]
            spec = KeySpec(name=name, type=attributes[name])
            if key["KeyType"] == "HASH":
                hash_keys.append(spec)
            else:
                range_keys.append(spec)

        return KeySchema(
            hash_key=tuple(hash_keys) if len(hash_keys) > 1 else hash_keys[0],
            range_key=(
                (tuple(range_keys) if len(range_keys) > 1 else range_keys[0])
                if range_keys
                else None
            ),
        )


class Select(Enum):
    all_attributes = "ALL_ATTRIBUTES"
    all_projected_attributes = "ALL_PROJECTED_ATTRIBUTES"
    count = "COUNT"
    specific_attributes = "SPECIFIC_ATTRIBUTES"


class RetryTimeout(Exception):
    pass


# https://github.com/python/mypy/issues/5374
@dataclass(frozen=True)
class MyPyWorkaroundRetryConfigBase:
    time_limit_secs: Seconds = 60


class RetryConfig(MyPyWorkaroundRetryConfigBase, metaclass=abc.ABCMeta):
    @classmethod
    def default(cls) -> RetryConfig:
        """
        Default RetryConfig to be used as a throttle config for Client
        """
        return ExponentialBackoffRetry()

    @classmethod
    def default_wait_config(cls) -> RetryConfig:
        """
        Default RetryConfig to be used as wait config for table level operations.
        """
        return ExponentialBackoffRetry(time_limit_secs=500)

    @abc.abstractmethod
    def delays(self) -> Iterable[Seconds]:
        """
        Custom RetryConfig classes must implement this method. It should return
        an iterable yielding numbers of seconds indicating the delay before the
        next attempt is made.
        """
        raise NotImplementedError()

    async def attempts(self) -> AsyncIterable[None]:
        deadline = time.monotonic() + self.time_limit_secs
        for delay in self.delays():
            yield
            if time.monotonic() > deadline:
                raise RetryTimeout()
            await asyncio.sleep(delay)


@dataclass(frozen=True)
class StaticDelayRetry(RetryConfig):
    delay: Seconds = 1

    def delays(self) -> Iterable[Seconds]:
        while True:
            yield self.delay


@dataclass(frozen=True)
class DecorelatedJitterRetry(RetryConfig):
    base_delay_secs: Seconds = 0.05
    max_delay_secs: Seconds = 1

    def delays(self) -> Iterable[Seconds]:
        current_delay_secs = self.base_delay_secs
        while True:
            current_delay_secs = min(
                self.max_delay_secs,
                random.uniform(self.base_delay_secs, current_delay_secs * 3),
            )
            yield current_delay_secs


@dataclass(frozen=True)
class ExponentialBackoffRetry(RetryConfig):
    base_delay_secs: Seconds = 2
    max_delay_secs: Seconds = 20

    def delays(self) -> Iterable[Seconds]:
        for attempt in count():
            yield min(
                random.random() * (self.base_delay_secs**attempt), self.max_delay_secs
            )


@dataclass(frozen=True)
class Page:
    items: list[Item]
    last_evaluated_key: dict[str, Any] | None

    @property
    def is_last_page(self) -> bool:
        return self.last_evaluated_key is None


@dataclass(frozen=True)
class BatchGetRequest:
    keys: list[Item]
    projection: ProjectionExpression | None = None
    consistent_read: bool = False

    def to_request_payload(self) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "Keys": [py2dy(key) for key in self.keys],
            "ConsistentRead": self.consistent_read,
        }
        if self.projection:
            params = Parameters()
            payload["ProjectionExpression"] = self.projection.encode(params)
            payload.update(params.to_request_payload())

        return payload


@dataclass(frozen=True)
class BatchGetResponse:
    items: dict[TableName, list[Item]]
    unprocessed_keys: dict[TableName, list[Item]]


@dataclass(frozen=True)
class BatchWriteRequest:
    keys_to_delete: list[Item] | None = None
    items_to_put: list[Item] | None = None

    def to_request_payload(self) -> list[dict[str, Any]]:
        payload: list[dict[str, Any]] = []
        if self.keys_to_delete:
            payload.extend(
                {"DeleteRequest": {"Key": py2dy(key)}} for key in self.keys_to_delete
            )
        if self.items_to_put:
            payload.extend(
                {"PutRequest": {"Item": py2dy(item)}} for item in self.items_to_put
            )
        return payload


@dataclass(frozen=True)
class BatchWriteResult:
    undeleted_keys: list[Item]
    unput_items: list[Item]
