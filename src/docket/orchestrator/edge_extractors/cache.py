from hashlib import sha256

from ..file_readers import SourceFile
from .prompt import PROMPT_VERSION


# TODO: Probably need a UnknownModelError? Idk if the lib does this
def hash_slinging_slasher(model: str, sources: list[SourceFile]) -> str:
    """
    Hash a job's source files with the model and prompt version.

    Args:
        model: the llm provider to use
        sources: a list of source files to generate the cache for

    Returns:
        The hashed representation (the key)
    """
    digest = sha256()
    digest.update(f"{PROMPT_VERSION}\x00{model}\x00".encode())
    for source in sorted(sources, key=lambda source: source["path"]):
        contents_hash = sha256(source["contents"].encode()).hexdigest()
        digest.update(f"{source['path']}\x00{contents_hash}\x00".encode())
    return digest.hexdigest()
