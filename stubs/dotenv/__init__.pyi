from typing import Any, Optional

def load_dotenv(
    dotenv_path: Optional[str] = ...,
    stream: Optional[Any] = ...,
    verbose: bool = ...,
    interpolate: bool = ...,
    override: bool = ...,
    encoding: Optional[str] = ...,
) -> bool: ...

def set_key(
    dotenv_path: str,
    key_to_set: str,
    value_to_set: str,
    quote_mode: str = ...,
    export: bool = ...,
    encoding: str = ...,
) -> tuple[Optional[bool], str, str]: ...

def get_key(dotenv_path: str, key_to_get: str, encoding: str = ...) -> Optional[str]: ...
def unset_key(dotenv_path: str, key_to_unset: str, quote_mode: str = ..., encoding: str = ...) -> tuple[Optional[bool], str]: ...
def find_dotenv(filename: str = ..., raise_error_if_not_found: bool = ..., usecwd: bool = ...) -> str: ...
def dotenv_values(dotenv_path: Optional[str] = ..., stream: Optional[Any] = ..., verbose: bool = ..., interpolate: bool = ..., override: bool = ..., encoding: Optional[str] = ...) -> dict[str, Optional[str]]: ...
