import abc
from dataclasses import dataclass
from typing import Any

from aiodynamo.errors import EmptyItem
from aiodynamo.expressions import (
    Condition,
    Parameters,
    ProjectionExpression,
    UpdateExpression,
)
from aiodynamo.types import Item, TableName
from aiodynamo.utils import py2dy


class Operation(metaclass=abc.ABCMeta):
    @abc.abstractmethod
    def to_request_payload(self) -> dict[str, Any]:
        pass


@dataclass(frozen=True)
class Get(Operation):
    table: TableName
    key: Item
    projection: ProjectionExpression | None = None

    def to_request_payload(self) -> dict[str, Any]:
        dynamo_key = py2dy(self.key)
        if not dynamo_key:
            raise EmptyItem()

        payload: dict[str, Any] = {
            "TableName": self.table,
            "Key": dynamo_key,
        }

        if self.projection:
            params = Parameters()
            payload["ProjectionExpression"] = self.projection.encode(params)
            payload.update(params.to_request_payload())

        return {"Get": payload}


@dataclass(frozen=True)
class Put(Operation):
    table: TableName
    item: Item
    condition: Condition | None = None

    def to_request_payload(self) -> dict[str, Any]:
        dynamo_item = py2dy(self.item)
        if not dynamo_item:
            raise EmptyItem()

        payload: dict[str, Any] = {
            "TableName": self.table,
            "Item": dynamo_item,
        }
        if self.condition:
            params = Parameters()
            payload["ConditionExpression"] = self.condition.encode(params)
            payload.update(params.to_request_payload())

        return {"Put": payload}


@dataclass(frozen=True)
class Update(Operation):
    table: TableName
    key: Item
    expression: UpdateExpression
    condition: Condition | None = None

    def to_request_payload(self) -> dict[str, Any]:
        params = Parameters()
        expression = self.expression.encode(params)
        if not expression:
            raise EmptyItem()

        payload: dict[str, Any] = {
            "TableName": self.table,
            "UpdateExpression": expression,
            "Key": py2dy(self.key),
        }

        if self.condition:
            payload["ConditionExpression"] = self.condition.encode(params)

        payload.update(params.to_request_payload())

        return {"Update": payload}


@dataclass(frozen=True)
class Delete(Operation):
    table: TableName
    key: Item
    condition: Condition | None = None

    def to_request_payload(self) -> dict[str, Any]:
        dynamo_item = py2dy(self.key)
        if not dynamo_item:
            raise EmptyItem()

        payload: dict[str, Any] = {
            "TableName": self.table,
            "Key": dynamo_item,
        }
        if self.condition:
            params = Parameters()
            payload["ConditionExpression"] = self.condition.encode(params)
            payload.update(params.to_request_payload())

        return {"Delete": payload}


@dataclass(frozen=True)
class ConditionCheck(Operation):
    table: TableName
    key: Item
    condition: Condition | None = None

    def to_request_payload(self) -> dict[str, Any]:
        dynamo_item = py2dy(self.key)
        if not dynamo_item:
            raise EmptyItem()

        payload: dict[str, Any] = {
            "TableName": self.table,
            "Key": dynamo_item,
        }
        if self.condition:
            params = Parameters()
            payload["ConditionExpression"] = self.condition.encode(params)
            payload.update(params.to_request_payload())

        return {"ConditionCheck": payload}
