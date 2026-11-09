#!/usr/bin/env bats

setup() {
  TEST_TEMP_DIR="$(mktemp -d)"
  OUTPUT_DIR="$(mktemp -d)"
  export GITHUB_OUTPUT="${OUTPUT_DIR}/github_output"
  touch "$GITHUB_OUTPUT"
  export SCRIPT_PATH="$(cd "${BATS_TEST_DIRNAME}/.." && pwd)/publish_fix.sh"

  # Create an isolated clean git repository
  cd "$TEST_TEMP_DIR"
  git init -q
  git config user.name "test-user"
  git config user.email "test@example.com"
  echo "initial" > init.txt
  git add init.txt
  git commit -q -m "initial commit"
}

teardown() {
  rm -rf "$TEST_TEMP_DIR" "$OUTPUT_DIR"
}

@test "publish_fix exits with error when git working tree is clean" {
  cd "$TEST_TEMP_DIR"
  run bash "$SCRIPT_PATH"
  [ "$status" -eq 1 ]
  run grep "remediated=false" "$GITHUB_OUTPUT"
  [ "$status" -eq 0 ]
}
