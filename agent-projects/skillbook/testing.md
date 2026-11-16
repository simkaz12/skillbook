base: master

[skillbook]
focused: bash hooks/test-scope-map.sh | bash scripts/tests/test_pull_base.sh | python3 -m unittest <module>
full: bash hooks/test-scope-map.sh
full: python3 -m unittest discover -s skills/flow-eval/tests
full: python3 -m unittest discover -s scripts/tests
full: bash scripts/tests/test_pull_base.sh
full: python3 scripts/corpus-check.py --self-test
full: bash hooks/test-agent-additions.sh
