base: main

[tabularium]
focused: mise exec uv@0.12.21 -- uv run pytest tests/<file> | -k <pattern>
full: mise exec uv@0.12.21 -- uv run pytest --junit-xml .test-results/pytest.xml
