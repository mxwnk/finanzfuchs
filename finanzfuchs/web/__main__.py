"""`python -m finanzfuchs.web` starts the web app (as in the container)."""

import logging
import os

import uvicorn

from finanzfuchs.config import Settings, WebSettings
from finanzfuchs.web.app import create_app


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s %(message)s")
    web_settings = WebSettings.from_environment(os.environ)
    app = create_app(Settings.from_environment(os.environ), web_settings)
    uvicorn.run(app, host=web_settings.host, port=web_settings.port, proxy_headers=True)


if __name__ == "__main__":
    main()
