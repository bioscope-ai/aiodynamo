import decimal
from collections.abc import Callable
from enum import Enum
from typing import Any, TypedDict

Timeout = float | int
Numeric = float | int | decimal.Decimal

Item = dict[str, Any]
DynamoItem = dict[str, dict[str, Any]]
TableName = str


class ParametersDict(TypedDict, total=False):
    ExpressionAttributeNames: dict[str, str]
    ExpressionAttributeValues: dict[str, dict[str, Any]]


NOTHING = object()

Seconds = float | int


class AttributeType(Enum):
    string = "S"
    string_set = "SS"
    number = "N"
    number_set = "NS"
    binary = "B"
    binary_set = "BS"
    boolean = "BOOL"
    null = "NULL"
    list = "L"
    map = "M"


class EncodedThroughputData(TypedDict):
    ReadCapacityUnits: int
    WriteCapacityUnits: int


class EncodedThroughput(TypedDict):
    ProvisionedThroughput: EncodedThroughputData


class EncodedPayPerRequest(TypedDict):
    BillingMode: str


class EncodedKeySchema(TypedDict):
    AttributeName: str
    KeyType: str


class EncodedProjectionRequired(TypedDict):
    ProjectionType: str


class EncodedProjection(EncodedProjectionRequired, total=False):
    NonKeyAttributes: list[str]


class EncodedLocalSecondaryIndex(TypedDict):
    IndexName: str
    KeySchema: list[EncodedKeySchema]
    Projection: EncodedProjection


class EncodedGlobalSecondaryIndex(EncodedLocalSecondaryIndex, total=False):
    ProvisionedThroughput: EncodedThroughput


class EncodedStreamSpecificationRequired(TypedDict):
    StreamEnabled: bool


class EncodedStreamSpecification(EncodedStreamSpecificationRequired, total=False):
    StreamViewType: str


SIMPLE_TYPES = frozenset({AttributeType.boolean, AttributeType.string})


NumericTypeConverter = Callable[[str], Any]
