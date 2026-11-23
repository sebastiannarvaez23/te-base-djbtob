from enum import Enum


class DataType(str, Enum):
    STRING = 'STRING'
    INT = 'INT'
    DECIMAL = 'DECIMAL'
    BOOL = 'BOOL'
    JSON = 'JSON'
