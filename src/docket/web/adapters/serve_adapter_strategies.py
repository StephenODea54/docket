import os
from abc import ABC, abstractmethod
from typing import Any, ClassVar

import uvicorn
from fastapi import FastAPI

RUNTIME_API = "AWS_LAMBDA_RUNTIME_API"

handler: Any = None


class ServeAdapterStrategy(ABC):
    type: ClassVar[str]

    @abstractmethod
    def serve(self, app: FastAPI, host: str, port: int) -> None:
        """
        Host the app until the process is told to stop.

        Args:
            app: the web application
            host: bind host, when the runtime binds a socket
            port: bind port, when the runtime binds a socket

        Returns:
            None
        """


class UvicornAdapter(ServeAdapterStrategy):
    type: ClassVar[str] = "uvicorn"

    def serve(self, app: FastAPI, host: str, port: int) -> None:
        """
        Serve the app with uvicorn bound to host and port.

        Args:
            app: the web application
            host: bind host
            port: bind port

        Returns:
            None
        """
        uvicorn.run(app, host=host, port=port)


class LambdaAdapter(ServeAdapterStrategy):
    type: ClassVar[str] = "lambda"

    def serve(self, app: FastAPI, host: str, port: int) -> None:
        """
        Serve the app from inside the AWS Lambda runtime; host and port are ignored.

        Wraps the app with Mangum and hands it to the Lambda Runtime Interface
        Client, which polls the runtime API for invocations until the execution
        environment is recycled. Requires the `lambda` extra.

        Args:
            app: the web application
            host: ignored
            port: ignored

        Returns:
            None

        Raises:
            RuntimeError: if not running inside AWS Lambda, or the `lambda`
                extra is not installed
        """
        global handler
        if RUNTIME_API not in os.environ:
            raise RuntimeError(
                f"{RUNTIME_API} is not set; "
                "the lambda adapter only runs inside AWS Lambda"
            )
        try:
            from awslambdaric.__main__ import main as run_runtime_client
            from mangum import Mangum
        except ImportError as error:
            raise RuntimeError(
                "the lambda adapter needs the `lambda` extra: "
                "pip install 'docket[lambda]'"
            ) from error
        handler = Mangum(app, lifespan="off")
        run_runtime_client(["awslambdaric", f"{__name__}.handler"])


STRATEGIES: list[type[ServeAdapterStrategy]] = [UvicornAdapter, LambdaAdapter]

ADAPTERS: dict[str, type[ServeAdapterStrategy]] = {cls.type: cls for cls in STRATEGIES}
