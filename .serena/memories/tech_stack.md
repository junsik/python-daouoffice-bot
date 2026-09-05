# Tech stack

- Python 3.12+ package, built with Hatchling; source version comes from `src/daouoffice/_version.py`.
- Runtime dependencies: `httpx[http2]`, Pydantic v2, PyYAML.
- `uv` is the development package/environment command. The `dev` extra supplies pytest, pytest-asyncio, respx and Ruff.
- Wheel package is explicitly `src/daouoffice`; package CLI entry point is `daoubot = daouoffice.cli:main`.
- Ruff line length is 99; its repository checks deliberately exclude `tools` and distributable `skills` assets.
- Tests run asynchronously with pytest asyncio auto mode and import from `src`.